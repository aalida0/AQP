#!/usr/bin/env bash
# Delta441 25k-LHE production pilot: shower up to 5000 EVNT events.
# Does not run MadGraph or depend on the previous DAG's wrapper status.
set -Eeuo pipefail
BASE=/data/aalida/AQP/Wjets/WENU
LHE_DIR="$BASE/production_pilot/delta441_16cpu_seed237_25k_lhe"
INPUT="$LHE_DIR/delta441_clean_v1_seed237_25000lhe.TXT.tar.gz"
OUT="$BASE/production_pilot/delta441_seed237_fxfx_5000evnt"
SCRATCH="${_CONDOR_SCRATCH_DIR:-}"
[[ -n "$SCRATCH" && -d "$SCRATCH" ]] || { echo "ERROR: requires Condor scratch" >&2; exit 2; }
SCRATCH="$(realpath "$SCRATCH")"
case "$SCRATCH/" in /data/*|/home/*) echo "ERROR: shared scratch" >&2; exit 2;; esac
[[ ! -e "$OUT" ]] || { echo "ERROR: output exists: $OUT" >&2; exit 3; }
[[ -s "$INPUT" ]] || { echo "ERROR: missing source TXT archive" >&2; exit 4; }
[[ -s "$SCRATCH/100004/mc.aMCPy8EG_Wenu_FxFx_2jets_D441_shower.py" ]] || {
  echo "ERROR: missing shower-only JO" >&2; exit 5;
}
mkdir -p "$OUT"
save() {
  rc=$?
  trap - EXIT
  set +e
  printf '%s\n' "$rc" > "$OUT/runner_exit_code"
  for f in Gen_tf_shower.log log.generate jobReport.json runargs.generate.py prmon.summary.generate.json; do
    [[ -f "$SCRATCH/$f" ]] && cp -p "$SCRATCH/$f" "$OUT/"
  done
  [[ -s "$SCRATCH/seed237_pilot.EVNT.pool.root" ]] &&
    cp -p "$SCRATCH/seed237_pilot.EVNT.pool.root" "$OUT/"
  echo "AQP_SEED237_INDEPENDENT_SHOWER_EXIT=$rc"
  exit "$rc"
}
trap save EXIT
trap 'exit 143' TERM
cd "$SCRATCH"
sha256sum "$INPUT" > "$OUT/source_archive.sha256"
gzip -t "$INPUT"
member="$(tar -tzf "$INPUT" | grep -m1 -F '.TXT.events' || true)"
[[ -n "$member" ]] || { echo "ERROR: TXT tarball has no LHE event member" >&2; exit 11; }
tar -xOf "$INPUT" "$member" > seed237_pilot.events
open_count="$(grep -c '<event' seed237_pilot.events || true)"
close_count="$(grep -c '</event>' seed237_pilot.events || true)"
echo "AQP_SEED237_SOURCE_EVENT_TAGS_OPEN=${open_count}_CLOSE=${close_count}"
[[ "$open_count" == 25000 && "$close_count" == 25000 ]] || {
  echo "ERROR: expected 25000 complete LHE events" >&2; exit 12;
}
grep -q '</LesHouchesEvents>' seed237_pilot.events || {
  echo "ERROR: missing LHE closing marker" >&2; exit 13;
}
[[ -s "$LHE_DIR/validated_LHE.events" ]] || {
  echo "ERROR: missing saved upstream LHE verification copy" >&2; exit 14;
}
cmp -s seed237_pilot.events "$LHE_DIR/validated_LHE.events" || {
  echo "ERROR: archived LHE differs from original extraction" >&2; exit 15;
}
[[ -s "$LHE_DIR/lhe_weight_audit.json" ]] || {
  echo "ERROR: upstream LHE weight audit missing" >&2; exit 16;
}
grep -q '"status": "PASS"' "$LHE_DIR/lhe_weight_audit.json" || {
  echo "ERROR: upstream LHE audit did not pass" >&2; exit 17;
}
[[ "$(cat "$LHE_DIR/runner_exit_code" 2>/dev/null)" == 0 ]] || {
  echo "ERROR: upstream 16-core pilot did not complete successfully" >&2; exit 18;
}
[[ -s "$LHE_DIR/log.generate" ]] || { echo "ERROR: missing original log" >&2; exit 16; }
grep -q 'AQP_DELTA441_LHE_EVENTS_REQUESTED=25000' "$LHE_DIR/log.generate" || {
  echo "ERROR: generator request marker absent" >&2; exit 17;
}
grep -q 'AQP_DELTA441_PARALLEL_CONFIG_VERIFIED_MODE=2_NB_CORE=16' "$LHE_DIR/log.generate" || {
  echo "ERROR: multicore configuration marker absent" >&2; exit 18;
}
echo "AQP_SEED237_SAVED_ARCHIVE_LHE_VALIDATED"

export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
set +e; set +u
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" > "$OUT/atlas_setup.log" 2>&1
als_rc=$?
if [[ "$als_rc" -eq 0 ]]; then
  asetup AthGeneration,23.6.63 >> "$OUT/atlas_setup.log" 2>&1
  setup_rc=$?
else
  setup_rc=99
fi
set -e; set -u
if [[ "$als_rc" -ne 0 || "$setup_rc" -ne 0 ]]; then
  echo "ERROR: ATLAS environment setup failed" >&2
  tail -n 40 "$OUT/atlas_setup.log"
  exit 19
fi
unset ATHENA_CORE_NUMBER
export OMP_NUM_THREADS=1
command -v Gen_tf.py >/dev/null

set +e
Gen_tf.py \
  --ecmEnergy=13000 \
  --maxEvents=5000 \
  --firstEvent=1 \
  --randomSeed=3237 \
  --jobConfig="$SCRATCH/100004" \
  --inputGeneratorFile=seed237_pilot.events \
  --outputEVNTFile=seed237_pilot.EVNT.pool.root \
  --outputFileValidation=False \
  > Gen_tf_shower.log 2>&1
rc=$?
set -e
if [[ "$rc" -ne 0 ]]; then tail -n 80 Gen_tf_shower.log >&2; exit "$rc"; fi
[[ -s seed237_pilot.EVNT.pool.root ]] || {
  echo "ERROR: no EVNT produced" >&2; exit 21;
}
grep -q 'AQP_FXFX_SHOWER_MADGRAPH_NOT_INVOKED' log.generate || {
  echo "ERROR: JO marker missing" >&2; exit 22;
}
grep -q 'Adding user hook JetMatchingMadgraph' log.generate || {
  echo "ERROR: FxFx matching hook missing" >&2; exit 23;
}
if ! grep -Eq 'Number of events processed:[[:space:]]*5000([[:space:]]|$)' log.generate; then
  echo "ERROR: Athena did not report 5000 processed events" >&2
  exit 24
fi
echo "AQP_DELTA441_16CORE_SEED237_5000_FXFX_EVNT_PASS"
