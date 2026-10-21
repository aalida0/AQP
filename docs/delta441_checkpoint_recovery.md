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
