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

## 2026-10-31: v3 offline result and fail-closed GF output gate

**User-run v3 acceptance:** 13/13 submission-fence, 13/13 history-guard tests, all four pinned candidate constructions, and all four combined-candidate status method tests PASS. The independent legacy stress recorded 252,000 simulated status opportunities, 2,400 synthetic submissions, 1,200 blocked duplicate intents, and 252,000 ledger model decisions with no guard failures. **This is offline evidence, not live Condor or GF output evidence.**

New candidate-only, non-production safeguards:

- `scripts/aqp_condor_output_manifest.py`: an isolated write-once publication and independent verification contract. It records the request ID, cluster ID, process/stage/GF identity, a caller-supplied source/cards fingerprint, required relative output names, sizes and SHA256 digests. Publishing links a fully synced staging file to a unique final name; verification independently rereads and rehashes every required file.
- `scripts/aqp_condor_output_guard.py`: refuses completion unless the existing scheduler history gate returns TERMINATED, a unique acknowledged job is linked to an intent, a trusted `AQP_CONDOR_INPUT_SHA256` is present, and the exact required GF outputs verify against the manifest.
- `scripts/aqp_prepare_condor_output_gate.py`: inserts a fail-closed `CondorCluster.check_termination()` override into the source-pinned, isolated backend; the original base handler is called **only after** manifest verification.
- `tests/test_aqp_condor_output_manifest.py` and `tests/test_aqp_condor_output_guard.py`: positive/negative tests for corrupted/empty/missing results, wrong job/input/stage, duplicate publication, traversal, symlinks and the completion-method override.
- The single `scripts/aqp_condor_full_recovery_campaign.py` now includes both suites, requires the manifest/guard companions in each generated isolated candidate, and confirms the override insertion.

**Do not deploy**: these checks are deliberately *nonfunctional for real production* until a real, verified GF worker publishes the manifest, a trusted source/cards hash is bound to each submission intent, and the actual MG `required_output` path contract is audited. The `AQP_CONDOR_INPUT_SHA256` environment variable is currently only a simulated trusted input, **not** independently authenticated or tied to a source/card snapshot. A user-editable JSON manifest cannot alone attest to physics validity. No safe release/retry policy is implemented. Moreover, the old five blockers printed by the independent legacy stress still describe its older model; they should not be misread as direct measured failures of the new candidate.

### Next one-command AF offline campaign

```bash
cd ~/AQP/aqp-production-audit
git pull --ff-only origin audit/production-framework
MG=/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt
python3 scripts/aqp_condor_full_recovery_campaign.py \
  --base "$HOME/AQP/Wjets/WENU" \
  --central "$MG/madgraph/various/cluster.py" \
  --channels 300 --rounds 210 \
  --report .aqp_staged/condor_recovery_full_20261031_v4.json
echo "Exit code: $?"
```

A successful offline run is still exit code 2 and `PRODUCTION_READINESS BLOCKED`. The next engineering step is a worker-side provenance/manifest publisher on a disposable non-physics process, followed by real schedd query/history semantics and crash-recovery validation. Do not patch existing processes or JOs.

## 2026-11-01: v4 passed; inspect generated `ajob1` worker before adding publication

The user ran **v4** of `scripts/aqp_condor_full_recovery_campaign.py` on the AF. Results: 13/13 submission-fence, 13/13 completion-guard, 15/15 manifest, and 12/12 output-gate regressions passed (**53/53**); four source-pinned candidates and four combined-controller status runs passed. The independent older stress logged 252,000 synthetic status opportunities, 2,400 simulated submissions, 1,200 permanently blocked duplicate claims, zero guard failures. The campaign intentionally returned code **2 / PRODUCTION_READINESS BLOCKED**. No live worker was run.

Source review of MG5_aMC 3.5.11 upstream `Template/NLO/SubProcesses/ajob_template` shows that generated `ajob1` receives four positional arguments, with the fourth the integration step. It runs `madevent_mintMC` or `madevent_mintFO`, captures executable return status, copies `log.txt` to `log_MINT$integration_step.txt` and `res.dat` to `res_$integration_step.dat`, then `exit $status`. The result-copy exit is **not** separately enforced by that template. A successful job exit therefore does not independently guarantee the stage-copy artifact is complete, and any manifest publisher must inspect actual outputs rather than trust job exit alone.

New read-only audit `scripts/aqp_audit_generated_ajob1_worker.py`, with tests `tests/test_aqp_audit_generated_ajob1_worker.py`, inspects the existing Wenu `P*/ajob1` scripts and stage-specific output files. It is included in the one-command comprehensive offline runner. Its output is observational and **not** a physics-validity or production-approval certificate. The script does not run MadGraph or Condor or modify production.

**Before any worker-side patch:** review the AF audit's worker pattern counts and observed stage output examples; establish the actual `required_output` relative paths that `Cluster.check_termination` receives, and the worker's environment / Condor ID / request ID transfer. The worker must publish the manifest *only after* an independently verified result copy and validated exit. The controller must bind the worker-published result to the durable intent and frozen physics-input fingerprint. Then prove crash/restart handling, live schedd ClassAd/history semantics, and a disposable non-physics job chain. No current JO should install the candidate.

One combined **v5** command (new report path; v4 preserved):

```bash
cd ~/AQP/aqp-production-audit
git pull --ff-only origin audit/production-framework
MG=/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt
python3 scripts/aqp_condor_full_recovery_campaign.py \
  --base "$HOME/AQP/Wjets/WENU" \
  --central "$MG/madgraph/various/cluster.py" \
  --channels 300 --rounds 210 \
  --report .aqp_staged/condor_recovery_full_20261101_v5.json
echo "Exit code: $?"
```

**Expected passing outcome remains exit 2 / BLOCKED.** The novel useful output is the `WORKER_AUDIT` lines and the embedded `generated_worker_contract_audit` JSON section. Do not replay expensive physics or replace process-local backends for this audit.

## 2026-11-01: v5 PASS, but worker-group identity/output mapping requires correction

User-run v5: all **61/61** regression tests, four candidate builds, four combined-candidate status tests PASS; 252,000 synthetic status opportunities and 2,400 simulated submissions, with zero guard failures. Read-only scan found **82 P*/ajob1 scripts per historical configuration**; 300 observed `res_0.dat`, `res_1.dat`, `log_MINT0.txt`, `log_MINT1.txt` files each. No run was submitted; **production remained blocked**.

### Corrected semantic error: one ajob1 submission is not one GF

Review of upstream MG5_aMC 3.5.11 `Template/NLO/SubProcesses/ajob_template` and `aMCatNLOCmd.run_all_jobs` confirms the actual argument order **(channel, run_mode, runnumber/split, integration_step)**. The previous `aqp_condor_submission_guard.reserve` called argument[0] the `gf` field and used only channel and stage for the ledger key. That would wrongly collapse distinct valid submissions of different modes or run numbers into the same reservation. Prior "1,200 duplicate intents blocked" counts were derived from the simplified mock; they are **not proof of correct deduplication across actual aMC worker groups**.

`scripts/aqp_condor_submission_guard.py` now includes the full 4-field worker identity in the ledger key (`ajob1:<channel>:<run_mode>:<runnumber>`, stage `MINT<integration_step>`). The legacy ledger JSON field `gf` currently stores a **whole worker-group key**, *not* a single GF directory. Two new regression tests check independent modes/run numbers and one checks blocking identical four-argument resubmissions. The output-gate fixture was aligned with the corrected identity. This remains candidate-only. The old ledger's write-once semantics still intentionally block legitimate repeat runs in the same root until independently reconciled.

### Required outputs are controller-dependent

Upstream `aMCatNLOCmd.getIO_ajob` constructs `required_output` relative to the **channel cwd**. In the MINTMC `F/B` branch, it appends stage-specific `G.../log_MINT<step>.txt` and, for steps 0 and 1, `G.../results.dat`. It does not add `G.../res_<step>.dat` to that list in the same way as the fixed-order branch. This must be checked against the actual installed ATLAS fork and generated process before any manifest publication. A worker script may produce more result files than the controller lists as required; do **not** substitute a generic `res_1.dat` list.

Upstream `store_input` records `self.retry_args[id]` only when `self.nb_retry > 0`; the prototype output-gated `check_termination` override currently depends on that state. Thus a valid submission using `cluster_nb_retry = 0` could lack `retry_args`, and the prototype would fail closed. **This is an outstanding integration defect, not a reason to enable retries or loosen the output checks.**

New `scripts/aqp_audit_ajob_controller_contract.py` extracts source-verified (AST) `run_all_jobs`, `getIO_ajob`, `store_input` and `Cluster.check_termination` from the user's installed ATLAS MG5 files. It is **read-only**, stores relevant source snippets and flags in JSON, and never runs MadGraph or Condor. `tests/test_aqp_audit_ajob_controller_contract.py` covers the audit on synthetic source. It now runs within the one comprehensive campaign before candidate construction. The output is source evidence, not an approved worker/manifest contract.

**Remaining release gates:** Bind input/card fingerprints to the immutable submission intent; correct retry-independent provenance; determine the exact per-worker group of GF outputs for the generated Wenu mode; publish and independently verify all required artifacts only after successful copy; reconcile lost acknowledgments by request-ID across scheduler queue and history; prove start/restart and legitimate retry; then run one disposable non-physics live HTCondor canary. Existing integrations, gridpacks and JOs remain unchanged.

### Next source audit and unified offline rerun (v6, new report filename)

```bash
cd ~/AQP/aqp-production-audit
git pull --ff-only origin audit/production-framework
MG=/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt
python3 scripts/aqp_condor_full_recovery_campaign.py \
  --base "$HOME/AQP/Wjets/WENU" \
  --central "$MG/madgraph/various/cluster.py" \
  --channels 300 --rounds 210 \
  --report .aqp_staged/condor_recovery_full_20261101_v6.json
echo "Exit code: $?"
```

The campaign remains **BLOCKED by design**. New useful output: `AJOB_SOURCE_FLAG` lines, installed ATLAS source SHA256s and exact required-output/retry snippets in the JSON.

## 2026-11-01 v6 PASS: retry-independent submitted-job provenance

**User-run v6:** all **71/71** offline regression tests PASS, six installed-source flags YES, four exact source-pinned candidates PASS, four combined candidate control-method tests PASS, legacy stress 252,000 synthetic status opportunities and 2,400 synthetic submissions with zero old-guard failures, **exit 2 / BLOCKED**. Installed ATLAS hashes:
- `madgraph/interface/amcatnlo_run_interface.py`: `fff31c41ef5d0bdcac7a02efd7d5f8f3d2d5f416ff6da6719a6315ca8efea871`
- `madgraph/various/cluster.py`: `feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe`.

The `store_input()` decorator in the installed version records `self.retry_args` only when `self.nb_retry > 0`. Therefore using `retry_args` as the **only** durable output provenance would break completion with `cluster_nb_retry=0`.

New, **non-deployed** changes on the audit branch:

1. `aqp_condor_submission_guard.reserve(..., required_output)` verifies nonempty, unique, safe relative output paths *before* creating an intent or submitting a job; the actual list is supplied from MadGraph's `submit`/`submit2` arguments.
2. `aqp_condor_submission_guard.acknowledge(request_id, cluster_id, cwd, required_output)` stores an immutable version-2 ACK containing the exact normalized working directory and `getIO_ajob`-derived `required_output`. The patcher writes this ACK **before** incrementing `self.submitted` or appending `self.submitted_ids`; a failed acknowledgment leaves the submission intent unresolved without claiming the job is tracked.
3. `aqp_condor_output_guard.require_verified(job_id, retry=None)` recovers the required output list from the durable ACK even when `retry_args` is absent. When `retry_args` exists, its cwd/output list must match the ACK exactly; discrepancies fail closed. Scheduler-ID, frozen-input and worker-manifest verification remain mandatory.
4. `aqp_prepare_condor_output_gate.py` no longer raises immediately when no `retry_args` record exists. It passes the optional record to the output verifier before delegating to MadGraph's original `Cluster.check_termination`.
5. Added regressions for **`cluster_nb_retry=0` with valid/missing output manifest**, wrong/missing output requirements, and disk failure between `condor_submit` and the ACK, plus assertions that the ACK precedes in-memory tracking.

**Current limitation:** The ACK is created only after a successful scheduler reply. A lost acknowledgment or controller crash before the ACK remains UNRESOLVED and requires request-ID lookup across scheduler queue/history, which is not implemented in this candidate. The input-card SHA remains an external environment value, not yet frozen in the intent. A real `ajob1` worker does not publish the required authenticated manifest. This increment resolves an important *source-level dependency*, not the whole recovery/retry problem.

### Next offline validation (v7; new report path)

```bash
cd ~/AQP/aqp-production-audit
git pull --ff-only origin audit/production-framework
MG=/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt
python3 scripts/aqp_condor_full_recovery_campaign.py \
  --base "$HOME/AQP/Wjets/WENU" \
  --central "$MG/madgraph/various/cluster.py" \
  --channels 300 --rounds 210 \
  --report .aqp_staged/condor_recovery_full_20261101_v7.json
echo "Exit code: $?"
```

The updated six synthetic suites currently contain **80** `test_*` functions, not yet executed on AF. If all pass, the campaign should still exit 2 and print `PRODUCTION_READINESS BLOCKED`. Preserve all previous v1-v6 reports and all historical process trees. The next *meaningful* development milestone is a disposable worker-side manifest protocol plus cross-restart request-ID reconciliation, **not** enabling the candidate in a JO.

## 2026-11-01 v7 PASS and v8 restart-specific candidate work

**User-run v7:** 21/21 submission-fence, 13/13 completion, 15/15 output-manifest, 16/16 output-gate, 8/8 ajob worker and 7/7 controller-contract regressions PASS (**80/80**). Four historical source-pinned candidates and four combined status-method campaigns passed. Six installed-source flags YES with unchanged pinned SHA256s, and the independent legacy stress again completed 252,000 status opportunities without observed old-guard failures. The run explicitly returned `PRODUCTION_READINESS BLOCKED` / exit 2.

Additional inspection of upstream MG5 3.5.11 `Cluster.check_termination` confirms that if `job_id` is absent from `retry_args`, its base implementation returns True **without removing the ID from `submitted_ids`**. The v7 override used a durable output-context verifier but delegated to that base method regardless. This can leave a verified, finished no-retry job in the active controller ID set.

**v8 isolated candidate fixes (not yet run on AF):**

1. `aqp_prepare_condor_output_gate.py` retires a successfully scheduler-and-manifest-verified job directly from `submitted_ids` when no retry context is available. It refuses to modify an untracked job or a packet-associated job without the packet bookkeeping. When a retry record exists, the original MG base method still handles the job.
2. `aqp_condor_intent_ledger.claim(..., context=...)` now atomically persists the exact four worker arguments, normalized cwd and `getIO_ajob` required-output list **before** calling `condor_submit`. Existing model-only five-argument claims remain supported for backward test compatibility but are not recoverable after lost ACK.
3. `aqp_condor_submission_guard.reserve` passes that full pre-submit context to the ledger. A scheduler-accepted job whose `condor_submit` reply was lost now leaves enough frozen worker context to reconstruct an acknowledgment *if its scheduler ID can be uniquely reidentified*.
4. `aqp_condor_missing_ack_recovery.py` is a **standalone, opt-in, non-automated** helper. It queries active queue and history with `AQPRequestId` as a scheduler ClassAd constraint. Only one uniquely matching job in exactly one scheduler source can be acknowledged, and only with explicit `commit=True`. It NEVER submits, retries, cancels, deletes or proves GF results. Missing, duplicate, conflicted, malformed or failed scheduler responses remain blocked. Its command/attribute syntax has **not** been tested on UChicago HTCondor.
5. `tests/test_aqp_condor_missing_ack_recovery.py` adds synthetic queue/history, duplicate identity, restart, malformed response and lost ACK tests. `tests/test_aqp_condor_output_guard.py` additionally checks completed-ID retirement only after successful verification and refusal of packet/untracked cases. `tests/test_aqp_condor_submission_fence.py` now verifies that the pre-submit intent retains the original required outputs when the ACK is lost.

**Current limitations:** The standalone recovery helper is packaged with the isolated candidate but is **not invoked by MadGraph**; real controller restart reattachment and state restoration do not yet exist. New job identity is not passed to the real `ajob1` process, so no actual authenticated completion manifest can be emitted. The physics-input/card digest is not independently frozen in the intent. No automatic safe retry/release policy or real scheduler tests are implemented. A correctly blocked state does not mean the integration can continue; the policy must be designed around durable terminal lifecycle transitions. The historical delta441_backup pin is not a pin of active delta441.

The updated single offline campaign contains **98 synthetic tests**. All v8 changes are committed to `audit/production-framework` but **have not yet been validated on AF**.

```bash
cd ~/AQP/aqp-production-audit
git pull --ff-only origin audit/production-framework
MG=/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt
python3 scripts/aqp_condor_full_recovery_campaign.py \
  --base "$HOME/AQP/Wjets/WENU" \
  --central "$MG/madgraph/various/cluster.py" \
  --channels 300 --rounds 210 \
  --report .aqp_staged/condor_recovery_full_20261101_v8.json
echo "Exit code: $?"
```

No deployment approval is implied by a PASS; successful offline campaign exit remains **2 / BLOCKED**. Do not modify Wenu process-local source, CVMFS, or gridpacks.
