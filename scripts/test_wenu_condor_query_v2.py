#!/usr/bin/env python3
"""Offline regression tests for the Wenu internal-Condor query patch."""
import sys
import types
import unittest
from unittest.mock import patch

from build_wenu_condor_query_v2 import (
    OLD_AGGREGATE, OLD_QUERY, patched_source,
)

FIXTURE = (
    OLD_QUERY + "\n"
    + "def _aqp_states(ids):\n"
    + "    def parse(rows, expected):\n"
    + "        found = {}\n"
    + "        for row in rows:\n"
    + "            if len(row) != 3 or row[0] not in expected or row[1] != '0':\n"
    + "                raise ClusterManagmentError('Malformed status')\n"
    + "            found[row[0]] = row[2]\n"
    + "        return found\n"
    + OLD_AGGREGATE
    + "    return result\n"
)


class ClusterManagmentError(Exception):
    pass


class Response:
    def __init__(self, rc, stdout="", stderr=""):
        self.returncode = rc
        self.stdout = stdout
        self.stderr = stderr


class StubSubprocess:
    TimeoutExpired = TimeoutError

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def run(self, args, capture_output, text, timeout):
        self.calls.append(tuple(args))
        return self.replies.pop(0)


class TestWenuQuery(unittest.TestCase):
    def setUp(self):
        source = patched_source(FIXTURE)
        self.scope = {"ClusterManagmentError": ClusterManagmentError}
        exec(source, self.scope)

    def test_transient_query_failure_recovers(self):
        mock = StubSubprocess([
            Response(1, stderr="Failed to receive remote ad."),
            Response(0, stdout="42 0 2\n"),
        ])
        self.scope["_aqp_query"].__globals__["subprocess"] = mock
        with patch("time.sleep"):
            got = self.scope["_aqp_query"](["condor_q", "42"])
        self.assertEqual(got, [["42", "0", "2"]])
        self.assertEqual(len(mock.calls), 2)

    def test_persistent_failure_stops(self):
        mock = StubSubprocess([
            Response(1, stderr="Failed to receive remote ad.")
            for _ in range(4)
        ])
        self.scope["_aqp_query"].__globals__["subprocess"] = mock
        with patch("time.sleep"), self.assertRaisesRegex(
            ClusterManagmentError, "after 4 attempts"
        ):
            self.scope["_aqp_query"](["condor_q", "42"])

    def test_bounded_batches(self):
        ids = [str(i) for i in range(1000, 1041)]
        replies = []
        for start in range(0, len(ids), 16):
            batch = ids[start:start + 16]
            replies.append(Response(0, stdout="".join(
                "%s 0 2\n" % jid for jid in batch
            )))
        mock = StubSubprocess(replies)
        self.scope["_aqp_query"].__globals__["subprocess"] = mock
        statuses = self.scope["_aqp_states"](ids)
        self.assertEqual(set(statuses), set(ids))
        self.assertEqual(len(mock.calls), 3)
        self.assertLessEqual(max(len(call) - 5 for call in mock.calls), 16)

    def test_unexpected_id_is_rejected(self):
        mock = StubSubprocess([Response(0, stdout="999 0 2\n")])
        self.scope["_aqp_query"].__globals__["subprocess"] = mock
        with self.assertRaisesRegex(ClusterManagmentError, "Malformed status"):
            self.scope["_aqp_states"](["42"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
