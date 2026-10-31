#!/usr/bin/env python3
"""Exercise ACTUAL isolated combined candidate CondorCluster status methods.

This is method-level FAULT INJECTION, not a full MadGraph controller run.
Never starts condor_q/condor_submit or modifies any real production process.
"""
import argparse
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

from aqp_condor_status_mock import isolated_method, ControlledClusterError


class FakeChild:
    def __init__(self, stdout=b"", stderr=b"", rc=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, rc

    def communicate(self, input=None):
        return self.stdout, self.stderr


def exercise(candidate_path, channels, rounds):
    ids = [str(900000 + i) for i in range(channels)]
    response = {"stdout": b"", "stderr": b"", "rc": 0, "calls": 0}
    guard = {"mode": "ACTIVE", "calls": []}

    def fake_popen(command, *args, **kwargs):
        if not command or not str(command[0]).startswith("condor_q "):
            raise AssertionError("Unexpected subprocess call: %r" % (command,))
        response["calls"] += 1
        return FakeChild(response["stdout"], response["stderr"], response["rc"])

    def check(job):
        guard["calls"].append(job)
        if guard["mode"] == "UNKNOWN":
            raise ControlledClusterError("Scheduler job identity unresolved")
        return guard["mode"]

    controller = isolated_method(candidate_path, "control", fake_popen)
    one = isolated_method(candidate_path, "control_one_job", fake_popen)
    # Inject an isolated fake identity-aware scheduler gate; the companion
    # helper's queue/history parsing has separate regression coverage.
    api = SimpleNamespace(check=check)
    controller.__globals__["_aqp_completion_guard"] = api
    one.__globals__["_aqp_completion_guard"] = api
    checked = []
    stub = SimpleNamespace(
        submitted_ids=list(ids),
        submitted=len(ids),
        finish=0,
        jobstatus={"0": "U", "1": "I", "2": "R", "3": "X",
                   "4": "C", "5": "H", "6": "E"},
        check_termination=lambda job: checked.append(job) or "done",
    )
    scenarios = ("visible", "visible_C", "missing_verified", "missing_unknown",
                 "query_failure", "malformed", "empty_unknown")
    checks = 0
    for index in range(rounds):
        scenario = scenarios[index % len(scenarios)]
        checked.clear()
        guard["calls"].clear()
        response["calls"] = 0
        guard["mode"] = "ACTIVE"
        response["rc"] = 0
        response["stderr"] = b""
        response["stdout"] = b"".join(
            ("%s %s\n" % (job, "4" if scenario == "visible_C" and j == 0 else "2")).encode()
            for j, job in enumerate(ids)
            if not (j == 0 and scenario in ("missing_verified", "missing_unknown"))
        )
        if scenario == "query_failure":
            response.update(stdout=b"", stderr=b"SECMAN:2007", rc=42)
        elif scenario == "malformed":
            response["stdout"] += b"INVALID_ROW\n"
        elif scenario == "empty_unknown":
            response["stdout"] = b""
        if scenario == "missing_verified":
            guard["mode"] = "TERMINATED"
        if scenario in ("missing_unknown", "empty_unknown"):
            guard["mode"] = "UNKNOWN"
        error = None
        try:
            result = controller(stub, ".")
        except ControlledClusterError as exc:
            error = str(exc)
            result = None
        checks += channels
        if response["calls"] != 1:
            raise AssertionError("%s: queried scheduler %d times" %
                                 (scenario, response["calls"]))
        if scenario in ("query_failure", "malformed", "missing_unknown", "empty_unknown"):
            if error is None or checked:
                raise AssertionError("%s: failed to block ambiguous completion" % scenario)
        elif error is not None:
            raise AssertionError("%s: unexpected error %s" % (scenario, error))
        elif scenario == "missing_verified":
            if checked != [ids[0]] or result[2] != 1:
                raise AssertionError("Verified terminal job not handled correctly")
        elif result[2] != 0 or result[1] != channels or checked:
            raise AssertionError("%s: visible running/C job falsely counted finished: %r" %
                                 (scenario, result))

    # Also check the actual candidate's control_one_job body, including
    # the queue-visible 'C' transition and an empty query with history.
    for raw, identity, expected in (
        (b"R\n", "ACTIVE", "R"),
        (b"C\n", "ACTIVE", "R"),
        (b"", "TERMINATED", "C"),
    ):
        response.update(stdout=raw, stderr=b"", rc=0)
        guard["mode"] = identity
        result = one(stub, ids[0])
        if result != expected:
            raise AssertionError("control_one_job %r -> %r (wanted %r)" %
                                 (raw, result, expected))
    return {"poll_rounds": rounds,
            "simulated_status_opportunities": checks,
            "candidate": str(candidate_path),
            "candidate_control_methods": "PASS",
            "real_scheduler_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--channels", type=int, default=300)
    parser.add_argument("--rounds", type=int, default=210)
    args = parser.parse_args()
    if not 10 <= args.channels <= 2000 or not 14 <= args.rounds <= 5000:
        parser.error("Invalid channels/rounds")
    result = exercise(args.candidate, args.channels, args.rounds)
    print("COMBINED_CANDIDATE_STATUS_PASS", json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
