# AQP MG5_aMC 3.5.11 internal HTCondor: recovery implementation contract

Status (2026-10-31): **write-once intent prototype implemented and locally smoke-tested; NOT INTEGRATED / NOT DEPLOYABLE**.

## Evidence and boundaries

The AQP source-pinned large offline test on `audit/production-framework` completed 252,000 synthetic GF/status opportunities and 2,400 synthetic submissions across standard111, delta111, delta221, historical delta441_backup, with zero failures of the two previously implemented guards. These numbers concern *isolated extracted methods with a fake scheduler*, not live Condor or numerical integration.

The same test correctly flags:
- `EMPTY_EXIT0_QUEUE_REPLY_NOT_INDEPENDENTLY_RECONCILED`
- `EMPTY_SINGLE_JOB_REPLY_NOT_INDEPENDENTLY_RECONCILED`
- `NO_DURABLE_ACK_RECONCILIATION_OR_IDEMPOTENT_RESTART`
- `PARTIAL_EXIT0_QUEUE_RESPONSE_CAN_TRIGGER_MISSING_JOB_HANDLING`

The original ATLAS MG5 3.5.11 `CondorCluster.submit` / `submit2` and `control` / `control_one_job` are the target. On standard111, the actual imported file was confirmed to be `PROCNLO_*/bin/internal/cluster.py`, not the central CVMFS copy. This file may contain local timing instrumentation. The previous patched copies remain **isolated**. Do not edit existing Wenu process trees or current gridpacks.

Historical forensic evidence: 188 distinct GF/stage logs contained multiple submit IDs; all 11 examined MINT1 bad-real GF pairs showed the second submit precede the first successful termination, with a later failing second execution. This supports re-entry but **does not determine which controller error initiated the second submission**.

## Required mechanism

### 1. Stable submission identity

Before **each scheduler submission**, persist a unique request token bound to *exactly* one `(process_identity, stage, GF, attempt)`, including exact source/cards identity where available. Use a durable, atomic write-once intent record in a shared, AF-approved filesystem. A mere in-memory Python dictionary is insufficient.

Inject that request token into the actual `condor_submit` job ClassAd as a custom attribute (e.g. `+AQPRequestId = "..."`) so both `condor_q` and `condor_history` can independently recover the original scheduler job. Verify the site scheduler exposes and preserves the attribute, including in history, before relying on it.

Enforce one unresolved submission intent per `(process, stage, GF)`. Re-entering the same stage under a fresh controller **must not issue a new condor_submit** while an intent is unresolved, even when local outputs are absent.

### 2. Acknowledgment and controller crash

Persist `INTENT` **before** invoking `condor_submit`. Persist `ACKNOWLEDGED` only after success, a valid cluster ID, and association to the request ID. If acknowledgment is lost or the controller crashes after the scheduler accepted a job, **do not retry**. Reconcile by the durable request ID, querying active queue and history. A failed lookup does not prove the job was never accepted.

Use monotonic, auditable states such as `INTENT`, `ACKNOWLEDGED`, `RUNNING`, `TERMINAL_VERIFIED`, and `UNRESOLVED`. Never automatically delete or replace an unresolved intent. Explicit, audited operator recovery may be necessary if the scheduler has permanently lost the record.

### 3. Queue/status reconciliation

An exit-0 empty `condor_q` reply is **not an error by itself**; terminated jobs normally leave the active queue. A partial response can similarly omit a tracked job.

When a previously tracked request ID is absent from the aggregate query, independently query queue and history **for that request ID** before changing job state or invoking `check_termination`. Query transport errors, malformed output, inconsistent metadata, or incomplete/expired history must yield **UNKNOWN/BLOCKED**, not assumed completion. Do not equate `condor_history` job exit status 0 with valid GF integration artifacts.

Only mark a GF/stage complete when the matching job has independently verified terminal success **and** required outputs are present, intact, and linked to the same request ID. A file existing or being nonempty alone does not establish integrity.

### 4. Safe recovery and output identity

Record source/card hashes, output manifest, job identity, and stage in the completion record. Missing or mismatched manifest -> stop; do not overwrite GF output. Prevent multiple *writers* even if two scheduler jobs exist. If old jobs are found, reconcile them; do not kill or resubmit automatically without a reviewed policy.

Do not patch standard111/delta111/delta221 historical processes, historical delta441_backup, or active delta441 as part of development. The active delta441 process is not covered by the historical backup's pinned hash.

## Implementation order and non-negotiable acceptance

1. Implement a **standalone, isolated** persistent request/ledger module with atomic intent creation and crash/restart semantics. Prove it refuses conflicting attempts (including concurrent processes). No production mutation.
2. Integrate the ledger with the *exact pinned* `CondorCluster.submit` / `submit2` source via a fail-closed, source-verified patcher. Assert the ClassAd token is in the submitted text for both methods.
3. Integrate queue/history reconciliation into `control` / `control_one_job`. Verify normal successful completion and real output-consumption behavior, not just negative tests.
4. Extend **one comprehensive stress campaign**: four configurations, 300 simulated GF identities each, 210 polling rounds, late scheduler disruptions, malformed/partial/empty responses, ambiguous ACK, controller crash at each durable transition, duplicate submission attempts, simultaneous controllers, wrong job-ID replies, output-missing/partial/corrupt cases, and replay of the observed historical 0->2 reentry sequence.
5. The campaign must assert **zero duplicate submit attempts for an unresolved key, zero ambiguous success transitions, verified normal completion, and restart safety**. A zero-failure count for *only the old methods* is not sufficient.
6. On a fresh disposable process, verify the actual `internal.cluster` import path and all site-specific ClassAd/history behavior. Run **one substantial live, non-physics Condor canary** with deliberate fault injection and an audit of every submitted ID. Do not create a multi-day physics run as the first live acceptance.
7. Only after successful live acceptance and explicit review: create a shared version-pinned installer invoked **after `new_process()` and before `generate()`** in future JOs. Keep the core Wenu physics settings unchanged. Do not modify CVMFS.

## Safety and result labels

The existing large stress result is **OLD_GUARDS_PASS / PRODUCTION_BLOCKED**, not production approval. No implementation that merely converts all empty exit-0 status responses into errors should be called complete. Any feature that cannot reconcile a stale/unavailable job safely must fail closed and leave the GF unchanged. No automatic retries of ambiguous submissions.

A standalone prototype, `scripts/aqp_condor_intent_ledger.py`, now implements write-once GF/stage intent claims using O_EXCL and fsync, and a **pure, model-only** reconciliation decision function. A limited local smoke test (including concurrent claim contention, confirmed terminal decision, and unreliable scheduler refusal) passed. This does **not** implement the actual MadGraph submission hook, persistent scheduler ClassAd injection, real `condor_q`/`condor_history` queries, authoritative output verification, or lifecycle restarts.

The existing single large stress runner `scripts/aqp_condor_large_stress.py` now includes this independent ledger model for all four historical configurations, alongside the original extracted-method checks. It must continue to report **PRODUCTION_READINESS BLOCKED**, including `DURABLE_INTENT_MODEL_NOT_INTEGRATED_WITH_MADGRAPH_OR_HTCONDOR`. Use a new JSON report path for each attempt: the runner refuses overwrite.

**Remaining work:** source-pinned integration into `CondorCluster.submit`/`submit2` and `control`/`control_one_job`, real scheduler reconciliation, artifact provenance, full controller crash testing, and a disposable live canary. The prototype is **not** a safe production drop-in; no existing Wenu generated process has been modified.

## 2026-10-31: isolated, source-pinned submit-fence candidate

New **NON-DEPLOYED** components on `audit/production-framework`:

- `scripts/aqp_condor_submission_guard.py`: requires `AQP_CONDOR_INTENT_ROOT`, reserves each recognized `ajob1` (channel, stage 0/1, GF) in the write-once ledger immediately before the `condor_submit` subprocess, and records a write-once acknowledgment on success. Unknown job types, stages, working directories and missing ledger roots fail closed. The ledger has no automatic unlocking/reset mechanism.
- `scripts/aqp_prepare_condor_submission_fence.py`: reconstructs the exact source-pinned combined candidate for four historical Wenu configurations; inserts a `+AQPRequestId` ClassAd attribute into **both** `submit` and `submit2`; bundles helper modules into isolated output directories. Does not install a patch into the generated processes, CVMFS, or any JO.
- `tests/test_aqp_condor_submission_fence.py`: synthetic backend-method regression suite covering both submission paths, normal acknowledgments, lost ACK, duplicate refusal, unrecognized stage, and failure to configure the ledger.

The first local synthetic fixture tests passed (11/11) using an AST-patched representative class, fake `condor_submit`, and real filesystem writes. This is **not** a test on the exact installed ATLAS source, nor a test that the pilot scheduler preserves `AQPRequestId`.

The candidate is intentionally restrictive and presently **not safe for a real run**:
1. It refuses any non-`ajob1` submission; other MG subprocess types and actual `ajob1` argument layouts must be audited.
2. Once a GF/stage has an intent, it cannot be resubmitted. This prevents accidental duplicate execution but also blocks genuine recovery and repeated integrations unless a reviewed, durable reconciliation process is added.
3. Acknowledged jobs have no lifecycle state reconciliation, verified output manifest or audited controller-restart path yet.
4. The normal `CondorCluster.control`, `control_one_job` and `check_termination` methods are **not** made recovery-safe by this submission fence. The four prior large-stress blockers remain.
5. The ledger's storage atomicity and filesystem semantics must be tested on the actual AF shared filesystem before trusting them for production.
6. Historical `delta441_backup` is not the validated *active* Delta441 process.

The appropriate next validation is to run `python3 -m unittest discover -s tests -p 'test_aqp_condor_submission_fence.py' -v` on the AF and create **isolated** candidates (not installed), then inspect the exact source diff and import environment. Even if these pass, do **not** run physics or enable this patch in a JO. The next engineering requirement is request-ID-based queue/history reconciliation and a genuine output-integrity contract.


## 2026-10-31 second implementation increment: isolated history-gated candidate

This branch now also includes:

- `scripts/aqp_condor_completion_guard.py`: verifies a queue/history record against a previously persisted `AQPRequestId` and the durable acknowledged cluster ID. Missing, malformed, mismatched, held, nonzero-exit or unavailable scheduler evidence fails closed. A job that is still queue-visible with `JobStatus=4` is treated as **outstanding** until terminal history is available.
- `scripts/aqp_prepare_condor_status_gate.py`: inserts the history gate before `CondorCluster.control` calls `check_termination` for a missing job; additionally handles queue-visible `C` status so it cannot count as finished prematurely, and guards missing/`C` `control_one_job` responses.
- `scripts/aqp_prepare_condor_submission_fence.py` now composes source-pinned combined status/submit fixes with the durable submission fence **and** history gate, outputting importable, isolated `internal/` packages with all three companions.
- `tests/test_aqp_condor_completion_guard.py` covers fake queue/history responses (no real scheduler).
- `scripts/aqp_condor_full_recovery_campaign.py` orchestrates the two new regression suites, verifies the four source-pinned isolated candidates, and runs the existing large `300 × 210 × 4` offline stress in **one invocation**. Its full-scale stress section continues to exercise extracted old-patch methods and an independent ledger model. It does **not** constitute 252,000 invocations of the newly integrated history-gated candidate.

Local synthetic tests were executed against representative patched method fixtures (submission guard 11/11 and history gate 7/7, separately); these results **do not** establish compatibility with the exact ATLAS 3.5.11 bundled source, actual Condor ClassAd/history behavior, or true GF output validity.

### One AF offline command (DO NOT install candidate or run physics)

```bash
cd ~/AQP/aqp-production-audit
git status --short
git pull --ff-only origin audit/production-framework

MG=/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt
python3 scripts/aqp_condor_full_recovery_campaign.py \
  --base "$HOME/AQP/Wjets/WENU" \
  --central "$MG/madgraph/various/cluster.py" \
  --channels 300 --rounds 210 \
  --report .aqp_staged/condor_recovery_full_20261031.json
echo "Exit status: $?"
```

Exit code 2 means the *offline* checks completed but **PRODUCTION_READINESS BLOCKED** is retained. Exit 1 means test/candidate generation failed. The four historical Wenu process trees, CVMFS and JOs are untouched.

### Remaining non-negotiable release blockers

- The actual process imports and HTCondor ClassAd/history query syntax need validation on a disposable AF test process. A source-pinned AST candidate is not itself evidence that the loaded code has been executed.
- Required GF output integrity remains the old `check_termination` file-presence behavior. A durable manifest with matching job provenance and content checks is still missing. Consequently, scheduler success does **not** mean grid integrity.
- The ledger is intentionally write-once with no safe retry release policy. Legitimate resubmission after a controller restart or a failed job would remain blocked. A reviewed, crash-safe reconciliation/terminal lifecycle is not yet implemented.
- The history guard queries the exact acknowledged cluster ID; it does not yet search all jobs by request token to prove no *other* scheduler ID was accepted during an ambiguous ACK. The live canary must test that.
- Full normal and faulted controller lifecycle (output publication, mixed stage transitions, exceptions and retries) has **not** been tested end-to-end against a real scheduler. The large synthetic runner cannot replace this.
- **No production deployment and no JO patch installation are authorized by these offline results.**

## 2026-10-31 candidate-generation failure: nested import anchor

AF report: submission-fence 11/11 and completion-guard 10/10 synthetic regression tests passed, but actual source-pinned candidate construction stopped with `ValueError: Expected exactly one import sys` in `aqp_prepare_condor_submission_fence.py`.

Root cause was confirmed in upstream MG5 3.5.11: its `cluster.py` contains **two** `import sys` statements, one at file scope and one nested in another backend class. Both candidate-injection helpers incorrectly searched all lines rather than the AST module-level import.

Both `scripts/aqp_prepare_condor_submission_fence.py` and `scripts/aqp_prepare_condor_status_gate.py` now locate a *single top-level `ast.Import` importing sys* and require its exact source line. Additional regression cases cover a nested `import sys` and reject a source with only a nested import.

**This correction has been committed but not yet rerun on the actual AF.** The prior failed report path exists, so use a NEW report name, e.g.:

```bash
cd ~/AQP/aqp-production-audit
git pull --ff-only origin audit/production-framework
MG=/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt
python3 scripts/aqp_condor_full_recovery_campaign.py \
  --base "$HOME/AQP/Wjets/WENU" \
  --central "$MG/madgraph/various/cluster.py" \
  --channels 300 --rounds 210 \
  --report .aqp_staged/condor_recovery_full_20261031_v2.json
echo "Exit code: $?"
```

**Do not install these candidates into the historical processes or invoke physics generation.**

## 2026-10-31 additional controller-state regression and integrated-method stress

The previous candidate could count a **queue-visible `JobStatus=4`** as a completed GF in `CondorCluster.control()`: the first attempt guarded the job identity but allowed the `finished = submitted - (idle + running + failed)` accounting to increment without passing through `check_termination`. This is not acceptable. The candidate now explicitly keeps every queue-visible `C` job counted as **outstanding** until it disappears from the active queue and is independently reconciled. `tests/test_aqp_condor_completion_guard.py` gained a concrete controller-counter regression (running=1, finished=0 rather than running=0, finished=1).

`scripts/aqp_condor_combined_control_stress.py` now exercises the **actual newly composed** `CondorCluster.control` and `control_one_job` method AST from each source-pinned isolated candidate with a fake `condor_q`. It tests visible running jobs, queue-visible C, successful terminal reconciliation, missing/unresolved jobs, malformed outputs, empty replies and failed queue queries. It injects an identity-checking callback rather than running real `condor_history`; that callback's parser has separate unit tests. The full existing offline campaign now runs this test across all four configurations with the same `--channels` and `--rounds` dimensions before the older method/ledger model stress.

This increment is committed but has **not yet been run on the AF**. The campaign MUST remain `PRODUCTION_READINESS BLOCKED`, even if all method-level stress checks pass. There is still no real-process import, scheduler history/ACK reconciliation against an actual schedd, validated GF output manifest, safe release of a durable intent after a legitimate failure, or controller crash/restart acceptance.

Use a fresh output filename such as `.aqp_staged/condor_recovery_full_20261031_v3.json`. Never overwrite the previous v2 report. Do not copy candidates into the historical process trees.
