#!/usr/bin/env bash
# Standalone NLO Delta441 MINT2 smoke test; script source in /home.
# Heavy input in /data; transient process runs on worker scratch;
# retained logs/results on /data.
set -euo pipefail

BASE=/data/aalida/AQP/Wjets/WENU
PACK="$BASE/gridpacks/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441_backup.MG3511.GRID.tar.gz"
OUT="$BASE/smoke_tests/delta441_backup/seed34_100events_retry2"
CORES=4
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
    grep -E 'FOUND GRIDPACK|only_generation|Generating events|MINT|ERROR|FATAL|Traceback' \
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

# MadGraphUtils.setNCores() uses ATHENA_CORE_NUMBER to override any
# cluster_type/run_mode settings inherited from the old gridpack.
export ATHENA_CORE_NUMBER="$CORES"
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
echo "ATHENA_CORE_NUMBER=$ATHENA_CORE_NUMBER"
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

# This is a TXT-only transform, not EVNT production.
# Its DSID is inferred from the 100003 JobOptions directory.
# The copied JO aborts if is_gen_from_gridpack() is False.
set +e
Gen_tf.py \
  --ecmEnergy=13000 \
  --maxEvents=100 \
  --firstEvent=1 \
  --randomSeed=34 \
  --jobConfig="$SCRATCH/100003" \
  --outputTXTFile=delta441_smoke.TXT.tar.gz \
  --outputFileValidation=False \
  > "$SCRATCH/Gen_tf.log" 2>&1
ret=$?
set -e

echo "Gen_tf exit code: $ret"
if [[ "$ret" -ne 0 ]]; then
  echo "ERROR: Gen_tf failed; see retained Gen_tf.log" >&2
  exit "$ret"
fi
# The copied JO prints this marker only if is_gen_from_gridpack() is True.
if ! grep -q 'AQP_DELTA441_SMOKE_LOCAL_MULTICORE=4' "$SCRATCH/Gen_tf.log"; then
  echo "ERROR: copied JO did not confirm generation-from-gridpack branch" >&2
  exit 91
fi
if ! grep -qE 'only_generation|--only_generation' "$SCRATCH/Gen_tf.log"; then
  echo "WARNING: --only_generation not visible in transform log; audit detailed job logs" >&2
fi
if [[ ! -s "$SCRATCH/delta441_smoke.TXT.tar.gz" ]]; then
  echo "ERROR: expected TXT archive was not produced" >&2
  exit 93
fi

echo "DELTA441_SMOKE_GRIDPACK_BRANCH_CONFIRMED"
echo "Transform finished; generated outputs still require content validation."
