# Delta441 checkpoint recovery (MG5_aMC@NLO v3.5.11)

Workflow policy: run recovery scripts from /home/aalida/AQP/Wjets/WENU; store the copied heavy process and all recovery artifacts under /data/aalida/AQP/Wjets/WENU. Do not add symbolic links. Preserve the original home process unchanged.

Source: https://github.com/mg5amcnlo/mg5amcnlo/blob/v3.5.11/madgraph/interface/amcatnlo_run_interface.py

The MG controller saves SubProcesses/job_status.pkl at the MINT1-to-MINT2 transition. In generation-only mode, it reads that pickle, rereads the original res_1.dat fields, recomputes event allocation, and prepares the MINT2 input. The missing state can be reconstructed from the actual delta441 subprocess/channel manifest and res_1.dat files.

1. On the AF login node, copy the original process tree to /data/aalida/AQP/Wjets/WENU/delta441_backup/PROCNLO_loop_sm-no_b_mass_0 using rsync -a. Do not erase the original.
2. Fetch scripts/rebuild_wjets_delta441_checkpoint.py to /home/aalida/AQP/Wjets/WENU, compile-check it with python3 -m py_compile, and run --process /data/.../delta441_backup/PROCNLO_loop_sm-no_b_mass_0 without --write-checkpoint.
3. Confirm RECOVERY_PRECHECK_PASS, 300 channels and expected run-card configuration. If any check fails, do not proceed.
4. Run again with --write-checkpoint and --report /data/aalida/AQP/Wjets/WENU/recovery_reports/delta441_checkpoint_audit.json. These options create the missing pickle and JSON report only; no MG executable is run. The tool refuses to overwrite an existing state or report.
5. Verify schema and stage-2 recovery prerequisites before calling MG generation-only. Never blindly call launch against the original, and do not run MG executables from /data if the local policy forbids it; plan the later runtime separately.

Audit flags intentionally reject missing/nonfinite result fields, incomplete MINT1 grid labels, missing process channels or mismatched GF directory counts, and zero ABS contribution that causes division by zero in MG allocation. The checkpoint is a testable reconstruction, not a claim that the full gridpack already works.
## Preflight PASS and stage-2 checkpoint write (21 October 2026)

Delta441 copied process passed a read-only audit: 300 GF / 82 subprocesses, valid MINT1 artifacts, run_card nevents=1000, req_acc=1e-4, folding=4,4,1, ickkw=3, nevt_job=-1, randinit=r=33. The two case-variant MCatNLO-Delta entries are processed sequentially by v3.5.11 RunCardNLO.read; the final lowercase mcatnlo_delta=True wins, so effective Delta is on.

The checkpoint builder was amended to match MG5 write_res_txt_file ordering (descending errorABS) and to validate the effective run card before writing. The script runs from /home while creating ONLY checkpoint and JSON in the /data copy.

Next, re-download the latest scripts/rebuild_wjets_delta441_checkpoint.py into /home, re-run audit, and explicitly write a checkpoint with --write-checkpoint --report /data/aalida/AQP/Wjets/WENU/recovery_reports/delta441_checkpoint_audit.json. Run scripts/validate_delta441_checkpoint.py against the trusted standard111 job_status.pkl and new Delta441 pickle. If comparison signals missing keys, halt and investigate; do not launch generation.

The next stage will need a no-execution-from-/data runtime design. Do not invoke MG5's only_generation from the /data process tree or rerun MINT0/1.

## Recovery checkpoint schema audit (October 21, 2026)

Following successful 300/300 GF preflight and initial checkpoint creation, comparison with the trusted `standard111` pickle found 20 reconstructed keys versus 21 reference keys. Only the key `fold_string` was missing. MG5 v3.5.11 `write_input_file` (called during MINT1 setup) populates `fold_string=' '.join(map(str, run_card['folding']))`; for Δ441 this is `4 4 1`. No MINT grid/integral rerun is warranted.

A separate repair utility (`scripts/repair_delta441_fold_string.py`) defaults to audit-only and, with `--apply`, hard-links the original checkpoint to `SubProcesses/job_status.pre_fold_string.pkl` and atomically replaces just `job_status.pkl` with the 300-job list amended. It writes only to the /data recovery copy. The checkpoint builder has also been fixed for *future fresh reconstructions*. The validator now requires all original reference keys in each job and `fold_string='4 4 1'` for all 300.

After repair, rerun `scripts/validate_delta441_checkpoint.py` from /home, comparing /data Δ441 checkpoint against a trusted original standard111 checkpoint from /home. Wait for `CHECKPOINT_SCHEMA_PASS` before attempting MadGraph generation-only. No original home process files must be changed.


## Stage 5: NLO gridpack packaging before MINT2

Following the restored 21/21-key checkpoint schema, the 300 Δ441 GF channels, job ordering and absolute /data GF paths all pass reference validation. The supplied ATLAS MadGraph documentation states that recovery of a failed parallel NLO gridpack can be accomplished by archiving the process directory (unlike the separate LO event combination procedure). For Δ441 we package the restored checkpoint and original MINT1 grids without requiring a pre-existing MINT2 LHE. This does not prove generation is functional: it enables the normal generation-from-gridpack smoke test.

First run read-only `scripts/audit_delta441_mint2_allocation.py` from /home. It mirrors v3.5.11 weighted GF allocation for the next seed, taking into account `update_random_seed`. If run card `iseed=0`, current `SubProcesses/randinit=r=33` will become `r=34` on the next controller launch; no seed state is changed by the audit. It does not launch MG and does not write files.

Then obtain the updated `scripts/package_wjets_gridpacks.sh` in /home and submit `condor/package_delta441.submit` from /home. It submits exactly one gridpack-packaging job, with `should_transfer_files=YES` so no FileSystemDomain restriction, NFS logs in /home, and direct archive output in /data. The producer's modified files are only its `/data/.../gridpacks/*.tar.gz` and `.sha256`. The source process is unchanged. The archive name includes `delta441_backup` to preserve provenance and avoid conflating it with a separate restarted `delta441` directory.

The compressed archive is an **integration-only candidate**; do not claim success until ATLAS `Gen_tf.py` generates a new LHE sample from this archive in an isolated runtime. The generator must not be executed within the /data source process tree. The eventual runtime should stage executable components on a worker's local scratch area (script source/orchestration in /home), with heavy archival inputs and retained outputs under /data. Be sure to set ATLAS AthGeneration and MadGraph/Pythia versions matching the integration.


## W+jets four-way Condor packaging hotfix (October 21, 2026)

The first sequential packaging Condor job (cluster 3877629) failed in archive validation because AWK's reserved built-in function name `sub` was used as an AWK variable. The fix renames it to `has_subprocesses` in `scripts/package_wjets_gridpacks.sh`; this was independently exercised against a synthetic gzip tar archive with the required `madevent/` layout. This was not a MadGraph integration failure. The temporary standard111 archive was removed on error, so no finalized gridpack existed.

Use `condor/package_wjets_four.submit` to create four independent HTCondor procs in one cluster, one each for `standard111`, `delta111`, `delta221`, and `delta441_backup`. Each has uniquely named stdout/stderr/HTCondor logs under NFS `/home/aalida/.../packaging_logs/`; inputs and output archives live under `/data/aalida/AQP/Wjets/WENU`. HTCondor transfers only the lightweight `/home` packaging script and runs it from worker scratch, without `MYFilesystem` or FileSystemDomain constraints. Delta441 is explicitly an integration-only candidate archive until MINT2 smoke testing succeeds.

## Stage 6: standalone Δ441 MINT2 smoke test via original JO

After four SHA256-validated archives and a passing MINT2 weighted allocation preflight, the supplied Δ441 JO (`delta441_backup/100003/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441.py`) has a correct `is_gen_from_gridpack()` branch. The `grid_pack=True` keyword in `generate()` does not cause reintegration on the gridpack path: `MadGraphUtils.generate()` dispatches early to `generate_from_gridpack()` when `madevent/` exists; on the NLO path it runs MG `bin/generate_events --parton --nocompile --only_generation -f` (MadGraphControl version should be verified locally in AthGeneration/23.6.63).

Because the supplied JO has `cluster_type='condor', run_mode=1`, the isolated test JO copy overrides `run_mode=2, nb_core=4` only in the gridpack case. The runner additionally exports `ATHENA_CORE_NUMBER=4` because `MadGraphUtils.setNCores()` derives its effective mode from that environment variable in current versions; this prevents nested Condor launch and permits the local worker's four cores. The original JO and archived cards are unchanged.

The source scripts live under `scripts/prepare_delta441_smoke_jo.py` and `scripts/run_delta441_smoke_condor.sh`, and the submit under `condor/delta441_mint2_smoke.submit`. Fetch them to `/home/aalida/AQP/Wjets/WENU`; use `prepare_delta441_smoke_jo.py --source /home/aalida/AQP/Wjets/WENU/delta441_backup/100003/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441.py --target-dir /home/aalida/AQP/Wjets/WENU/smoke_jo/100003 --cores 4`, check `python3 -m py_compile ...` and `bash -n run_delta441_smoke_condor.sh` and `condor_submit delta441_mint2_smoke.submit`.

The submit transfers only the small JO directory and runner script (code from `/home`) to Condor scratch. The 3.5GB archive is read directly from `/data/aalida/AQP/Wjets/WENU/gridpacks/` through `--inputGenConfFile`. The extracted `madevent` and generation intermediates live on local scratch; retained logs and generator outputs are copied to `/data/aalida/AQP/Wjets/WENU/smoke_tests/delta441_backup/seed34_100events/`. The original large `/data` integration process and archives must never be run in place. Initial smoke requests 4 cores, 8GB RAM, 45GB worker-local disk.

Smoke-test success is not established until log evidence confirms `FOUND GRIDPACK`, a generation-only MINT2 route, and the output contains the intended LHE events with appropriate FxFx shower validation. If the new directory exists from a previous attempt, the runner deliberately refuses reuse; audit it and choose a new output name before re-submitting.

## Smoke attempt 3897674: environment setup failure before MINT2 (Oct 21, 2026)

HTCondor cluster 3897674 exited in ~1 second with `ExitCode=1`. Stdout showed only worker scratch, /data gridpack/output paths, then `Warning: -e is set in the environment and may cause issues`; there was no Gen_tf.log, just runner_exit_code=1. This is an ATLAS shell setup failure, not evidence of a problem in the recovered integration. The original runner had `set -euo pipefail` and only disabled `-u` before sourcing atlasLocalSetup.sh.

The updated `scripts/run_delta441_smoke_condor.sh` disables both `errexit` and `nounset` while sourcing `atlasLocalSetup.sh` and running `asetup AthGeneration,23.6.63`, captures their exit codes separately, and writes `atlas_environment_setup.log` into the /data output directory. It additionally reports missing `Gen_tf.py`, `MADPATH`, and `PY8PATH` with explicit errors. Retry output is `.../smoke_tests/delta441_backup/seed34_100events_retry1` to avoid overwriting the previous run's diagnostic directory. The Condor submit file is unchanged.

## Smoke retry1: Gen_tf CLI mismatch; correct gridpack staging

On 2026-10-21 at ~17:48, the corrected ATLAS environment setup succeeded for `AthGeneration/23.6.63`, and `Gen_tf.py` started successfully. It aborted during CLI parsing with `unrecognized arguments: --runNumber=100003 --inputGenConfFile=/data/.../delta441_backup.MG3511.GRID.tar.gz`. This release accepts neither option, as confirmed by its printed argparse usage. It **does** accept `--jobConfig`, `--randomSeed`, `--maxEvents` and `--outputTXTFile`. `--inputGeneratorFile` is for event-file input, and must NOT be used as a substitute for the gridpack archive.

To test the recovered NLO gridpack, updated `scripts/run_delta441_smoke_condor.sh` untars the /data archive into worker scratch **as the relative directory `madevent/`**. ATLAS MadGraphControl detects this directory from the current working directory and enters its `is_gen_from_gridpack()` path. The copied smoke JO aborts if `madevent/` is absent, preventing accidental fresh integrations. The runner prechecks the extracted checkpoint, cards and `orderstags_glob.dat`, then calls supported `Gen_tf.py` options with `--jobConfig=/scratch/.../100003`; DSID comes from JO directory. The output path was advanced to `/data/aalida/AQP/Wjets/WENU/smoke_tests/delta441_backup/seed34_100events_retry2/` to preserve earlier failures. Every generation attempt still executes from worker scratch and retains artifacts on /data.

Retry only after `bash -n` validation of the updated runner and verify no retry2 directory already exists. Condor `delta441_mint2_smoke.submit` itself remains unchanged. Check stderr/stdout, `/data/.../retry2/Gen_tf.log` and archive produced before declaring MINT2 successful. The original /data integration trees and gridpack tarballs are never modified.
## Smoke retry2: missing MGControl initialization in AthGeneration 23.6.63

Job's extraction and AthGeneration transform succeeded through JOs, but failed before MadGraph integration/event generation: `AttributeError: 'NoneType' object has no attribute 'runCardDict'` from `/cvmfs/.../python/MadGraphControl/MadGraphUtils.py:1533` during `modify_run_card` (the Δ441 smoke JO line 158). The `log.generate` records two `Located input grid pack area` messages before failure, so the extracted `madevent/` was detected. This is the legacy MadGraphControl singleton initialization issue: the original JO initializes it implicitly via `new_process()` only in the fresh-process branch, skipped for gridpack runs.

Fix in `scripts/prepare_delta441_smoke_jo.py` (branch dev/wjets-recovery): after configuring `MadGraphControl.MadGraphUtils.MADGRAPH_PDFSETTING`, and BEFORE top-level `modify_run_card`, insert a gridpack-only guarded initialization: `import MadGraphControl.MadGraphUtils as _aqp_mg_utils; from MadGraphControl.MGC import MGControl as _AQP_MGControl; if _aqp_mg_utils.my_MGC_instance is None: _aqp_mg_utils.my_MGC_instance = _AQP_MGControl(pdf_setting=_aqp_mg_utils.MADGRAPH_PDFSETTING)`. Validate it refers to existing `madevent`, NLO and loaded run card. `MGControl()` detects `madevent/`, reads existing cards and sets the singleton; it does NOT call MadGraph `new_process()` or rerun MINT0/MINT1.

Update the complete isolated JO: rename `/home/aalida/AQP/Wjets/WENU/smoke_jo/100003` to a distinct backup (do not overwrite), then rerun `prepare_delta441_smoke_jo.py --source /home/aalida/AQP/Wjets/WENU/delta441_backup/100003/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441.py --target-dir /home/aalida/AQP/Wjets/WENU/smoke_jo/100003 --cores 4`. The Condor submit file still transfers `smoke_jo/100003`. The runner output path is now `.../seed34_100events_retry3/` and checks for the new `AQP_DELTA441_MGCONTROL_GRIDPACK_INIT_PASS` log marker. The original /home JO, /data gridpack, and integration trees are unchanged. Retained `retry2` diagnostics must be preserved.
## Smoke retry3: MGControl constructor signature mismatch; retry4 planned

`log.generate` for retry3 (Oct 21 ~23:15 UTC) reports `TypeError: MGControl.__init__() got an unexpected keyword argument 'pdf_setting'` in the isolated smoke JO. The singleton `my_MGC_instance` was missing, but the previous repair assumed the newer MGC API signature. The AthGeneration/23.6.63 constructor **does not** accept the `pdf_setting` keyword. The current ATLAS Doxygen development branch shows this keyword, which is not authoritative for the installed 23.6.63 release; do not derive release-specific keyword arguments from current main documentation.

The updated `scripts/prepare_delta441_smoke_jo.py` constructs `_AQP_MGControl()` without unsupported keywords in the gridpack-only branch; it propagates the JO `MADGRAPH_PDFSETTING` into the legacy `MadGraphControl.MGC` module before construction and into `pdf_setting` attribute if one exists, and prints the exact installed constructor signature with `inspect.signature`. Existing NLO / process directory / run-card checks remain in effect, as does the fail-closed no-new_process guard. The runner's output directory is now `seed34_100events_retry4`, preserving all earlier attempt directories.

Replace the isolated `smoke_jo/100003` by renaming it to a uniquely named backup and rerunning the updated prepare script against the original full delta441_backup JO. Download the updated runner. Check via `bash -n` and `python3 -m py_compile`, and inspect `grep -n '_AQP_MGControl(' smoke_jo/100003/mc.*delta441.py` to confirm a zero-arg constructor call. Then submit `delta441_mint2_smoke.submit`. Do not claim event-generation success without logs and an actual LHE/TXT result.