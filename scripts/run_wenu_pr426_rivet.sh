#!/usr/bin/env bash
# bash scripts/run_wenu_pr426_rivet.sh before|after 200|18000
# Execute only on an authorized compute host with local scratch.
set -Eeuo pipefail
CASE="${1:-}"
NEVENTS="${2:-200}"
case "$CASE" in before|after) ;; *) echo 'Usage: run_wenu_pr426_rivet.sh before|after [200|18000]' >&2; exit 2;; esac
case "$NEVENTS" in 200|18000) ;; *) echo 'Use 200 smoke or 18000 full' >&2; exit 2;; esac
REPO="$HOME/AQP/aqp-production-audit"
TOP=/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_shower
SRC="$TOP/${CASE}_accepted18000_seed13311_verified/wenu_pr426_${CASE}_accepted18000.EVNT.pool.root"
OUT="$TOP/rivet_pr426_jetdr/${CASE}_${NEVENTS}"
[[ -s "$SRC" && -s "$REPO/rivet/pr426/AQP_PR426_JETS.cc" ]] || {
  echo 'Missing source EVNT or Rivet plugin source' >&2; exit 3;
}
command -v athena.py >/dev/null || { echo 'Run asetup AthGeneration,23.6.63 first' >&2; exit 4; }
command -v rivet-buildplugin >/dev/null || { echo 'Missing rivet-buildplugin in active environment' >&2; exit 4; }
[[ ! -e "$OUT/$CASE.yoda.gz" ]] || { echo 'Existing YODA; refusing overwrite' >&2; exit 5; }
SCRATCH_BASE=/scratch
[[ -d "$SCRATCH_BASE" && -w "$SCRATCH_BASE" ]] || SCRATCH_BASE=/tmp
WORK="$(mktemp -d "$SCRATCH_BASE/aqp_pr426_${CASE}_${NEVENTS}_XXXXXX")"
echo "LOCAL_SCRATCH=$WORK"
cp -p "$SRC" "$WORK/input.EVNT.pool.root"
cmp -s "$SRC" "$WORK/input.EVNT.pool.root" || { echo 'EVNT copy mismatch' >&2; exit 6; }
cd "$WORK"
rivet-buildplugin RivetAQP_PR426_JETS.so "$REPO/rivet/pr426/AQP_PR426_JETS.cc" > plugin_build.log 2>&1 || {
  tail -n 70 plugin_build.log >&2; echo "BUILD_FAILED SCRATCH=$WORK" >&2; exit 7;
}
export AQP_PR426_EVNT="$WORK/input.EVNT.pool.root"
export AQP_PR426_PLUGIN_DIR="$WORK"
export AQP_PR426_YODA="$CASE.yoda.gz"
export AQP_PR426_MAX_EVENTS="$NEVENTS"
export OMP_NUM_THREADS=1
unset ATHENA_CORE_NUMBER
set +e
athena.py "$REPO/rivet/pr426/read_evnt.py" > athena_rivet.log 2>&1
RC=$?
set -e
if [[ "$RC" != 0 || ! -s "$CASE.yoda.gz" ]]; then
  tail -n 75 athena_rivet.log >&2
  echo "RIVET_FAILED EXIT=$RC SCRATCH=$WORK" >&2
  exit 8
fi
mkdir -p "$OUT"
for F in "$CASE.yoda.gz" athena_rivet.log plugin_build.log; do
  [[ ! -e "$OUT/$F" && ! -e "$OUT/$F.copying" ]] || {
    echo "Destination already exists: $OUT/$F" >&2; exit 9;
  }
  cp -p "$F" "$OUT/$F.copying"
  cmp -s "$F" "$OUT/$F.copying" || { echo "Copy mismatch: $F" >&2; exit 10; }
  mv "$OUT/$F.copying" "$OUT/$F"
done
sha256sum "$OUT/$CASE.yoda.gz" > "$OUT/$CASE.yoda.gz.sha256"
echo "AQP_PR426_RIVET_PASS CASE=$CASE EVENTS=$NEVENTS YODA=$OUT/$CASE.yoda.gz"
echo "Scratch retained at $WORK; remove manually after checking outputs."
