#!/usr/bin/env bash
# Mode-aware Delta441 GENtoTXT smoke test; script source in /home.
# Heavy input in /data; transient process runs on worker scratch;
# retained logs/results on /data.
set -euo pipefail

BASE=/data/aalida/AQP/Wjets/WENU
PACK="$BASE/gridpacks/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441_backup.MG3511.GRID.tar.gz"
OUT="$BASE/smoke_tests/delta441_backup/delta441_txt_modefixed_seed37_10events"
CORES=1
SCRATCH="$(printenv _CONDOR_SCRATCH_DIR || true)"
if [[ -z "$SCRATCH" || ! -d "$SCRATCH" ]]; then
  echo "ERROR: no worker-local Condor scratch detected" >&2
  exit 2
fi
SCRATCH="$(realpath "$SCRATCH")"
case "$SCRATCH/" in
  /data/*|/home/*)
    echo "ERROR: refusing to execute generated MG code on Ceph or NFS: $SCRATCH" >&2
    exit 2 ;;
esac
if [[ -e "$OUT" ]]; then
  echo "ERROR: output directory exists: $OUT" >&2
  exit 2
fi
if [[ ! -r "$PACK" ]]; then
  echo "ERROR: gridpack unavailable on /data: $PACK" >&2
  exit 2
fi
if [[ ! -f "$SCRATCH/100003/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441.py" ]]; then
  echo "ERROR: transferred full JO directory 100003 is missing" >&2
  exit 2
fi

mkdir -p "$OUT"
copy_artifacts() {
  local status=$?
  trap - EXIT
  set +e
  echo "$status" > "$OUT/runner_exit_code"
  if [[ -f "$SCRATCH/Gen_tf.log" ]]; then
    cp -p "$SCRATCH/Gen_tf.log" "$OUT/Gen_tf.log"
    grep -E 'AQP_DELTA441|FOUND GRIDPACK|only_generation|Generating events|MINT|ERROR|FATAL|Traceback' \
      "$SCRATCH/Gen_tf.log" | tail -n 150 > "$OUT/diagnostic_tail.txt"
  fi
  for f in runargs.generate.py jobReport.json log.generate; do
    if [[ -f "$SCRATCH/$f" ]]; then cp -p "$SCRATCH/$f" "$OUT/"; fi
  done
  find "$SCRATCH" -maxdepth 1 -type f \
    \( -name '*.TXT.tar.gz' -o -name '*.TXT' -o -name '*.events' \
       -o -name 'events.lhe.gz' -o -name '*.TXT.gz' \) \
    -exec cp -p '{}' "$OUT/" \;
  # Preserve small generation-state logs and the produced LHE, if available.
  if [[ -d "$SCRATCH/madevent/Events" ]]; then
    find "$SCRATCH/madevent/Events" -maxdepth 2 -type f \
      \( -name 'events.lhe.gz' -o -name 'events.lhe' \) -size -100M \
      -exec cp -p '{}' "$OUT/" \;
  fi
  echo "Smoke job exit status: $status"
  echo "Retained artifacts: $OUT"
  exit "$status"
}
trap copy_artifacts EXIT

cd "$SCRATCH"
echo "Worker scratch: $PWD"
echo "Archive: $PACK"
echo "Results: $OUT"

# ATLAS setup scripts are not safe with Bash -e/-u:
# earlier run 3897674 died in atlasLocalSetup.sh with "-e is set".
# Capture both setup steps independently and preserve their diagnostics
# under /data even if Gen_tf never starts.
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
SETUP_LOG="$OUT/atlas_environment_setup.log"
echo "Starting ATLAS environment setup" | tee "$SETUP_LOG"
set +e
set +u
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" >> "$SETUP_LOG" 2>&1
als_exit=$?
echo "atlasLocalSetup.sh exit code: $als_exit" | tee -a "$SETUP_LOG"
if [[ "$als_exit" -eq 0 ]]; then
  asetup AthGeneration,23.6.63 >> "$SETUP_LOG" 2>&1
  asetup_exit=$?
  echo "asetup AthGeneration,23.6.63 exit code: $asetup_exit" | tee -a "$SETUP_LOG"
else
  asetup_exit=99
fi
set -e
set -u
tail -n 35 "$SETUP_LOG"
if [[ "$als_exit" -ne 0 || "$asetup_exit" -ne 0 ]]; then
  echo "ERROR: ATLAS environment setup failed. See $SETUP_LOG" >&2
  exit 11
fi

# Match the established Wenu gridpack event-generation JO:
# run_mode=0, nb_core=1, no nested HTCondor or multicore override.
# An inherited ATHENA_CORE_NUMBER would defeat these tested settings.
unset ATHENA_CORE_NUMBER
export OMP_NUM_THREADS=1
if ! command -v Gen_tf.py >/dev/null; then
  echo "ERROR: Gen_tf.py unavailable after asetup" >&2
  exit 12
fi
if [[ -z "$(printenv MADPATH || true)" ]]; then
  echo "ERROR: MADPATH not defined by AthGeneration setup" >&2
  exit 13
fi
if [[ -z "$(printenv PY8PATH || true)" ]]; then
  echo "ERROR: PY8PATH not defined by AthGeneration setup" >&2
  exit 14
fi
echo "MADPATH=$MADPATH"
echo "PY8PATH=$PY8PATH"
echo "AQP_DELTA441_SMOKE_SERIAL_RUN_MODE=0; ATHENA_CORE_NUMBER is unset"
echo "Gen_tf.py: $(which Gen_tf.py)"
echo "Starting Gen_tf.py in worker scratch..."
head -n 7 "$MADPATH/VERSION" || true

# AthGeneration/23.6.63 does NOT accept --runNumber or
# --inputGenConfFile.  --inputGeneratorFile is for LHE, NOT a gridpack.
# ATLAS MadGraphControl detects a prepared gridpack by finding the
# relative directory "madevent" under the generation working directory.
# Extract the archived NLO process to worker scratch, never to /data.
echo "Extracting Δ441 NLO gridpack into worker scratch..."
date -u
tar -xzf "$PACK" -C "$SCRATCH" > "$OUT/gridpack_extract_stdout.log" \
  2> "$OUT/gridpack_extract_stderr.log"
if [[ ! -d "$SCRATCH/madevent" || 
      ! -s "$SCRATCH/madevent/SubProcesses/job_status.pkl" || 
      ! -s "$SCRATCH/madevent/Cards/run_card.dat" || 
      ! -s "$SCRATCH/madevent/SubProcesses/orderstags_glob.dat" ]]; then
  echo "ERROR: extracted NLO gridpack is incomplete" >&2
  exit 41
fi
# The --only_generation flow will read this reconstructed checkpoint;
# fail closed if it was not extracted.
test -s "$SCRATCH/madevent/SubProcesses/randinit"
echo "AQP_DELTA441_MADEVENT_EXTRACTED_AND_CHECKED"
date -u

# NLO SubProcesses/makefile includes ../Source/make_opts and appends
# $(LDFLAGS) to the collect_events link command. The broken '-lc++'
# is NOT a literal token in SubProcesses/makefile. Patch only the
# worker's extracted Source/make_opts if it contains the problematic
# token; use a command-line LDFLAGS override for an early link smoke.
COLLECT_MAKE="$SCRATCH/madevent/SubProcesses/makefile"
SOURCE_OPTS="$SCRATCH/madevent/Source/make_opts"
if [[ ! -f "$COLLECT_MAKE" || ! -f "$SOURCE_OPTS" ]]; then
  echo "ERROR: missing NLO collector makefile or included Source/make_opts" >&2
  exit 42
fi
LIBSTDCXX="$(gfortran -print-file-name=libstdc++.so)"
if [[ "$LIBSTDCXX" == "libstdc++.so" || ! -f "$LIBSTDCXX" ]]; then
  echo "ERROR: GCC toolchain cannot locate libstdc++.so" >&2
  exit 43
fi
if grep -Fq -- '-lc++' "$SOURCE_OPTS"; then
  cp -p "$SOURCE_OPTS" "$SOURCE_OPTS.before_stdlib_linkfix"
  sed -i 's/-lc++/-lstdc++/g' "$SOURCE_OPTS"
  echo "AQP_DELTA441_SCRATCH_SOURCE_OPTS_LINK_FIX_APPLIED"
else
  echo "AQP_DELTA441_SCRATCH_SOURCE_OPTS_NO_LITERAL_LIBCPP"
fi
# This is a link-only preflight and does not run any MINT0/1/2 channel.
# The command-line override takes priority over assignments in make_opts;
# an early link error is much cheaper than failure after channel generation.
if ! make -C "$SCRATCH/madevent/SubProcesses" collect_events \
  LDFLAGS=-lstdc++ \
  > "$OUT/collect_events_link_preflight.log" 2>&1; then
  echo "ERROR: collect_events link preflight failed" >&2
  tail -n 60 "$OUT/collect_events_link_preflight.log" >&2
  exit 44
fi
test -x "$SCRATCH/madevent/SubProcesses/collect_events"
echo "AQP_DELTA441_COLLECT_EVENTS_LINK_PASS"

# Archived madevent/ may contain historical *_debug.log files from a
# failed gridpack-building attempt. AthGeneration 23.6.63 treats any of
# these root-level debug logs as fatal after successful LHE generation,
# even when the new run was clean. Quarantine ONLY those pre-existing
# logs from the extracted scratch copy, preserving originals on /data.
STALE_DEBUG_OUT="$OUT/archived_gridpack_debug_logs"
mkdir -p "$STALE_DEBUG_OUT"
while IFS= read -r -d '' f; do
  name="$(basename "$f")"
  cp -p "$f" "$STALE_DEBUG_OUT/$name"
  rm -- "$f"
  echo "AQP_DELTA441_QUARANTINED_STALE_DEBUG=$name"
done < <(find "$SCRATCH/madevent" -maxdepth 1 -type f \
  -name '*_debug.log' -print0)
# Guard against unchanged/unhandled root-level debug logs.
if find "$SCRATCH/madevent" -maxdepth 1 -type f \
  -name '*_debug.log' -print -quit | grep -q .; then
  echo "ERROR: stale debug logs remain in extracted gridpack" >&2
  exit 45
fi
echo "AQP_DELTA441_PREEXISTING_DEBUG_LOGS_CLEARED"

# This is a TXT-only transform, not EVNT production.
# Its DSID is inferred from the 100003 JobOptions directory.
# The copied JO aborts if is_gen_from_gridpack() is False.
set +e
Gen_tf.py \
  --ecmEnergy=13000 \
  --maxEvents=10 \
  --firstEvent=1 \
  --randomSeed=37 \
  --jobConfig="$SCRATCH/100003" \
  --outputTXTFile=delta441_modefixed_seed37.TXT.tar.gz \
  --outputFileValidation=False \
  > "$SCRATCH/Gen_tf.log" 2>&1
ret=$?
set -e

echo "Gen_tf exit code: $ret"
if [[ "$ret" -ne 0 ]]; then
  echo "ERROR: Gen_tf failed; see retained Gen_tf.log" >&2
  exit "$ret"
fi
# The dedicated generation JO prints these markers after accepting madevent/.
if ! grep -q 'AQP_DELTA441_EXISTING_GRIDPACK_ONLY' "$SCRATCH/log.generate"; then
  echo "ERROR: standalone JO did not confirm the existing-gridpack-only branch" >&2
  exit 90
fi
if ! grep -q 'AQP_DELTA441_MGCONTROL_CARDS_LOADED' "$SCRATCH/log.generate"; then
  echo "ERROR: proven MGControl card-loading sequence was not completed" >&2
  exit 91
fi
if ! grep -qE 'only_generation|--only_generation' "$SCRATCH/Gen_tf.log"; then
  echo "WARNING: --only_generation not visible in transform log; audit detailed job logs" >&2
fi
if ! grep -q 'AQP_DELTA441_TXT_MODE_DUMMY_WITHOUT_LHE_OR_FXFX_HOOK' "$SCRATCH/log.generate"; then
  echo "ERROR: patched JO did not select TXT dummy mode without FxFx hook" >&2
  exit 92
fi
if grep -q 'Adding user hook JetMatchingMadgraph' "$SCRATCH/log.generate"; then
  echo "ERROR: FxFx hook was incorrectly attached to TXT dummy event" >&2
  exit 94
fi
if [[ ! -s "$SCRATCH/delta441_modefixed_seed37.TXT.tar.gz" ]]; then
  echo "ERROR: expected TXT archive was not produced" >&2
  exit 93
fi

echo "DELTA441_SMOKE_GRIDPACK_BRANCH_CONFIRMED"
echo "Transform finished; generated outputs still require content validation."
