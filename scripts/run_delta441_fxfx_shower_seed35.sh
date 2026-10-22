#!/usr/bin/env bash
# Shower the preserved Delta441 seed35 50-event LHE with Pythia8 FxFx.
# Runs on HTCondor worker scratch. Never extracts/runs the MG gridpack.
# Writes diagnostics and EVNT output to /data even if Athena fails.
set -euo pipefail

BASE=/data/aalida/AQP/Wjets/WENU
SOURCE="$BASE/smoke_tests/delta441_backup/interactive_linkfix/seed35/events.lhe.gz"
EXPECTED_SHA=e94be1450418afa260a8d412febe09f08256658e4f3e4a28e1cbb5740cd152d8
OUT="$BASE/smoke_tests/delta441_backup/seed35_fxfx_showeronly_run01"
SCRATCH="$(printenv _CONDOR_SCRATCH_DIR || true)"
if [[ -z "$SCRATCH" || ! -d "$SCRATCH" ]]; then
  echo "ERROR: run from a HTCondor worker with _CONDOR_SCRATCH_DIR" >&2
  exit 2
fi
SCRATCH="$(realpath "$SCRATCH")"
case "$SCRATCH/" in
  /home/*|/data/*)
    echo "ERROR: scratch cannot be a shared /home or /data mount" >&2
    exit 2 ;;
esac
if [[ -e "$OUT" ]]; then
  echo "ERROR: refusing to overwrite existing results $OUT" >&2
  exit 2
fi
if [[ ! -f "$SCRATCH/100004/mc.aMCPy8EG_Wenu_FxFx_2jets_D441_shower.py" ]]; then
  echo "ERROR: 100004 JO directory not transferred to worker scratch" >&2
  exit 3
fi
if [[ ! -s "$SOURCE" ]]; then
  echo "ERROR: preserved source LHE is missing: $SOURCE" >&2
  exit 4
fi

mkdir -p "$OUT"
preserve_results() {
  rc=$?
  trap - EXIT
  set +e
  printf '%s\n' "$rc" > "$OUT/runner_exit_code"
  for f in Gen_tf_shower.log log.generate jobReport.json runargs.generate.py prmon.summary.generate.json; do
    if [[ -f "$SCRATCH/$f" ]]; then cp -p "$SCRATCH/$f" "$OUT/"; fi
  done
  if [[ -f "$SCRATCH/seed35_fxfx.EVNT.pool.root" ]]; then
    cp -p "$SCRATCH/seed35_fxfx.EVNT.pool.root" "$OUT/"
  fi
  if [[ -f "$SCRATCH/Gen_tf_shower.log" ]]; then
    grep -E 'AQP_FXFX_SHOWER|JetMatching|FxFx|Pythia8.*(ERROR|FATAL)|SIGSEGV|Segmentation fault|ERROR|FATAL|Traceback|efficiency|accepted|success' \
      "$SCRATCH/Gen_tf_shower.log" | tail -n 180 > "$OUT/diagnostic_tail.txt"
  fi
  echo "AQP_FXFX_SHOWER_EXIT=$rc"
  echo "AQP_FXFX_SHOWER_RESULTS=$OUT"
  exit "$rc"
}
trap preserve_results EXIT
cd "$SCRATCH"

echo "AQP_FXFX_SHOWER_HOST=$(hostname)"
echo "AQP_FXFX_SHOWER_SCRATCH=$PWD"
echo "AQP_FXFX_SHOWER_LHE=$SOURCE"
echo "AQP_FXFX_SHOWER_OUTPUT=$OUT"

# The exact source hash was recorded after the original failed seed35
# transform. This prevents accidentally showering another sample.
actual_sha="$(sha256sum "$SOURCE" | awk '{print $1}')"
if [[ "$actual_sha" != "$EXPECTED_SHA" ]]; then
  echo "ERROR: seed35 LHE SHA256 mismatch: $actual_sha" >&2
  exit 20
fi
gzip -t "$SOURCE"
gzip -cd "$SOURCE" > seed35_fxfx.events
if ! grep -q '^<LesHouchesEvents' seed35_fxfx.events; then
  echo "ERROR: LHE opening tag missing" >&2
  exit 21
fi
n_open="$(grep -c '<event' seed35_fxfx.events || true)"
n_close="$(grep -c '</event>' seed35_fxfx.events || true)"
if [[ "$n_open" != 50 || "$n_close" != 50 ]]; then
  echo "ERROR: expected exactly 50 LHE events, got $n_open/$n_close" >&2
  exit 22
fi
if ! grep -q '</LesHouchesEvents>' seed35_fxfx.events; then
  echo "ERROR: LHE closing tag missing" >&2
  exit 23
fi
echo "AQP_FXFX_SHOWER_SOURCE_VALID=50_EVENTS"
echo "$actual_sha  $SOURCE" > "$OUT/source_lhe.sha256"

# Do not allow AthGeneration setup to exit due to shell -e/-u.
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
set +e
set +u
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" > "$OUT/atlas_setup.log" 2>&1
als_rc=$?
if [[ "$als_rc" -eq 0 ]]; then
  asetup AthGeneration,23.6.63 >> "$OUT/atlas_setup.log" 2>&1
  asetup_rc=$?
else
  asetup_rc=99
fi
set -e
set -u
if [[ "$als_rc" -ne 0 || "$asetup_rc" -ne 0 ]]; then
  echo "ERROR: ATLAS setup failed ($als_rc, $asetup_rc)" >&2
  tail -n 40 "$OUT/atlas_setup.log" >&2
  exit 30
fi
unset ATHENA_CORE_NUMBER
export OMP_NUM_THREADS=1
command -v Gen_tf.py >/dev/null

# The legacy GENtoEVGEN skeleton accepts a local *.events file directly.
# It discovers 'seed35_fxfx.events' by matching inputGeneratorFile to the
# event-file basename. No tar extraction or MG generation is needed.
set +e
Gen_tf.py \
  --ecmEnergy=13000 \
  --maxEvents=5 \
  --firstEvent=1 \
  --randomSeed=13535 \
  --jobConfig="$SCRATCH/100004" \
  --inputGeneratorFile=seed35_fxfx.events \
  --outputEVNTFile=seed35_fxfx.EVNT.pool.root \
  --outputFileValidation=False \
  > Gen_tf_shower.log 2>&1
rc=$?
set -e
echo "AQP_FXFX_SHOWER_TRANSFORM_EXIT=$rc"
if [[ "$rc" -ne 0 ]]; then
  tail -n 70 Gen_tf_shower.log
  exit "$rc"
fi
if [[ ! -s seed35_fxfx.EVNT.pool.root ]]; then
  echo "ERROR: transform returned success but EVNT output is missing" >&2
  exit 40
fi
if ! grep -q 'AQP_FXFX_SHOWER_MADGRAPH_NOT_INVOKED' log.generate; then
  echo "ERROR: standalone shower-only JO marker not found" >&2
  exit 41
fi
if ! grep -q 'JetMatchingMadgraph' log.generate; then
  echo "ERROR: FxFx JetMatchingMadgraph hook not visible in log" >&2
  exit 42
fi
echo "AQP_FXFX_SHOWER_REAL_LHE_TO_EVNT_PASS"
