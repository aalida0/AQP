#!/usr/bin/env bash
# Third DAG stage: validated 1000-LHE Delta441 -> Pythia8 FxFx -> EVNT.
# The input TXT was produced by the eight-core preceding DAG stage.
set -Eeuo pipefail
BASE=/data/aalida/AQP/Wjets/WENU
INPUTDIR="$BASE/smoke_tests/delta441_backup/delta441_clean_v1_8cpu_seed137_1000lhe"
INPUT="$INPUTDIR/delta441_clean_v1_seed137_1000lhe.TXT.tar.gz"
OUT="$BASE/smoke_tests/delta441_backup/delta441_clean_v1_seed137_fxfx_shower"
SCRATCH="${_CONDOR_SCRATCH_DIR:-}"
if [[ -z "$SCRATCH" || ! -d "$SCRATCH" ]]; then echo 'ERROR: missing worker scratch' >&2; exit 2; fi
SCRATCH="$(realpath "$SCRATCH")"
case "$SCRATCH/" in /data/*|/home/*) echo "ERROR: shared scratch"; exit 2;; esac
if [[ -e "$OUT" ]]; then echo "ERROR: refusing overwrite $OUT"; exit 3; fi
if [[ ! -s "$INPUT" ]]; then echo "ERROR: missing upstream TXT $INPUT"; exit 4; fi
if [[ ! -s "$SCRATCH/100004/mc.aMCPy8EG_Wenu_FxFx_2jets_D441_shower.py" ]]; then
  echo "ERROR: shower-only 100004 JO not transferred"; exit 5
fi
if [[ "$(cat "$INPUTDIR/runner_exit_code" 2>/dev/null)" != 0 ]]; then
  echo "ERROR: upstream generator was not successful"; exit 6
fi
mkdir -p "$OUT"
on_exit() {
  rc=$?
  trap - EXIT
  set +e
  echo "$rc" > "$OUT/runner_exit_code"
  for file in Gen_tf_shower.log log.generate runargs.generate.py jobReport.json prmon.summary.generate.json; do
    [[ -f "$SCRATCH/$file" ]] && cp -p "$SCRATCH/$file" "$OUT/"
  done
  [[ -s "$SCRATCH/delta441_clean_v1_seed137.EVNT.pool.root" ]] && \
    cp -p "$SCRATCH/delta441_clean_v1_seed137.EVNT.pool.root" "$OUT/"
  if [[ -f "$SCRATCH/Gen_tf_shower.log" ]]; then
    grep -Ei 'AQP_FXFX_SHOWER|JetMatching|FxFx|ERROR|FATAL|Segmentation fault|efficiency|accepted|rejected' \
      "$SCRATCH/Gen_tf_shower.log" | tail -n 200 > "$OUT/diagnostic_tail.txt"
  fi
  echo "AQP_DELTA441_FXFX_SHOWER_EXIT=$rc"; exit "$rc"
}
trap on_exit EXIT
trap 'exit 143' TERM
cd "$SCRATCH"

sha256sum "$INPUT" | tee "$OUT/upstream_Txt.sha256"
gzip -t "$INPUT"
member="$(tar -tzf "$INPUT" | grep -m1 -F '.TXT.events' || true)"
if [[ -z "$member" ]]; then echo "ERROR: cannot locate LHE in TXT archive"; exit 11; fi
tar -xOf "$INPUT" "$member" > delta441_1000lhe.events
open_count="$(grep -c '<event' delta441_1000lhe.events || true)"
close_count="$(grep -c '</event>' delta441_1000lhe.events || true)"
if [[ "$open_count" != 1000 || "$close_count" != 1000 ]]; then
  echo "ERROR: upstream LHE count mismatch: $open_count/$close_count"; exit 12
fi
grep -q '</LesHouchesEvents>' delta441_1000lhe.events
echo 'AQP_DELTA441_FXFX_SHOWER_INPUT_EVENTS=1000'

export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
set +e; set +u
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" > "$OUT/atlas_setup.log" 2>&1
als_rc=$?
if [[ "$als_rc" -eq 0 ]]; then
  asetup AthGeneration,23.6.63 >> "$OUT/atlas_setup.log" 2>&1
  setup_rc=$?
else setup_rc=99; fi
set -e; set -u
if [[ "$als_rc" -ne 0 || "$setup_rc" -ne 0 ]]; then
  echo "ERROR: AthGeneration setup failed"; tail -n 40 "$OUT/atlas_setup.log"; exit 13
fi
unset ATHENA_CORE_NUMBER
export OMP_NUM_THREADS=1
command -v Gen_tf.py >/dev/null

set +e
Gen_tf.py \
  --ecmEnergy=13000 \
  --maxEvents=200 \
  --firstEvent=1 \
  --randomSeed=3137 \
  --jobConfig="$SCRATCH/100004" \
  --inputGeneratorFile=delta441_1000lhe.events \
  --outputEVNTFile=delta441_clean_v1_seed137.EVNT.pool.root \
  --outputFileValidation=False \
  > Gen_tf_shower.log 2>&1
ret=$?
set -e
echo "AQP_DELTA441_FXFX_SHOWER_TRANSFORM_EXIT=$ret"
if [[ "$ret" -ne 0 ]]; then
  tail -n 60 Gen_tf_shower.log
  exit "$ret"
fi
if [[ ! -s delta441_clean_v1_seed137.EVNT.pool.root ]]; then
  echo "ERROR: EVNT file missing"; exit 21
fi
grep -q 'AQP_FXFX_SHOWER_MADGRAPH_NOT_INVOKED' log.generate || {
  echo "ERROR: shower-only JO marker missing"; exit 22;
}
grep -q 'Adding user hook JetMatchingMadgraph' log.generate || {
  echo "ERROR: FxFx user hook missing"; exit 23;
}
echo "AQP_DELTA441_CLEAN_1000LHE_TO_FXFX_EVNT_PASS"
