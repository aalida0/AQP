#!/usr/bin/env bash
# Wenu FxFx PR426 shower-only: no MadGraph, integration or gridpack.
# Run in a dedicated working directory; one CPU is sufficient.
set -Eeuo pipefail
CASE="$1"; EVENTS="$2"; INPUT="$3"
case "$CASE" in before|after) ;; *) echo "Usage: $0 before|after 200|18000 FILE.lhe.gz" >&2; exit 2;; esac
case "$EVENTS" in 200|18000) ;; *) echo "ERROR: choose 200 or 18000 accepted EVNT" >&2; exit 2;; esac
[[ "$INPUT" == /* && -s "$INPUT" ]] || { echo "ERROR: absolute existing input required" >&2; exit 2; }
case "$INPUT" in
  /home/aalida/AQP/fxfx_pr426_standard111_internal/*/PROCNLO_loop_sm-no_b_mass_0/Events/run_pr426_50k_seed411/events.lhe.gz) ;;
  *) echo "ERROR: not an expected saved PR426 50k LHE" >&2; exit 2;;
esac
ROOT=/home/aalida/AQP/aqp-production-audit
JO="$ROOT/joboptions/wenu_fxfx_pr426_shower/100007/mc.aMCPy8EG_Wenu_FxFx_2jets_PR426_shower.py"
[[ -s "$JO" ]] || { echo "ERROR: shower JO missing" >&2; exit 3; }
if [[ "$EVENTS" == 18000 ]]; then
  # Pythia is serial, and unlike MadGraph integration needs no inner Condor.
  # Run the long shower on one external Condor worker and stage output to /data.
  SCRATCH="$(printenv _CONDOR_SCRATCH_DIR || true)"
  [[ -n "$SCRATCH" && -d "$SCRATCH" ]] || {
    echo "ERROR: 18000-event shower requires an outer Condor worker" >&2; exit 3;
  }
  WORK="$(realpath "$SCRATCH")"
  case "$WORK/" in /home/*|/data/*) echo "ERROR: scratch is shared" >&2; exit 3;; esac
  OUT="/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_shower/$CASE""_accepted$EVENTS""_seed13311"
  [[ ! -e "$OUT" && ! -L "$OUT" ]] || {
    echo "ERROR: persistent output exists: $OUT" >&2; exit 4;
  }
  mkdir -p "$(dirname "$OUT")"
  mkdir "$OUT"
else
  WORK="/home/aalida/AQP/fxfx_pr426_standard111_shower/$CASE""_accepted$EVENTS""_seed13311"
  OUT="$WORK"
  [[ ! -e "$WORK" && ! -L "$WORK" ]] || {
    echo "ERROR: workdir already exists: $WORK" >&2; exit 4;
  }
  mkdir -p "$WORK"
fi
mkdir -p "$WORK/100007"
cp -p "$JO" "$WORK/100007/"
cd "$WORK"
sha256sum "$INPUT" > source_lhe.sha256
gzip -t "$INPUT"
gzip -cd "$INPUT" > input.events

export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
# atlasLocalSetup/asetup warn and may misbehave if bash errexit (-e) is active.
# Disable -e/-u ONLY while sourcing, check return codes, then restore both.
set +e
set +u
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh"
atlas_setup_rc=$?
if (( atlas_setup_rc == 0 )); then
  asetup AthGeneration,23.6.63
  athgen_setup_rc=$?
else
  athgen_setup_rc=99
fi
set -u
set -e
if (( atlas_setup_rc != 0 || athgen_setup_rc != 0 )); then
  echo "ERROR: ATLAS setup failed (atlas=$atlas_setup_rc, asetup=$athgen_setup_rc)" >&2
  exit 12
fi
command -v Gen_tf.py >/dev/null || { echo "ERROR: Gen_tf.py missing after setup" >&2; exit 12; }
export AQP_FXFX_PR426_CASE="$CASE"
export OMP_NUM_THREADS=1
unset ATHENA_CORE_NUMBER
EVNT="wenu_pr426_$CASE""_accepted$EVENTS.EVNT.pool.root"
record_exit() {
  rc=$?
  trap - EXIT
  set +e
  if [[ "$OUT" != "$WORK" ]]; then
    for name in Gen_tf_shower.log log.generate jobReport.json runargs.generate.py \
                prmon.summary.generate.json source_lhe.sha256; do
      [[ -f "$WORK/$name" ]] && cp -p "$WORK/$name" "$OUT/" || true
    done
    if [[ -s "$WORK/$EVNT" ]]; then
      cp -p "$WORK/$EVNT" "$OUT/" || rc=81
    elif [[ "$rc" == 0 ]]; then
      rc=82
    fi
  fi
  echo "$rc" > "$OUT/runner_exit_code"
  echo "AQP_FXFX_PR426_SHOWER_EXIT=$rc OUT=$OUT"
  exit "$rc"
}
trap record_exit EXIT
set +e
Gen_tf.py --ecmEnergy=13000 --maxEvents="$EVENTS" --firstEvent=1 \
  --randomSeed=13311 --jobConfig="$WORK/100007" \
  --inputGeneratorFile=input.events --outputEVNTFile="$EVNT" \
  --outputFileValidation=False > Gen_tf_shower.log 2>&1
rc=$?
set -e
if [[ "$rc" != 0 ]]; then
 tail -n 70 Gen_tf_shower.log >&2
 exit "$rc"
fi
[[ -s "$EVNT" && -s log.generate ]] || { echo "ERROR: missing EVNT/log" >&2; exit 10; }
for marker in "AQP_FXFX_PR426_SHOWER_CASE=$CASE" \
              "AQP_FXFX_PR426_SHOWER_MADGRAPH_NOT_INVOKED" \
              "AQP_FXFX_PR426_SHOWER_FXFX_NJETMAX=2_QCUT=20_A14" \
              "Adding user hook JetMatchingMadgraph"; do
 grep -Fq "$marker" log.generate || { echo "ERROR: missing $marker" >&2; exit 11; }
done
echo "AQP_FXFX_PR426_SHOWER_PASS=$CASE $EVENTS"
echo "EVNT=$WORK/$EVNT"
