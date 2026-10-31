#!/usr/bin/env python3
"""One large, deterministic MG5 internal-Condor reliability campaign.

Uses the EXACT source-pinned process-local standard111, delta111, delta221,
and historical delta441_backup backends. Reconstructs the combined status
and submit candidate in memory and tests extracted real CondorCluster methods
against an in-memory scheduler. No actual condor_q, condor_submit, MadGraph
integration, gridpack access, or process modifications.

A single invocation exercises 300 simulated GF/stage identities per backend
over 210 polling rounds by default, with late failures and thousands of
submission/status transitions.

This is NOT a live-scheduler acceptance test. It intentionally identifies
known safety gaps (partial successful queue replies, lost submission ACKs).
"GUARDS_PASS" does NOT mean "PRODUCTION_READY".
"""

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace

from aqp_prepare_bundled_condor_patch import BUNDLES, CENTRAL_SHA, build
from aqp_condor_status_mock import isolated_method, ControlledClusterError
from aqp_condor_submit_mock import get_method, MockClusterError
from aqp_condor_intent_ledger import claim, read, reconcile, UnresolvedIntent

EXPECTED_CANDIDATES = {
    "standard111": "682075381f79c6ad027244a4a2157f6c21b1202ea561fbc40a8fc0d0383a4a2e",
    "delta111": "b2879ef87fa4f1a4f70a79699b2db6c1025c0770c3828d704a6c19acb5d2d17a",
    "delta221": "f17032fc4f814bcbff1b878d1f9192832a266f6f453b82827afe4140dc4c8263",
    "delta441_backup": "a1d0916e8c9a03b2825a87a781077cc85e4f7119cd2a310bc1b9532cefa791c2",
}
def validate_candidate_fingerprints():
    """Reject mistyped or incomplete pinned SHA256 constants before any campaign."""
    if set(EXPECTED_CANDIDATES) != set(BUNDLES):
        raise ValueError("Expected candidate fingerprint set differs from bundled configurations")
    for name, fingerprint in EXPECTED_CANDIDATES.items():
        if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
            raise ValueError("Malformed expected SHA256 for " + name + ": " + fingerprint)


JOBSTATUS = {"0": "U", "1": "I", "2": "R", "3": "X", "4": "C", "5": "H", "6": "E"}


class FakeChild:
    def __init__(self, stdout=b"", stderr=b"", rc=0):
        self.stdout_data = stdout
        self.stderr_data = stderr
        self.returncode = rc

    def communicate(self, input=None):
        return self.stdout_data, self.stderr_data


def original_and_candidate(base, central):
    central_bytes = central.read_bytes()
    if hashlib.sha256(central_bytes).hexdigest() != CENTRAL_SHA:
        raise ValueError("Central ATLAS cluster.py SHA256 mismatch; refusing test")
    orig = central_bytes.decode("utf-8")
    for config, (expected_hash, _) in BUNDLES.items():
        file = base / config / "PROCNLO_loop_sm-no_b_mass_0/bin/internal/cluster.py"
        raw = file.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_hash:
            raise ValueError(config + ": bundled source SHA256 mismatch; refusing test")
        candidate = build(orig, raw.decode("utf-8"), config)
        fingerprint = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        if fingerprint != EXPECTED_CANDIDATES[config]:
            raise ValueError(config + ": candidate SHA256 differs from validated artifact: " + fingerprint)
        yield config, candidate, fingerprint


def status_campaign(path, channels, rounds):
    """Exercise actual patched control/control_one_job bodies over long synthetic histories."""
    response = {"stdout": b"", "stderr": b"", "rc": 0, "calls": 0}

    def popen(argv, *args, **kwargs):
        if not argv or "condor_q" not in str(argv[0]):
            raise AssertionError("Unexpected scheduler command: " + repr(argv))
        response["calls"] += 1
        return FakeChild(response["stdout"], response["stderr"], response["rc"])

    control = isolated_method(path, "control", popen)
    one = isolated_method(path, "control_one_job", popen)
    ids = [str(1000000 + x) for x in range(channels)]
    active = b"".join((f"{job_id} {1 if idx % 3 == 0 else 2}\n").encode()
                      for idx, job_id in enumerate(ids))
    nchecks = 0
    failures = []
    gaps = set()
    scenarios = [
        "all-visible", "queue-warning", "query-fails",
        "malformed-response", "query-fails-with-rows",
        "partial-successful-response", "empty-successful-response",
    ]
    for round_no in range(rounds):
        scenario = scenarios[round_no % len(scenarios)]
        response["calls"] = 0
        response["stdout"], response["stderr"], response["rc"] = active, b"", 0
        if scenario == "queue-warning":
            response["stderr"] = b"nonfatal diagnostic\n"
        elif scenario == "query-fails":
            response.update(stdout=b"", stderr=b"SECMAN:2007\n", rc=42)
        elif scenario == "malformed-response":
            response["stdout"] = active + b"not-a-valid-condor-row\n"
        elif scenario == "query-fails-with-rows":
            response.update(stderr=b"SECMAN:2011\n", rc=42)
        elif scenario == "partial-successful-response":
            response["stdout"] = b"".join(active.splitlines(keepends=True)[:-1])
        elif scenario == "empty-successful-response":
            response["stdout"] = b""

        checked = []
        stub = SimpleNamespace(
            submitted_ids=list(ids), submitted=len(ids), finish=0,
            jobstatus=JOBSTATUS,
            check_termination=lambda job_id: checked.append(job_id) or "wait",
        )
        caught = None
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                control(stub, ".")
        except ControlledClusterError:
            caught = "scheduler_error"
        except Exception as exc:
            caught = type(exc).__name__ + ":" + str(exc)[:120]
        nchecks += channels
        must_fail = scenario in ("query-fails", "malformed-response", "query-fails-with-rows")
        if response["calls"] != 1:
            failures.append(f"round {round_no}: scheduler invoked {response['calls']} times")
        if must_fail:
            if caught != "scheduler_error" or checked:
                failures.append(f"round {round_no}: {scenario} did not fail closed; "
                                f"caught={caught}, output_checks={len(checked)}")
        elif caught:
            failures.append(f"round {round_no}: unexpected exception {caught} ({scenario})")
        elif scenario in ("all-visible", "queue-warning") and checked:
            failures.append(f"round {round_no}: valid active jobs treated as gone")
        elif scenario == "partial-successful-response":
            if checked:
                gaps.add("PARTIAL_EXIT0_QUEUE_RESPONSE_CAN_TRIGGER_MISSING_JOB_HANDLING")
            else:
                # This would represent a stronger safety property, but is not required
                # for the two limited patches under test.
                pass
        elif scenario == "empty-successful-response" and checked:
            gaps.add("EMPTY_EXIT0_QUEUE_REPLY_NOT_INDEPENDENTLY_RECONCILED")

    for i in range(rounds):
        case = i % 4
        response["calls"] = 0
        response["stdout"], response["stderr"], response["rc"] = b"R\n", b"", 0
        if case == 1:
            response.update(stdout=b"", stderr=b"SECMAN:2007\n", rc=42)
        elif case == 2:
            response["stdout"] = b"not-a-status\n"
        elif case == 3:
            response["stdout"] = b""
        stub = SimpleNamespace(jobstatus=JOBSTATUS)
        caught = None
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                result = one(stub, ids[0])
        except ControlledClusterError:
            caught = "scheduler_error"
            result = None
        except Exception as exc:
            caught = type(exc).__name__ + ":" + str(exc)[:120]
            result = None
        if response["calls"] != 1:
            failures.append(f"single-job round {i}: expected one condor_q")
        if case == 0 and (caught or result != "R"):
            failures.append(f"single-job round {i}: valid R response failed")
        if case in (1, 2) and caught != "scheduler_error":
            failures.append(f"single-job round {i}: malformed/failed query not rejected")
        if case == 3 and not caught and result == "":
            gaps.add("EMPTY_SINGLE_JOB_REPLY_NOT_INDEPENDENTLY_RECONCILED")

    return {
        "simulated_gf_status_opportunities": nchecks,
        "aggregate_poll_rounds": rounds,
        "single_job_poll_rounds": rounds,
        "guard_failures": failures[:25],
        "total_guard_failures": len(failures),
        "readiness_gaps": sorted(gaps),
    }


def submission_campaign(path, channels):
    """Exercise actual patched submit/submit2 bodies, without real HTCondor."""
    findings = []
    total_attempts = 0
    success_count = 0
    unresolved_count = 0
    for method_name in ("submit", "submit2"):
        response = {"stdout": b"", "stderr": b"", "rc": 0, "calls": 0}

        def popen(argv, *args, **kwargs):
            if argv != ["condor_submit"]:
                raise AssertionError("Unexpected scheduler command: " + repr(argv))
            response["calls"] += 1
            return FakeChild(response["stdout"], response["stderr"], response["rc"])

        env = {
            "os": os, "re": re, "ClusterManagmentError": MockClusterError,
            "subprocess": SimpleNamespace(PIPE=subprocess.PIPE, Popen=popen),
            "misc": SimpleNamespace(Popen=popen),
        }
        method = get_method(path.read_text(encoding="utf-8"),
                            method_name, env, expect_retry=False)
        stub = SimpleNamespace(cluster_queue=None, options={},
                               submitted=0, submitted_ids=[])
        for gf in range(channels):
            response["calls"] = 0
            job_id = str(900000 + gf + (100000 if method_name == "submit2" else 0))
            kind = gf % 15
            response["stdout"] = f"1 job(s) submitted to cluster {job_id}.\n".encode()
            response["stderr"], response["rc"] = b"", 0
            if kind == 0:
                # Scheduler may have accepted it but acknowledgment was lost.
                response["stdout"] = b"Submitting job(s).\n"
            elif kind == 1:
                # Scheduler returned a cluster ID but signaled failure.
                response["rc"] = 42
            elif kind == 2:
                response["stdout"] = b"submitted to cluster \n"
            kwargs = {"prog": "/bin/true", "cwd": "/tmp"}
            if method_name == "submit2":
                kwargs["input_files"] = ["fake_input.dat"]
            tracked_before = len(stub.submitted_ids)
            caught = None
            try:
                method(stub, **kwargs)
            except MockClusterError as exc:
                caught = str(exc)
            except Exception as exc:
                caught = type(exc).__name__ + ":" + str(exc)[:120]
            total_attempts += response["calls"]
            expected_failure = kind in (0, 1, 2)
            if response["calls"] != 1:
                findings.append(f"{method_name} GF{gf}: {response['calls']} submissions")
            if expected_failure:
                unresolved_count += 1
                if not caught or len(stub.submitted_ids) != tracked_before:
                    findings.append(f"{method_name} GF{gf}: unsafe acknowledgment handling")
            else:
                success_count += 1
                if caught or len(stub.submitted_ids) != tracked_before + 1:
                    findings.append(f"{method_name} GF{gf}: normal submission failed")
                elif stub.submitted_ids[-1] != job_id:
                    findings.append(f"{method_name} GF{gf}: wrong tracked cluster ID")
    return {
        "simulated_submission_attempts": total_attempts,
        "normal_submission_cases": success_count,
        "ambiguous_or_failed_ack_cases": unresolved_count,
        "total_guard_failures": len(findings),
        "guard_failures": findings[:25],
        "readiness_gaps": ["NO_DURABLE_ACK_RECONCILIATION_OR_IDEMPOTENT_RESTART"]
                          if unresolved_count else [],
    }


def ledger_campaign(temp_root, name, channels, rounds):
    """Exercise the isolated persistent-intent model; NOT integrated with MG5."""
    root = Path(temp_root) / (name + "_intents")
    root.mkdir()
    failures = []
    records = []
    duplicates_blocked = 0
    scenarios = (
        "complete", "history-error", "active", "duplicate-jobs",
        "unknown", "wrong-request", "bad-output", "failed-exit",
        "queue-error", "empty-queue-without-history",
    )
    for i in range(channels):
        gf = "GF%d.0" % i
        request_id = "%s_MINT1_GF%d_attempt1" % (name, i)
        try:
            claim(root, name, "MINT1", gf, request_id)
            records.append(read(root, name, "MINT1", gf))
            try:
                claim(root, name, "MINT1", gf, request_id + "_retry")
                failures.append("GF%d permitted second submission intent" % i)
            except UnresolvedIntent:
                duplicates_blocked += 1
        except Exception as exc:
            failures.append("GF%d unexpected ledger error: %s" % (i, exc))

    decisions = 0
    for tick in range(rounds):
        scenario = scenarios[tick % len(scenarios)]
        for record in records:
            rid = record["request_id"]
            item = {"request_id": rid, "job_id": "910001.0",
                    "state": "TERMINATED", "exit_code": 0}
            queue = {"reliable": True, "records": []}
            history = {"reliable": True, "records": [item]}
            artifact = {"verified": True, "matching_request_id": True,
                        "complete_manifest": True}
            expected = "TERMINAL_VERIFIED_NO_AUTOMATIC_RESUBMISSION"
            if scenario == "history-error":
                history["reliable"] = False
                expected = "BLOCK_SCHEDULER_UNAVAILABLE"
            elif scenario == "active":
                queue["records"] = [{"request_id": rid, "job_id": "910001.0",
                                     "state": "RUNNING"}]
                history["records"] = []
                expected = "BLOCK_JOB_ACTIVE"
            elif scenario == "duplicate-jobs":
                history["records"].append({"request_id": rid, "job_id": "910002.0",
                                           "state": "TERMINATED", "exit_code": 2})
                expected = "BLOCK_DUPLICATE_JOBS"
            elif scenario in ("unknown", "empty-queue-without-history"):
                history["records"] = []
                expected = "BLOCK_UNKNOWN_JOB_STATE"
            elif scenario == "wrong-request":
                history["records"][0]["request_id"] = "some_other_request"
                expected = "BLOCK_IDENTITY_MISMATCH"
            elif scenario == "bad-output":
                artifact["complete_manifest"] = False
                expected = "BLOCK_UNVERIFIED_OUTPUT"
            elif scenario == "failed-exit":
                history["records"][0]["exit_code"] = 2
                expected = "BLOCK_FAILED_JOB"
            elif scenario == "queue-error":
                queue["reliable"] = False
                expected = "BLOCK_SCHEDULER_UNAVAILABLE"
            observed = reconcile(record, queue=queue, history=history,
                                 artifact=artifact)
            decisions += 1
            if observed != expected:
                failures.append("%s GF=%s expected=%s observed=%s" %
                                (scenario, record["gf"], expected, observed))
                if len(failures) >= 20:
                    break
        if len(failures) >= 20:
            break
    return {
        "created_intents": len(records),
        "blocked_duplicate_intents": duplicates_blocked,
        "reconciliation_decisions": decisions,
        "total_guard_failures": len(failures),
        "guard_failures": failures[:20],
        "readiness_gaps": [
            "DURABLE_INTENT_MODEL_NOT_INTEGRATED_WITH_MADGRAPH_OR_HTCONDOR"
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path,
                        default=Path.home() / "AQP/Wjets/WENU")
    parser.add_argument("--central", type=Path, required=True,
                        help="Pinned installed ATLAS MG5 3.5.11 cluster.py")
    parser.add_argument("--channels", type=int, default=300)
    parser.add_argument("--rounds", type=int, default=210)
    parser.add_argument("--report", type=Path,
                        help="Optional NEW JSON report path; never overwrite")
    args = parser.parse_args()
    if not (10 <= args.channels <= 2000 and 14 <= args.rounds <= 5000):
        parser.error("channels must be 10..2000 and rounds 14..5000")
    if args.report and args.report.exists():
        parser.error("Report exists; refusing overwrite")

    try:
        validate_candidate_fingerprints()
    except ValueError as exc:
        print("STRESS_SETUP_FAILED", type(exc).__name__, str(exc), file=sys.stderr)
        return 1

    reports = {}
    try:
        with tempfile.TemporaryDirectory(prefix="aqp_condor_stress_") as temp:
            for name, candidate, fingerprint in original_and_candidate(
                    args.base, args.central):
                path = Path(temp) / "cluster.py"
                path.write_text(candidate, encoding="utf-8")
                status = status_campaign(path, args.channels, args.rounds)
                submit = submission_campaign(path, args.channels)
                ledger = ledger_campaign(temp, name, args.channels, args.rounds)
                reports[name] = {
                    "candidate_sha256": fingerprint, "status": status,
                    "submission": submit, "ledger_model": ledger,
                    "guard_failures": (status["total_guard_failures"]
                                       + submit["total_guard_failures"]
                                       + ledger["total_guard_failures"]),
                    "readiness_gaps": sorted(set(status["readiness_gaps"]
                                                  + submit["readiness_gaps"]
                                                  + ledger["readiness_gaps"])),
                }
                path.unlink()
                print("STRESS_CONFIG_DONE", name,
                      "guard_failures=" + str(reports[name]["guard_failures"]),
                      "readiness_gaps=" + str(len(reports[name]["readiness_gaps"])),
                      flush=True)
    except (OSError, ValueError, SyntaxError, RuntimeError) as exc:
        print("STRESS_SETUP_FAILED", type(exc).__name__, str(exc), file=sys.stderr)
        return 1

    all_failures = sum(v["guard_failures"] for v in reports.values())
    all_gaps = sorted(set(g for v in reports.values() for g in v["readiness_gaps"]))
    output = {
        "campaign": "AQP_MG3511_BUNDLED_CONDOR_FULLSCALE_SIMULATION",
        "scope": "source-pinned, extracted backend methods, in-memory scheduler",
        "real_htcondor_calls": 0,
        "production_files_modified": False,
        "delta441_active_backend_tested": False,
        "channels_per_config": args.channels,
        "poll_rounds_per_config": args.rounds,
        "simulated_gf_status_opportunities": sum(
            v["status"]["simulated_gf_status_opportunities"] for v in reports.values()),
        "simulated_submission_attempts": sum(
            v["submission"]["simulated_submission_attempts"] for v in reports.values()),
        "ledger_model_intents": sum(
            v["ledger_model"]["created_intents"] for v in reports.values()),
        "ledger_model_duplicate_intents_blocked": sum(
            v["ledger_model"]["blocked_duplicate_intents"] for v in reports.values()),
        "ledger_model_reconciliation_decisions": sum(
            v["ledger_model"]["reconciliation_decisions"] for v in reports.values()),
        "guards": "PASS" if all_failures == 0 else "FAIL",
        "production_readiness": "BLOCKED" if all_gaps or all_failures else "OFFLINE_ONLY",
        "unresolved_safety_gaps": all_gaps,
        "per_configuration": reports,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as stream:
            json.dump(output, stream, indent=2, sort_keys=True)
            stream.write("\n")
        print("REPORT", args.report)
    print("CAMPAIGN_GUARDS", output["guards"])
    print("SIMULATED_GF_STATUS_OPPORTUNITIES", output["simulated_gf_status_opportunities"])
    print("SIMULATED_SUBMISSIONS", output["simulated_submission_attempts"])
    print("LEDGER_MODEL_INTENTS", output["ledger_model_intents"])
    print("LEDGER_DUPLICATE_INTENTS_BLOCKED", output["ledger_model_duplicate_intents_blocked"])
    print("LEDGER_RECONCILIATION_DECISIONS", output["ledger_model_reconciliation_decisions"])
    print("PRODUCTION_READINESS", output["production_readiness"])
    for gap in all_gaps:
        print("BLOCKER", gap)
    print("NOTE: no real HTCondor jobs submitted; a separate live-scheduler canary is required.")
    # Exit 2 is intentional when the patch guards pass but known release gates remain.
    if all_failures:
        return 1
    return 2 if all_gaps else 0


if __name__ == "__main__":
    sys.exit(main())
