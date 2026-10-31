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
