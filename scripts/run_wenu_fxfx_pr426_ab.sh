#!/usr/bin/env bash
# Fresh Wenu FxFx PR426 A/B: 200 or 50k LHE, no gridpacks, local 16-core.
# Execute ONLY in an outer Condor worker slot, never on a login node.
set -Eeuo pipefail
CASE="$1"; NEVENTS="$2"; SEED="$3"
case "$CASE" in before|after) ;; *) echo "ERROR: invalid case" >&2; exit 2 ;; esac
case "$NEVENTS" in 200|50000) ;; *) echo "ERROR: invalid target count" >&2; exit 2 ;; esac
case "$SEED" in *[!0-9]*|"") echo "ERROR: bad seed" >&2; exit 2 ;; esac

TAG="smoke200"
[[ "$NEVENTS" == 50000 ]] && TAG="benchmark50k"

SCRATCH="$(printenv _CONDOR_SCRATCH_DIR || true)"
[[ -n "$SCRATCH" && -d "$SCRATCH" ]] || { echo "ERROR: Condor scratch required" >&2; exit 3; }
SCRATCH="$(realpath "$SCRATCH")"
case "$SCRATCH/" in
  /data/*|/home/*) echo "ERROR: scratch must not be on Ceph/NFS" >&2; exit 3 ;;
esac
BASE=/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_ab
OUT="$BASE/$TAG""_$CASE""_seed$SEED"
[[ ! -e "$OUT" && ! -L "$OUT" ]] || { echo "ERROR: output already exists: $OUT" >&2; exit 4; }
if [[ "$NEVENTS" == 50000 ]]; then
  for version in before after; do
    gate="$BASE/smoke200_$version""_seed311/runner_exit_code"
    [[ -f "$gate" && "$(cat "$gate")" == 0 ]] || {
      echo "ERROR: missing successful $version 200-event smoke" >&2; exit 5;
    }
  done
fi

cd "$SCRATCH"
JO="100005/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_$CASE.py"
for file in "$JO" dummy_fct.f montecarlocounter_MINE.f \
            aqp_prepare_fxfx_exclusive_kt_patch.py; do
  [[ -s "$file" ]] || { echo "ERROR: missing transferred input: $file" >&2; exit 6; }
done

mkdir -p "$OUT"

save_outputs() {
  local ret=$?
  trap - EXIT
  set +e
  printf '%s\n' "$ret" > "$OUT/runner_exit_code"
  for file in Gen_tf.log log.generate runargs.generate.py jobReport.json \
              prmon.summary.generate.json validated.events; do
    if [[ -f "$SCRATCH/$file" ]]; then cp -p "$SCRATCH/$file" "$OUT/"; fi
  done
  find "$SCRATCH" -maxdepth 1 -type f \
    \( -name '*.TXT.tar.gz' -o -name '*.TXT.events' \) \
    -exec cp -p '{}' "$OUT/" \;
  echo "AQP_FXFX_AB_RUNNER_EXIT=$ret CASE=$CASE LHE=$NEVENTS"
  echo "OUTPUT=$OUT"
  exit "$ret"
}
trap save_outputs EXIT

export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
set +e
set +u
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" \
  > "$OUT/atlas_setup.log" 2>&1
init_rc=$?
if [[ "$init_rc" == 0 ]]; then
  asetup AthGeneration,23.6.63 >> "$OUT/atlas_setup.log" 2>&1
  setup_rc=$?
else
  setup_rc=99
fi
set -e
set -u
if [[ "$init_rc" -ne 0 || "$setup_rc" -ne 0 ]]; then
  tail -n 60 "$OUT/atlas_setup.log" >&2
  exit 11
fi
command -v Gen_tf.py >/dev/null || { echo "ERROR: no Gen_tf.py" >&2; exit 12; }
[[ -n "$(printenv MADPATH || true)" && -n "$(printenv PY8PATH || true)" ]] || {
  echo "ERROR: missing MADPATH or PY8PATH" >&2; exit 13;
}
unset ATHENA_CORE_NUMBER
export OMP_NUM_THREADS=1
export AQP_FXFX_AB_INPUT_DIR="$SCRATCH"
echo "AQP_FXFX_AB_PROCESS_FRESH_AND_GRIDPACK_DISABLED"

MAX_EVENTS=$((NEVENTS / 5))
OUTPUT="wenu_standard111_pr426_$CASE""_seed$SEED""_$NEVENTS""lhe.TXT.tar.gz"
set +e
Gen_tf.py --ecmEnergy=13000 \
  --maxEvents="$MAX_EVENTS" \
  --firstEvent=1 \
  --randomSeed="$SEED" \
  --jobConfig="$SCRATCH/100005" \
  --outputTXTFile="$OUTPUT" \
  --outputFileValidation=False \
  > "$SCRATCH/Gen_tf.log" 2>&1
ret=$?
set -e
if [[ "$ret" -ne 0 ]]; then
  echo "ERROR: Gen_tf returned $ret" >&2
  tail -n 70 "$SCRATCH/Gen_tf.log" >&2
  exit "$ret"
fi
if [[ ! -s "$SCRATCH/$OUTPUT" || ! -s "$SCRATCH/log.generate" ]]; then
  echo "ERROR: successful Gen_tf without TXT archive/log" >&2; exit 14;
fi
for marker in "AQP_FXFX_AB_CASE=$CASE" \
              "AQP_FXFX_AB_LOCAL_MULTICORE_MODE=2_NB_CORE=16" \
              "AQP_FXFX_AB_REQUESTED_LHE=$NEVENTS""_REQ_ACC=0.1"; do
  grep -Fq "$marker" "$SCRATCH/log.generate" || {
    echo "ERROR: required log marker absent: $marker" >&2; exit 15;
  }
done
if [[ "$CASE" == after ]]; then
  grep -Fq 'AQP_FXFX_AB_PR426_ENABLED=True' "$SCRATCH/log.generate" || exit 15
else
  grep -Fq 'AQP_FXFX_AB_PR426_ENABLED=False' "$SCRATCH/log.generate" || exit 15
fi

MEMBER="$(tar -tzf "$SCRATCH/$OUTPUT" | grep -m1 '\.TXT\.events$' || true)"
[[ -n "$MEMBER" ]] || { echo "ERROR: archive lacks TXT.events member" >&2; exit 16; }
tar -xOf "$SCRATCH/$OUTPUT" "$MEMBER" > "$SCRATCH/validated.events"
python3 - "$SCRATCH/validated.events" "$NEVENTS" <<'PY'
import sys
from pathlib import Path
file=Path(sys.argv[1])
expected=int(sys.argv[2])
data=file.read_bytes()
count=data.count(b"<event>")
ends=data.count(b"</event>")
if count != expected or ends != expected or b"</LesHouchesEvents>" not in data:
    raise SystemExit(f"INVALID LHE count start={count} end={ends} expected={expected}")
print("AQP_FXFX_AB_LHE_VALIDATED", count)
PY
printf '%s\n' "$CASE" > "$OUT/variant"
printf '%s\n' "$NEVENTS" > "$OUT/lhe_count"
printf '%s\n' "$SEED" > "$OUT/seed"
echo "AQP_FXFX_AB_GENERATION_PASS CASE=$CASE LHE=$NEVENTS"
