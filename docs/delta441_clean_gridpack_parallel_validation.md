# Δ441 Wenu cleaned gridpack and 8-CPU parallel 1000-LHE validation

Status: **prepared on GitHub, NOT YET EXECUTED**.
Branch: `dev/wjets-recovery`. Environment: UChicago AF, AthGeneration 23.6.63, MG5_aMC@NLO 3.5.11, GCC14/EL9, Pythia8 8.315. Generation uses 13 TeV Wenu+0,1,2 partons, FxFx `ickkw=3`, MC@NLO-Δ on, folding `(4,4,1)`, HT2 biasing and PDF LHAPDF ID 325100.

## Why this design

- **Keep original recovered gridpack immutable**: `gridpacks/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441_backup.MG3511.GRID.tar.gz`.
- **Package a corrected COPY**: `gridpacks/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441_cleaned_v1.MG3511.GRID.tar.gz`.
- Original and clean archives preserve `madevent/SubProcesses/job_status.pkl` and the MINT1 integration grids. Only stale top-level `madevent/*_debug.log` are removed from the cleaned archive. `madevent/Source/make_opts` is patched from `-lc++` to `-lstdc++` **if and only if required**. Collector-link preflight runs at packaging time. Checkpoint checksum before and after is recorded; source archive SHA256 is recorded. No integration or MadGraph generation executes during repackaging.
- Run MadGraph generation from worker-local scratch with `run_mode=2, nb_core=8` (**local multicore**), inside **one outer 8-CPU HTCondor allocation**. Do **not** use `run_mode=1` here: that mode submits inner cluster jobs and is not needed. `ATHENA_CORE_NUMBER` is unset to avoid unintended Athena multiprocessing; explicit config card controls MadGraph cores. Inspect MG runtime logs for actual concurrency.
- `--outputTXTFile` uses the validated **dummy event without FxFx hook** from the successful seed-37 test. LHE parton events remain unshowered in TXT. Real LHE showering is in the third DAG stage, using the verified seed-35 shower-only JO.
- First test is **1000 LHE events**, not 1000 EVNT events. `LHE_OVERSAMPLING_FACTOR=5`; hence `Gen_tf --maxEvents=200` requests **1000 LHE**. Shower stage requests **200 EVNT** from those 1000 input LHE events; whether sufficient after FxFx vetoes is measured by the job and not assumed.

## One DAG submission (on AF login node)

```bash
cd /home/aalida/AQP/Wjets/WENU
curl -fsSL https://raw.githubusercontent.com/aalida0/AQP/dev/wjets-recovery/scripts/stage_delta441_clean_8cpu_dag.sh \
  -o stage_delta441_clean_8cpu_dag.sh
bash stage_delta441_clean_8cpu_dag.sh
# Stop here if syntax, destination-exists, input or environment checks fail.
condor_submit_dag delta441_clean_8cpu_1000lhe.dag
```

The staging script downloads **complete** JobOptions, three batch runners, three submit files, and the DAG into `/home/aalida/AQP/Wjets/WENU/`, checks the Python and bash syntax, and refuses to target an existing output directory/archive.

The DAG has three strict success dependencies:
1. CLEAN: 1 CPU, 8 GB RAM, 60 GB worker scratch; extract/repair/repack source. Reports in `smoke_tests/delta441_backup/clean_gridpack_v1/`.
2. LHE: 8 CPUs, 16 GB RAM, 60 GB scratch; MadGraph `run_mode=2, nb_core=8`; 1000 LHE, seed 137. Reports in `smoke_tests/delta441_backup/delta441_clean_v1_8cpu_seed137_1000lhe/`.
3. SHOWER: 1 CPU, 6 GB RAM, 8 GB scratch; uses real FxFx Pythia8 `nJetMax=2, qCut=20 GeV`, and requests 200 EVNT events, seed 3137. Reports in `smoke_tests/delta441_backup/delta441_clean_v1_seed137_fxfx_shower/`.

DAGMan skips downstream nodes if an upstream node exits unsuccessfully; no automatic retries are configured. Submission and execution are independent of SSH connections. If the DAG fails, **do not resubmit an unchanged DAG**: each runner refuses to overwrite persistent outputs. Preserve logs, fix the cause, and choose unique versioned paths for any retry.

### Monitor live while SSH can disconnect

```bash
condor_q -nobatch
# For a running CLEAN, LHE or SHOWER proc:
condor_ssh_to_job <ClusterId.ProcId>
cd "$_CONDOR_SCRATCH_DIR"
# For LHE stage:
tail -n 50 -F Gen_tf.log
# For SHOWER stage:
tail -n 50 -F Gen_tf_shower.log
```

On disconnect, log back in and reattach to the same running batch job. If it finished, inspect its retained `/data` output and `/home/.../packaging_logs/delta441_*.{out,err,log}` files. For CLEAN, inspect `/data/.../clean_gridpack_v1/packaging.stdout`, which is written while packaging runs.

### Interpreting results

```bash
BASE=/data/aalida/AQP/Wjets/WENU
CLEAN=$BASE/smoke_tests/delta441_backup/clean_gridpack_v1
LHE=$BASE/smoke_tests/delta441_backup/delta441_clean_v1_8cpu_seed137_1000lhe
SHOWER=$BASE/smoke_tests/delta441_backup/delta441_clean_v1_seed137_fxfx_shower

cat "$CLEAN/prepare_exit_code" "$LHE/runner_exit_code" "$SHOWER/runner_exit_code"
cat "$CLEAN/cleaned_gridpack.sha256"
grep -E 'AQP_DELTA441|only_generation|run_mode|nb_core|Completed:|Generating events' "$LHE/Gen_tf.log" | tail -n 70
grep -E 'AQP_FXFX_SHOWER|JetMatching|Using FxFx|events processed' "$SHOWER/log.generate" | tail -n 70
ls -lh "$LHE"/*.TXT.tar.gz "$SHOWER"/*.EVNT.pool.root
```

A passing overall test requires three exit codes equal 0, clean archive SHA256, the **1000 complete LHE events** in the TXT tarball, and an EVNT pool file produced by the real FxFx shower. Small-sample shower output does **not** yet establish final production cross-section normalization, biased-event effective statistics, matching efficiency, or stable million-event throughput.

MadGraph `run_mode` reference: 0 serial / 1 cluster / 2 local multicore (see MG5_aMC NLO configuration examples and CMS NLO gridpack documentation).
