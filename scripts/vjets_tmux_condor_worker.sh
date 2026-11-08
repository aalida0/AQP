#!/usr/bin/env bash
# Executed inside a single tmux controller; original gridpack remains untouched.
set -Eeuo pipefail
(( $# == 1 )) || { echo "usage: worker SESSION_ENV" >&2; exit 2; }
source "$1"
: "${VJETS_RUN:?}" "${VJETS_OUT:?}" "${VJETS_PACK:?}" "${VJETS_SEED:?}" "${VJETS_EVENTS:?}"
: "${VJETS_PROC:?}" "${VJETS_CFG:?}" "${VJETS_DSID:?}"
: "${AQP_CLUSTER_CANDIDATE:?}" "${AQP_CONDOR_GUARD_DIR:?}"
cd "$VJETS_RUN"
start=$(date +%s)
printf 'start_epoch=%s\n' "$start" > "$VJETS_OUT/timing.txt"
finish() {
  rc=$?
  trap - EXIT
  printf 'end_epoch=%s\nwall_seconds=%s\nexit_code=%s\n' "$(date +%s)" "$(( $(date +%s) - start ))" "$rc" >> "$VJETS_OUT/timing.txt"
  printf '%s\n' "$rc" > "$VJETS_OUT/exit_code.txt"
  for f in run.log log.generate tmp_LHE_events.tar.gz; do
    if [[ -s "$f" ]]; then
      cp -f "$f" "$VJETS_OUT/$f" || echo "COPY_FAILED=$f" >&2
    fi
  done
}
trap finish EXIT
[[ -s "$VJETS_PACK" ]] || { echo 'Missing gridpack' >&2; exit 2; }
shopt -s nullglob
jos=("jo/$VJETS_DSID"/mc.*.py)
(( ${#jos[@]} == 1 )) && [[ -s "${jos[0]}" ]] || { echo "Missing JO" >&2; exit 2; }
export DATAPATH="$VJETS_RUN/jo/$VJETS_DSID:${DATAPATH:-}"
export EVENT_USE_CONDOR=1
python3 -c 'import madgraph.various.cluster as c; assert hasattr(c,"_aqp_states"); print("CONDOR_BACKEND_OK")'
echo "Extracting $VJETS_PACK"
tar -xzf "$VJETS_PACK"
test -f madevent/bin/aMCatNLO
test -f madevent/Cards/run_card.dat
output="${VJETS_PROC}.${VJETS_CFG}.seed${VJETS_SEED}.EVNT.pool.root"
set +e
{ time Gen_tf.py --ecmEnergy=13000 --maxEvents="$VJETS_EVENTS" \
    --randomSeed="$VJETS_SEED" --firstEvent=1 \
    --jobConfig="$VJETS_RUN/jo/$VJETS_DSID" \
    --outputEVNTFile="$output" 2>&1 | tee run.log; } 2> "$VJETS_OUT/controller_cpu.txt"
rc=$?
set -e
if (( rc != 0 )); then echo "Gen_tf failed with $rc" >&2; exit "$rc"; fi
[[ -s "$output" ]] || { echo "Missing output EVNT" >&2; exit 3; }
cp -f "$output" "$VJETS_OUT/$output"
echo "GEN_TF_SUCCESS: $output"
