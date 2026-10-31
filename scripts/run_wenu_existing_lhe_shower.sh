#!/usr/bin/env bash
# Shower-only Wenu FxFx 1000-LHE smoke. Condor worker scratch only.
# Never runs MadGraph/MINT or touches the original process or gridpack.
set -Eeuo pipefail
CFG="$1"; EXPECTED_SHA="$2"
case "$CFG" in
  standard111) SEED=3311 ;;
  delta111) SEED=3321 ;;
  delta221) SEED=3322 ;;
  *) echo "ERROR: unknown config" >&2; exit 2 ;;
esac
[[ "$EXPECTED_SHA" =~ ^[[:xdigit:]]{64}$ ]] || { echo "ERROR: invalid SHA" >&2; exit 2; }
SOURCE="/home/aalida/AQP/Wjets/WENU/$CFG/PROCNLO_loop_sm-no_b_mass_0/Events/run_01/events.lhe.gz"
ROOT="/data/aalida/AQP/Wjets/WENU/production_pilot/wenu_recovered_lhe_shower_v1"
OUT="$ROOT/$CFG"
SCRATCH="$(printenv _CONDOR_SCRATCH_DIR || true)"
[[ -n "$SCRATCH" && -d "$SCRATCH" ]] || { echo "ERROR: Condor scratch required" >&2; exit 2; }
SCRATCH="$(realpath "$SCRATCH")"
case "$SCRATCH/" in /home/*|/data/*) echo "ERROR: shared scratch" >&2; exit 2;; esac
JO="$SCRATCH/100004/mc.aMCPy8EG_Wenu_FxFx_2jets_$CFG""_shower.py"
AUDIT="$SCRATCH/audit_wenu_delta441_lhe.py"
[[ -s "$JO" && -s "$AUDIT" && -s "$SOURCE" ]] || {
  echo "ERROR: JO, audit script, or LHE missing" >&2; exit 3;
}
[[ ! -e "$OUT" && ! -L "$OUT" ]] || { echo "ERROR: output exists; no retry" >&2; exit 4; }
mkdir -p "$ROOT"
mkdir "$OUT" || { echo "ERROR: concurrent output owner" >&2; exit 4; }
EVNT="wenu_$CFG""_recovered1000_seed$SEED.EVNT.pool.root"
on_exit() {
  rc=$?
  trap - EXIT
  set +e
  echo "$rc" > "$OUT/runner_exit_code"
  for f in Gen_tf_shower.log log.generate runargs.generate.py jobReport.json prmon.summary.generate.json; do
    [[ ! -f "$SCRATCH/$f" ]] || cp -p "$SCRATCH/$f" "$OUT/"
  done
  [[ ! -s "$SCRATCH/$EVNT" ]] || cp -p "$SCRATCH/$EVNT" "$OUT/"
  if [[ -f "$SCRATCH/Gen_tf_shower.log" ]]; then
    grep -Ei 'AQP_|JetMatching|FxFx|ERROR|FATAL|Traceback|efficiency|accepted|rejected' \
      "$SCRATCH/Gen_tf_shower.log" | tail -n 140 > "$OUT/diagnostic_tail.txt" || true
  fi
  echo "AQP_WENU_SHOWER_ONLY_EXIT=$rc"
  echo "AQP_WENU_SHOWER_ONLY_OUT=$OUT"
  exit "$rc"
}
trap on_exit EXIT
trap 'exit 143' TERM
cd "$SCRATCH"
SHA="$(sha256sum "$SOURCE" | awk '{print $1}')"
[[ "$SHA" == "$EXPECTED_SHA" ]] || { echo "ERROR: source SHA changed" >&2; exit 11; }
printf '%s  %s\n' "$SHA" "$SOURCE" > "$OUT/source_lhe.sha256"
gzip -t "$SOURCE" || exit 12
gzip -cd "$SOURCE" > recovered.events
python3 "$AUDIT" recovered.events --expected-events 1000 \
  --json-output="$OUT/lhe_weight_audit.json" || exit 13
echo "AQP_WENU_SOURCE_1000_LHE_VALIDATED=$CFG"
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
set +e; set +u
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" > "$OUT/atlas_setup.log" 2>&1
a_rc=$?
if [[ "$a_rc" -eq 0 ]]; then
  asetup AthGeneration,23.6.63 >> "$OUT/atlas_setup.log" 2>&1
  s_rc=$?
else
  s_rc=99
fi
set -e; set -u
[[ "$a_rc" -eq 0 && "$s_rc" -eq 0 ]] || {
  echo "ERROR: Athena setup failed" >&2; tail -n 30 "$OUT/atlas_setup.log" >&2; exit 14;
}
unset ATHENA_CORE_NUMBER
export OMP_NUM_THREADS=1
command -v Gen_tf.py >/dev/null
set +e
Gen_tf.py \
  --ecmEnergy=13000 --maxEvents=200 --firstEvent=1 --randomSeed="$SEED" \
  --jobConfig="$SCRATCH/100004" --inputGeneratorFile=recovered.events \
  --outputEVNTFile="$EVNT" --outputFileValidation=False \
  > Gen_tf_shower.log 2>&1
rc=$?
set -e
[[ "$rc" -eq 0 ]] || { tail -n 70 Gen_tf_shower.log >&2; exit "$rc"; }
[[ -s "$EVNT" && -s log.generate ]] || { echo "ERROR: EVNT/log missing" >&2; exit 21; }
grep -Fq "AQP_WENU_SHOWER_CONFIG=$CFG" log.generate || exit 22
grep -Fq 'AQP_FXFX_SHOWER_MADGRAPH_NOT_INVOKED' log.generate || exit 23
grep -Fq 'Adding user hook JetMatchingMadgraph' log.generate || exit 24
grep -Eq 'Number of events processed:[[:space:]]*200([[:space:]]|$)' log.generate || exit 25
echo "AQP_WENU_$CFG""_RECOVERED_1000LHE_TO_200EVNT_PASS"
