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