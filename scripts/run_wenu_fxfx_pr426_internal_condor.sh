#!/usr/bin/env bash
# Wenu Standard111 FxFx PR426 A/B with MadGraph internal Condor.
# Foreground launcher for persistent tmux terminal; never reuses gridpacks.
set -Eeuo pipefail
CASE="$1"
LHE_COUNT="$2"
SEED="$3"
case "$CASE" in before|after) ;; *) echo "Usage: $0 before|after 200|50000 SEED" >&2; exit 2 ;; esac
case "$LHE_COUNT" in 200|50000) ;; *) echo "ERROR: LHE count must be 200 or 50000" >&2; exit 2 ;; esac
case "$SEED" in ""|*[!0-9]*) echo "ERROR: seed must be numeric" >&2; exit 2 ;; esac
if [[ -z "$(printenv MADPATH || true)" || -z "$(printenv PY8PATH || true)" ]]; then
    echo "ERROR: first run 'asetup AthGeneration,23.6.63' in this terminal" >&2
    exit 3
fi
command -v Gen_tf.py >/dev/null || { echo "ERROR: Gen_tf.py unavailable" >&2; exit 3; }
command -v condor_submit >/dev/null || { echo "ERROR: Condor CLI unavailable" >&2; exit 3; }
command -v condor_q >/dev/null || { echo "ERROR: Condor query unavailable" >&2; exit 3; }

# New workspace keyed by compile cores; never reuse old one-core process.
COMPILE_CORES="$(printenv AQP_FXFX_AB_COMPILE_CORES || true)"
COMPILE_CORES="${COMPILE_CORES:-4}"
case "$COMPILE_CORES" in 4|16|24|32) ;; *)
    echo "ERROR: AQP_FXFX_AB_COMPILE_CORES must be 4, 16, 24, or 32" >&2; exit 6 ;;
esac
case "$(hostname -s)" in
  login*|head*)
    if (( COMPILE_CORES > 4 )); then
        echo "ERROR: shared AF login/head allows at most four local compile cores." >&2
        echo "24 compilation cores require a separately authorized host." >&2
        exit 6
    fi ;;
  *)
    AVAILABLE_CPUS="$(nproc)"
    if (( AVAILABLE_CPUS < COMPILE_CORES )); then
        echo "ERROR: visible CPUs ($AVAILABLE_CPUS) < requested $COMPILE_CORES" >&2
        exit 6
    fi ;;
esac
export AQP_FXFX_AB_COMPILE_CORES="$COMPILE_CORES"
echo "AQP_FXFX_AB_COMPILE_CORES=$COMPILE_CORES"

REPO=/home/aalida/AQP/aqp-production-audit
SOURCE=/home/aalida/AQP/Wjets/WENU/standard111/100000
BASE=/home/aalida/AQP/fxfx_pr426_standard111_internal
WORK="$BASE/$CASE""_$LHE_COUNT""_seed$SEED""_compile$COMPILE_CORES"
JO="mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_$CASE.py"
for input in "$REPO/joboptions/wenu_fxfx_pr426_internal_condor/$CASE/100006/$JO" \
    "$REPO/scripts/aqp_prepare_fxfx_exclusive_kt_patch.py" \
    "$SOURCE/dummy_fct.f" "$SOURCE/montecarlocounter_MINE.f"; do
    [[ -s "$input" ]] || { echo "ERROR: missing $input" >&2; exit 4; }
done
if [[ -e "$WORK" || -L "$WORK" ]]; then
    echo "ERROR: work directory already exists: $WORK" >&2; exit 5;
fi
if [[ "$LHE_COUNT" == 50000 ]]; then
    for version in before after; do
        smoke="$BASE/$version""_200_seed311""_compile$COMPILE_CORES/runner_exit_code"
        [[ -f "$smoke" && "$(cat "$smoke")" == 0 ]] || {
            echo "ERROR: missing passing 200-LHE smoke for $version: $smoke" >&2
            exit 5
        }
    done
fi
mkdir -p "$WORK/100006"
cp -p "$REPO/joboptions/wenu_fxfx_pr426_internal_condor/$CASE/100006/$JO" "$WORK/100006/"
cp -p "$REPO/scripts/aqp_prepare_fxfx_exclusive_kt_patch.py" "$WORK/"
cp -p "$SOURCE/dummy_fct.f" "$SOURCE/montecarlocounter_MINE.f" "$WORK/"
cd "$WORK"
export AQP_FXFX_AB_INPUT_DIR="$WORK"
unset ATHENA_CORE_NUMBER
export OMP_NUM_THREADS=1
git -C "$REPO" rev-parse HEAD > source_commit.txt
sha256sum "100006/$JO" aqp_prepare_fxfx_exclusive_kt_patch.py \
    dummy_fct.f montecarlocounter_MINE.f > staged_inputs.sha256

OUTPUT="wenu_standard111_fxfx_pr426_$CASE""_seed$SEED""_$LHE_COUNT""lhe.TXT.tar.gz"
MAX_EVENTS=$((LHE_COUNT / 5))
echo "CASE=$CASE LHE=$LHE_COUNT seed=$SEED"
echo "WORK=$WORK"
echo "Internal MG Condor unpatched: run_mode=1 cluster_size=100; compile cores=$COMPILE_CORES"
echo "Testing FxFx PR426 only; not testing the Condor scheduler patch"
echo "Requested --maxEvents=$MAX_EVENTS (JO converts to $LHE_COUNT LHE)"

record_exit() {
    local rc=$?
    trap - EXIT
    printf '%s\n' "$rc" > "$WORK/runner_exit_code"
    echo "AQP_FXFX_AB_TERMINAL_EXIT=$rc CASE=$CASE LHE=$LHE_COUNT"
}
trap record_exit EXIT

set +e
Gen_tf.py \
    --ecmEnergy=13000 \
    --maxEvents="$MAX_EVENTS" \
    --firstEvent=1 \
    --randomSeed="$SEED" \
    --jobConfig="$WORK/100006" \
    --outputTXTFile="$OUTPUT" \
    --outputFileValidation=False \
    > Gen_tf.log 2>&1
rc=$?
set -e
echo "Gen_tf exit=$rc"
if [[ "$rc" -ne 0 ]]; then
    tail -n 80 Gen_tf.log >&2
    echo "IMPORTANT: inspect internal Condor children and reconcile before retry."
    exit "$rc"
fi
[[ -s "$OUTPUT" && -s log.generate ]] || {
    echo "ERROR: missing TXT archive or log.generate" >&2; exit 7;
}
grep -Fq "AQP_FXFX_AB_CASE=$CASE" log.generate || exit 8
grep -Fq 'AQP_FXFX_AB_INTERNAL_CONDOR_MODE=1_CLUSTER_SIZE=100' log.generate || exit 8
grep -Fq "AQP_FXFX_AB_COMPILE_CORES=$COMPILE_CORES" log.generate || exit 8
grep -Fq "AQP_FXFX_AB_REQUESTED_LHE=$LHE_COUNT""_REQ_ACC=0.1" log.generate || exit 8
if [[ "$CASE" == after ]]; then
    grep -Fq 'AQP_FXFX_AB_PR426_ENABLED=True' log.generate || exit 8
else
    grep -Fq 'AQP_FXFX_AB_PR426_ENABLED=False' log.generate || exit 8
fi
python3 - "$OUTPUT" "$LHE_COUNT" <<'PY'
import sys,tarfile
from pathlib import Path
file=Path(sys.argv[1]); expected=int(sys.argv[2])
with tarfile.open(file,"r:gz") as archive:
    members=[m for m in archive.getmembers() if m.name.endswith(".TXT.events")]
    if len(members)!=1:
        raise SystemExit("BAD_TXT_ARCHIVE_MEMBERS "+repr([m.name for m in members]))
    f=archive.extractfile(members[0])
    if f is None: raise SystemExit("CANNOT_READ_TXT_MEMBER")
    data=f.read()
count=data.count(b"<event>"); ends=data.count(b"</event>")
if count!=expected or ends!=expected or b"</LesHouchesEvents>" not in data:
    raise SystemExit(f"BAD_LHE_COUNT start={count} end={ends}, expected={expected}")
print(f"AQP_FXFX_AB_LHE_VALIDATED {count}")
PY
echo "AQP_FXFX_AB_INTERNAL_CONDOR_COMPLETE_CASE=$CASE"
