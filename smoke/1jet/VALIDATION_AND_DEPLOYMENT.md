# AQP minimal Condor patch — validated scope and deployment gates

**Status (2026-11-01): v3 Condor integration/generation and 16/16 automatic reweight completions PASS; full Athena transform remains OPEN because optional systematics or output-weight checks failed. Current smoke JO intentionally disables those extras; production approval remains OPEN.**

This document applies to the `aalida0/AQP` **experimental** smoke-test branch.
The frozen, two-file patch and tests live separately in
`validated/condor-mint0-20261101` (copied from `fix/minimal-condor`).
Do not merge the smoke-test helpers or generated process files into `main`.

## What was actually validated

| Validation | Observed result |
| --- | --- |
| Python unit/fault-injection tests | 21/21 PASS on UChicago AF |
| Source-pinned candidate output | SHA256 `2286e475b32323f1e391fb8e64af06fa8e41531abccd4d2c701b7746a22cc5bd` |
| Synthetic `submit2()` worker | HTCondor 4062219.0 PASS |
| Worker exits 17 | HTCondor 4062220.0: rejected, guard retained |
| Successful job with missing output | HTCondor 4062221.0: rejected, guard retained |
| Real FxFx 1-jet `ajob1` MINT0 | HTCondor 4062514.0 PASS; `GF1.0/log_MINT0.txt` and `GF1.0/results.dat` verified |
| Two real MINT0 jobs through one controller | HTCondor 4062520.0 and 4062521.0 PASS; controller (2,0,0,0) TRACKED 2 -> (0,0,2,0) TRACKED 0; `TWO_REAL_AJOB1_PASS` |
| Real MINT0->MINT1->MINT2 stage transitions | 56+56+16 workers completed; transitions observed in 2026-11-01 end-to-end attempt |
| Complete Gen_tf FxFx test including postprocessing | **NOT YET PASS**: v2 failed on zero-byte summary checks; v3 fixed live 16/16 reweight completion and produced 20-event LHE, but then failed in `systematics.py` on zero-weight-sum percent calculation. |

A separate 56-job attempt (4062447–4062502) was accepted by HTCondor but
all jobs held with `HoldReasonCode=14, SubCode=2` because their `Initialdir`
was under **node-local `login03:/scratch`**, inaccessible to scheduler
`head04`. They were later removed with `condor_rm`; those holds do not
demonstrate integration correctness.

## End-to-end attempt (2026-11-01): finalization failure, root cause pending

Isolated `/home/aalida/AQP/condor-smoke/MG1jet-smoke.sviBub` run:
MINT0 56/56 (3m04s), upper envelope MINT1 56/56 (2m36s),
MINT2 event generation 16/16 (49s). Total **128 integration/event
workers**. MadGraph then printed `Doing reweight` and `Start waiting
for update`. Condor history showed reweight jobs with `JobStatus=4`
and `ExitCode=0`; inspected subprocesses contained `events.lhe.rwgt`.
The queue was empty, submission guards numbered 0, but `Gen_tf.py`
eventually exited **65** with `RuntimeError: Error detected in
MadGraphControl process`. No `smoke_lhe_events.tar.gz` exists.

**Root-cause candidate identified from MG 3.5.11 source:** the reweighting
`submit2` contract includes `scale_pdf_dependence.dat`. With
`reweight_scale=False` and `reweight_pdf=False`, that file may exist
but have zero bytes; the v2 patch's unconditional nonempty check rejects
the finished worker. Upstream `misc.multiple_try` contains a bare
`raise` after retries, which masks the underlying failure with
`RuntimeError: No active exception to reraise`. This is a source-based
diagnosis, pending exact reproduction with the patched runner.

An **experimental v3** change exists only on this smoke-test branch:
it accepts an empty `scale_pdf_dependence.dat` **only** for reweight
jobs with a readable unambiguous run card disabling both scale and PDF
variations, still requires the file's existence, and always requires
nonempty `.rwgt` and reweight logs. It also removes the masking retry
decorators from the Condor monitoring overrides. Six new regression
tests were added. **Tests have not yet been executed on AF**; neither
`validated/condor-mint0-20261101` nor production `main` was changed.

**Do not infer the Condor patch is fully validated or that the reweight
files are correct.** The shared log excerpt contained the *tail* of the
MadGraph error diagnostics (mostly a run-card parameter dump), not
the underlying exception. Extract the **first** MadGraph exception
from `generation.log` or
`PROCNLO_loop_sm-no_b_mass_0/run_01_tag_1_debug.log` before patching or
rerunning. Do not erase the run or reuse its submission guards.


## Experimental v3: replay completion of the already-finished reweight jobs

Candidate generated on AF:
`/home/aalida/AQP/aqp-condor-minimal/.aqp_staged/minimal_v3/cluster.py`.
Expected SHA256:
`ab60358a273531522835cd64c0f76acaca91faed1d426374ae8c04796ca4ef3c`.

This candidate is NOT installed for production, and its end-to-end
correctness is NOT established. Do not replace the v2 patch.

The file `smoke/1jet/bootstrap_v3/sitecustomize.py` uses the new pin,
leaving the original v2 bootstrap untouched. The read-only
`smoke/1jet/replay_reweight_completion.py` checks 16 archived workers
(4062653–4062668) against their original HTCondor history, files and v3
completion logic. It submits no jobs and does not rerun physics.

```bash
# Same AF host, with access to the original completed /home process
setupATLAS
asetup 23.6.63,AthGeneration
cd ~/AQP/aqp-condor-minimal
git pull --ff-only origin test/condor-fxfx-1jet-smoke

python3 -m unittest discover -s tests -p 'test_condor_minimal.py' -v
# Require all 27 tests PASS before continuing.
sha256sum .aqp_staged/minimal_v3/cluster.py
# Require the exact v3 SHA above.

export AQP_CLUSTER_CANDIDATE="$PWD/.aqp_staged/minimal_v3/cluster.py"
export PYTHONPATH="$PWD/smoke/1jet/bootstrap_v3:$(readlink -f "$MADPATH"):${PYTHONPATH:-}"
python3 -c 'import madgraph.various.cluster as c; assert hasattr(c, "_aqp_output_contract"); print("V3_PATCH_LOADED")'
python3 -m py_compile smoke/1jet/replay_reweight_completion.py
python3 smoke/1jet/replay_reweight_completion.py
```

**Regression tests (2026-11-01):** 27/27 PASS on AF (reported by user).
**LHE integrity (2026-11-01):** all 16 `events.lhe.rwgt` files ended with `</LesHouchesEvents>`; `SubProcesses/collect_events` executable absent, consistent with the premature exit before `misc.compile(['collect_events'])`.
**Native collector recovery (2026-11-01):** in an isolated copy at
`~/AQP/condor-collect/collect.Dp3LBn/PROCNLO`, updated
`SubProcesses/nevents_unweighted` to reference all 16 `.rwgt` files;
`make collect_events` succeeded (exit 0), and collector mode `2`
(`event_norm=average`) succeeded (exit 0). Collector reported
`found 16 files` and `Final event file (with 20 events) is:
allevents_0_001`; output size **133153 bytes**. Original process
left unchanged. Independent merged-LHE structure **PASS**: 133153 bytes; 20 opening and 20 closing `<event>` tags; valid `<LesHouchesEvents>`, `<init>`, and closing tag. `gzip -t` **PASS** on a separate 21 KB diagnostic `merged_events.lhe.gz`. The automatically executed Athena transform/shower remain **NOT VALIDATED**.


**Observed PASS (2026-11-01):** `ZERO_BYTE_SCALE_PDF_SUMMARIES 16`,
`V3_CONTROL_STATE (0, 0, 16, 0)`, and `REWEIGHT_REPLAY_PASS 16 workers`.
This validates source-pinned v3 reweight completion bookkeeping for all
16 archived jobs, **not** successful LHE assembly, showering, or a production
end-to-end run. Unit-test outcome must be separately confirmed; none was
included with the replay output. Do not repeat integration to obtain this proof.



## Next gate: native v3 `--reweightonly` in the isolated collector copy

MG5 3.5.11 `generate_events` supports `-r/--reweightonly`,
`-c/--cluster`, `-p/--parton`, `-f/--force`, and `-n/--name`.
The `reweightonly` path bypasses MINT0/MINT1/MINT2 and calls
`reweight_and_collect_events`; it restores `nevents_unweighted.orig`
before starting the reweight workers. The original `/home` failed run
must remain untouched.

Use **only** the existing separate collector copy:
`~/AQP/condor-collect/collect.Dp3LBn/PROCNLO`. After verifying the v3
SHA256, the 27 unit tests, the `.orig` manifest and a new
`Events/run_02` name, remove stale generated reweight results and
`allevents_0_001` **from that copy only**. With the separate v3
bootstrap first on `PYTHONPATH` and a fresh
`AQP_CONDOR_GUARD_DIR`, launch from inside the copy:

```bash
python3 bin/generate_events aMC@NLO -r -c -p -f -n run_02 \
  2>&1 | tee ../v3_reweight_only.log
```

Expected: **16 new reweight jobs**, automatic native
`collect_events`, and a new `Events/run_02/events.lhe[.gz]`.
A successful reweight-only run demonstrates MG-level automatic
finalization with v3, **not** completion of the full Athena `Gen_tf`
transform or Pythia8 FxFx shower. Verify no MINT jobs, no duplicate
submissions, nonzero events and the final LHE structural integrity;
never claim success based only on an exit code.

**Observed attempt 2026-11-01: FAILED before worker submission.**
27/27 tests passed, SHA256 v3 pin checked, v3 module loaded; native
`bin/generate_events aMC@NLO --reweightonly --cluster --parton --force --name=run_02`
immediately reported `KeyError: 'mgshowercard'` before
`Starting run`/`Doing reweight`. No `Events/run_02` exists.
Crucially, `bin/generate_events` returned exit code **0 even after
reporting this fatal error**; the wrapper printed a false
`REWEIGHT_ONLY_COMMAND_EXIT_0`. Never accept subprocess status alone:
require expected MadGraph stage markers, absence of an interrupted-command
error, and structural checks on the actual output. The cause of the
missing `mgshowercard` must be determined from
`run_02_tag_1_debug.log` before another test. This is not evidence
that the Condor v3 patch failed, as the run never submitted jobs.



## Clean v3 restart (recommended instead of repairing run_02)

The isolated `--reweightonly` test failed during MadGraph
`ask_run_configuration` because that path adds only `run_card.dat`
to the banner and still requests `mgshowercard` for `aMC@NLO`.
The original JO and regular `Gen_tf.py` path should be used for a
clean end-to-end validation rather than patching MadGraph's reweight-only
initialization. The v3 Condor code remains unchanged.

`smoke/1jet/prepare_v3.sh` is the original minimal smoke preflight
adapted only to the SHA256-pinned v3 candidate, separate
`bootstrap_v3`, and fresh `MG1jet-v3.XXXXXX` workspace.
It checks the exact Athena/MG source and creates `launch.sh`
without submitting any jobs. That launcher invokes the original
10-event JO `Gen_tf.py`, performs an error-marker scan, and requires
a valid `smoke_lhe_events.tar.gz` archive to print
`AQP_V3_GEN_TF_ARCHIVE_PASS`. The legacy v2 preflight and validated
candidate remain untouched.

```bash
setupATLAS
asetup 23.6.63,AthGeneration
cd ~/AQP/aqp-condor-minimal
git pull --ff-only origin test/condor-fxfx-1jet-smoke
bash -n smoke/1jet/prepare_v3.sh
bash smoke/1jet/prepare_v3.sh  # no jobs submitted
# Run only the 'bash /home/.../MG1jet-v3.XXXXXX/launch.sh' line printed
```

Stop on any failure; do not reuse the old `MG1jet-smoke.sviBub` or
`collect.Dp3LBn` results, submission guards, or jobs. No production
approval until the automatic end-to-end run succeeds.



## V3 clean end-to-end attempt: NLO generation/reweight/collection PASS; systematics fails (2026-11-01)

In `/home/aalida/AQP/condor-smoke/MG1jet-v3.WjxA36`, the v3
controller automatically finished MINT stages, 16 event-generation jobs
(06:18:40), 16 reweight jobs (06:19:43), and native event collection
(06:19:43). The MG5 summary reported **20 generated events** and
`4.115e+03 +/- 2.0e+01 pb`; it wrote
`PROCNLO_loop_sm-no_b_mass_0/Events/run_01/events.lhe.gz`
at 06:19:46. **The original empty-summary Condor failure is now
resolved in a real automatic workflow.**

`Gen_tf.py` then failed with exit **65** in the *independent*
`systematics` postprocessor. Its `print_cross_sections` divided by
`all_cross[0] == 0` while reporting the relative scale uncertainty
(`systematics.py:546`), raising `ZeroDivisionError`. The reason
the central event-weight sum was zero in this 20-event run has not yet
been directly verified; the generator-level cross-section summary is
distinct from this small-sample event sum. This is NOT a
Condor-completion issue and does NOT justify changing `cluster.py`.

**Next smoke run uses a complete separate JO** at
`smoke/1jet/JO_v3_nosyst/mc.MGPy8EG_Zll_FxFx_1jets_AQPsmoke.py`:
central PDF 325100 unchanged, PDF/scale variation lists empty,
`systematics_program='none'`, and **`store_rwgt_info=True`** to
continue exercising the 16 nominal reweight workers. The original JO
and production configs remain untouched. The experimental
`smoke/1jet/prepare_v3.sh` uses the new JO and creates unique
`MG1jet-v3nosyst.XXXXXX` workspaces. This is **backend smoke testing
only**; full variation weights must be restored for production
generation and for physics validation. Confirm the actual run card
contains `none = systematics_program` before accepting the result.



## V3 nominal-only: automatic Condor PASS; ATLAS expected-weights validation mismatch

The isolated `MG1jet-v3nosyst.LTC55Y` run automatically completed
16/16 event-generation workers, 16/16 reweight workers, and collected
20 NLO events (`4115 +/- 20 pb`). MadGraph's `reweight -from_cards`
and `decay_events -from_cards` steps returned without error. The run
failed after that in the ATLAS `arrange_output` step:

```
The following 0 weights have been written to the LHE file:
Checking whether the following expected weights are in LHE file: MUR1.0_MUF1.0_PDF325100
RuntimeError: Did not find expected weight MUR1.0_MUF1.0_PDF325100
```

This is a **configuration mismatch** in the deliberately nominal-only
smoke: `systematics_program=none` produces no named systematic weights,
but the ATLAS output helper still requests the central systematic weight
when `pdf_variations` exists as an empty list in the explicit
`MADGRAPH_PDFSETTING`. Confirmed by inspecting public ATLAS
`MadGraphUtils.py:get_expected_systematic_names`: the function
appends that central weight for *any* list-type `pdf_variations`, even
an empty one.

The attempted `arrange_output(..., pdf_setting={})` fix was **invalid
for AthGeneration 23.6.63**: `TypeError: arrange_output() got an
unexpected keyword argument 'pdf_setting'`. The incompatible recovery
script was deleted from this branch. Do not use the retired
`JO_v3_nosyst` setup; it is retained only as an audit trail.

### Current requested workflow: no reweighting or systematic variations

A complete replacement smoke JO is available at
`smoke/1jet/JO_v3_norw/mc.MGPy8EG_Zll_FxFx_1jets_AQPsmoke.py`.
This sets `MADGRAPH_PDFSETTING={}`; retains the nominal LHAPDF
`lhaid=325100`; explicitly disables `reweight_scale`,
`reweight_pdf`, and `store_rwgt_info`; and selects
`systematics_program=none`. It restores the **original four-argument**
`arrange_output` call supported by Athena 23.6.63.

**Correction from the older working 2-jet gridpack JO:** its
`MADGRAPH_PDFSETTING` contains `central_pdf=325100` and empty
`pdf_variations`, `alternative_pdfs`, and `scale_variations`.
The prior `MADGRAPH_PDFSETTING=None` recommendation was unnecessary and
did not follow the established ATLAS pattern. The current no-reweight JO
now uses the same complete dictionary during `modify_run_card`,
enforcing the central PDF and no systematic variations. After
`generate` it sets `MADGRAPH_PDFSETTING=None` **only before
`arrange_output`**, which prevents the 23.6.63 output helper from
looking for a nominal *named systematic weight* that was intentionally
not produced. This does not modify the physical central PDF recorded
in the LHE or run card. This arrangement-only waiver is for the tiny
nominal smoke test, not production; it retains the supported
`arrange_output(..., saveProcDir=True)` signature. The preflight previously imported `MadGraphSystematicsUtils` directly, which raised a circular-import `ImportError` before launch creation in AthGeneration 23.6.63. It now uses Python's standard-library `ast` to inspect the **complete experimental JO** for its pinned central-PDF/empty-variations fragment, output-arrangement reset, and no-reweight settings. This is a **static configuration check**, not a claim that the ATLAS systematics helper has executed. It prints `PRECHECK_NORW_STATIC_CONFIG_PASS 325100`.

A clean no-reweight smoke attempt at `MG1jet-v3norw.r1opIU` did
**not** enter integration: the intentional empty dictionary
`MADGRAPH_PDFSETTING={}` caused
`RuntimeError: No "central_pdf" configured in base fragment` from
`modify_run_card`. The fix is the older, fully populated central-PDF dictionary
with empty variation lists, followed by an arrangement-only waiver
of nonexistent named systematic-weight checks.
No systematic weights or extra reweight jobs are requested.

The separate `prepare_v3.sh` pins the unchanged v3 Condor patch,
points to the new `JO_v3_norw`, and generates a fresh
`MG1jet-v3norw.XXXXXX` directory and launch script. The preflight now executes the **installed**
`setup_pdf_and_systematic_weights(None, {...}, True)` on an isolated
configuration dictionary and requires
`PRECHECK_NORW_PDF_SETUP_PASS` before launch creation. It also checks
that the generation log contains neither `Doing reweight` nor
`Running Systematics computation`.

```bash
setupATLAS
asetup 23.6.63,AthGeneration
cd ~/AQP/aqp-condor-minimal
git pull --ff-only origin test/condor-fxfx-1jet-smoke
python3 -m py_compile smoke/1jet/JO_v3_norw/mc.MGPy8EG_Zll_FxFx_1jets_AQPsmoke.py
bash -n smoke/1jet/prepare_v3.sh
bash smoke/1jet/prepare_v3.sh # preflight only
# Then run ONLY the newly printed MG1jet-v3norw.XXXXXX/launch.sh
```

**Not production-valid physics weights:** this probe intentionally
omits PDF/scale systematic variations. The v3 reweighting completion
logic was already validated separately with 16/16 real workers; this
new no-reweight smoke checks integration, LHE arrangement and showering.


## 2026-11-01: v3 no-reweight smoke — Condor and ATLAS LHE packaging PASS; Pythia segfault

The live `MG1jet-v3norw.ndkEHd` workflow now completes **all 16/16
Condor event-generation workers**, native `Collecting events`,
20-event `Events/run_01/events.lhe.gz`, and ATLAS
`arrange_output()` (explicit `Found all required weights!` and
`All done with output arranging!` at 08:04:42). A standalone
`smoke_lhe_events.tar.gz` containing `smoke_lhe_events.events` was
created. The job-option's `MADGRAPH_PDFSETTING=None` reset, strictly
after `generate()`, avoided expecting absent named systematic weights
in this intentionally nominal-only test. No `Doing reweight` or
`Running Systematics computation` worker stage occurred; the
`reweight -from_cards` MadGraph command was printed but did not launch
reweight workers.

After LHE packaging, `Gen_tf.py` initialized Pythia8 8.315 with
`JetMatchingMadgraph` and the FxFx hook. For LHE-only production,
Athena subsequently launched **one dummy Pythia event**. During this
event, Pythia8 crashed with **signal 11** in
`Pythia8::MultipartonInteractions::pTnext`, called by
`MultipartonInteractions::pTfirst`, `PartonLevel::next`, and
`Pythia::next`. The transform reported exit **65** (after a
signal-related 129 exit). This is downstream of Condor and LHE
packaging; the C++ segfault cause is **not yet established**.
The diagnostic also printed
`PYTHIA Warning in Pythia::init: should not combine softQCD processes with hard ones`;
do not equate this warning with proven segfault causation.

**Conclusions:** v3 Condor integration/generation/LHE collection are
validated in the live no-reweight test. Separate earlier live tests
confirmed 16/16 v3 reweight-worker completion. The full Athena
transform has NOT passed, and no actual production FxFx shower sample
is established by the LHE-only dummy-event stage. Do not modify the
Condor patch or rerun MINT to debug a Pythia-only failure. Verify
`smoke_lhe_events.tar.gz` with `tar -tzf` and count LHE `<event>`
entries; isolate the Pythia crash in a separate disposable shower test.
This 20-event sample is backend-validation evidence, not production
physics.

## Exact source and runtime contract

- Use `asetup 23.6.63,AthGeneration` on AF (GCC14 / Python 3.12).
- The pinned MadGraph `cluster.py` source SHA256 is
  `feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe`.
  An Athena setup selecting `atlas15-c33bd` / GCC15 is **not compatible**
  with this candidate, even though it may also report MadGraph version 3.5.11.
- Use candidate
  `~/AQP/aqp-condor-minimal/.aqp_staged/minimal_v2/cluster.py`, with SHA256
  `2286e475b32323f1e391fb8e64af06fa8e41531abccd4d2c701b7746a22cc5bd`.
- Never modify CVMFS or an existing production `PROCNLO_*` process.
- The bootstrap in `smoke/1jet/bootstrap/sitecustomize.py` is **experimental**.
  It loads the pinned backend without editing MadGraph installation files,
  and preserves the LCG `sitecustomize`. Verify it is active before any test.
- `cluster_nb_retry=0`: ambiguous submit acknowledgements and scheduler
  anomalies are **fail-closed**; no blind retry or duplicate submission.
- Give each independent process a new, persistent, writable
  `AQP_CONDOR_GUARD_DIR`. Never delete `*.intent` to bypass an error.
  A guard is deleted only after successful history and required-output checks.

## Filesystem policy on UChicago AF

**Do not launch Condor submissions from `/data`.**
`/scratch` on the login node is a local ext4 filesystem and is not
Condor's shared submit-side `Initialdir`. Neither path can be used for
the process working directory in this deployment.

For small pilot workers, use a **fresh process directory on shared NFS
`/home`**, where the real successful canary ran. Check the **personal**
home quota, not only the `df` report for the shared NFS export.
The old full process was approximately 694 MB; the selected subprocess
31 MB; the archived transfer input set about 140 MB per worker.

For full Wenu/Zee production, a scalable, submit-host-accessible staging
solution must be chosen and tested; the approximately 10 GB personal home
space reported by the user is **not** a green light for a large FxFx gridpack.
Do not adopt HTCondor `-spool` until output retrieval and reconciliation
have been implemented and separately validated.

## Two-real-worker pilot (one controller, two jobs) — PASS 2026-11-01

**Observed:** two independent `ajob1` submissions, jobs `4062520.0` and
`4062521.0`, both completed and validated in one controller; `TWO_REAL_AJOB1_PASS`.
The polling samples showed all 2 jobs initially idle and then both completed;
we did **not** observe an intermediate one-complete/one-pending state.
No MINT1/MINT2 stages ran.

The procedure below reproduces the bounded pilot if ever needed; **do not
rerun just to repeat the same validation**.

No process generation and no 56-worker submission. Both workers are
copied from the *already compiled* original MadGraph MINT0 process in
`/scratch` using the archived input contract of job `4062447.0`.

In the existing AQP smoke worktree (on AF):

```bash
setupATLAS
asetup 23.6.63,AthGeneration
cd ~/AQP/aqp-condor-minimal
git pull --ff-only origin test/condor-fxfx-1jet-smoke

export AQP_CLUSTER_CANDIDATE="$PWD/.aqp_staged/minimal_v2/cluster.py"
export PYTHONPATH="$PWD/smoke/1jet/bootstrap:$(readlink -f "$MADPATH"):${PYTHONPATH:-}"

python3 -m py_compile smoke/1jet/one_real_worker.py
python3 -m unittest discover -s tests -p 'test_condor_minimal.py' -q
sha256sum "$MADPATH/madgraph/various/cluster.py" "$AQP_CLUSTER_CANDIDATE"

# Create TWO DIFFERENT fresh directories (does not submit anything).
python3 smoke/1jet/one_real_worker.py prepare
python3 smoke/1jet/one_real_worker.py prepare
```

Copy the two different `ONE_WORKER_STAGED` paths into `STAGE_A`
and `STAGE_B`. **Run once**:

```bash
STAGE_A="$HOME/AQP/condor-one-worker/mint0-REPLACE_A"
STAGE_B="$HOME/AQP/condor-one-worker/mint0-REPLACE_B"
python3 smoke/1jet/one_real_worker.py run "$STAGE_A" "$STAGE_B" \
  2>&1 | tee "$HOME/AQP/condor-two-worker-pilot.log"
```

The script refuses more than two workers, reuse of a stage, duplicate stage
paths and non-staged inputs. Two real `ajob1` jobs are submitted through
**one** `CondorCluster`, exercising `condor_q` with multiple IDs, partial
completion, history validation and per-worker guard cleanup.

**Required PASS:** `TWO_REAL_AJOB1_PASS`; two distinct submitted job IDs;
both `GF1.0/log_MINT0.txt` and `GF1.0/results.dat` nonempty in their
respective stage directories; both guard directories empty.

**On any error:** stop immediately. Do **not** rerun the command, release,
remove or resubmit workers blindly, or erase `jobid`/`*.intent`.
Use the saved job IDs and `condor_q`/`condor_history` to reconcile.

## Deployment decision

The two-worker pilot establishes concurrent MINT0 handling. A separate full
run subsequently demonstrated MINT0->MINT1->event-generation transitions,
but **failed during post-generation finalization**. Final-stage failure diagnosis
and production filesystem/quota handling remain open. Freeze source hashes and use
a new isolated pilot process for any later full-workflow testing; never
retrofit the candidate into existing integration/gridpack directories.
