#!/usr/bin/env bash
# AQP Grid event generation, 5000 EVNT per job, using untouched main JOs.
# No set -e, set -u, or pipefail by request.

GP="$1"
DSID="$2"
SEED="$3"
BASE="$4"
EVTS=5000
TIMING=generation_timing.txt

if [ "$#" -ne 4 ]; then
    echo 'Usage: bash vjets_grid_2m_worker.sh GRIDPACK DSID SEED BASE'
    exit 2
fi

case "$DSID" in
    100000|100001|100002|100003|200000|200001|200002|200003) ;;
    *) echo "ERROR: invalid DSID $DSID"; exit 2 ;;
esac
case "$SEED:$BASE" in
    *[!0-9:]*|:*) echo 'ERROR: nonnumeric seed/base'; exit 2 ;;
esac

FIRST=$(( 1 + (SEED - BASE) * EVTS ))
if [ "$FIRST" -lt 1 ] || [ "$FIRST" -gt 2000000 ]; then
    echo "ERROR: first event $FIRST outside production range"
    exit 2
fi
if [ ! -s "$GP" ]; then
    echo "ERROR: gridpack unavailable: $GP"
    exit 3
fi
case "$(basename "$GP")" in
    mc_13TeV*.GRID.tar.gz) ;;
    *) echo "ERROR: unexpected gridpack basename: $GP"; exit 3 ;;
esac
if ! compgen -G "$DSID/mc.*.py" >/dev/null; then
    echo "ERROR: main JO missing for DSID $DSID"
    exit 3
fi

printf 'dsid=%s\nrequested_accepted_events=%s\nseed=%s\nseed_base=%s\nfirst_event=%s\ngridpack=%s\n' \
    "$DSID" "$EVTS" "$SEED" "$BASE" "$FIRST" "$(basename "$GP")" > "$TIMING"

ALL_START=$(date +%s)
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" > setup.log 2>&1
RC=$?
if [ "$RC" -ne 0 ]; then
    echo "ERROR: atlasLocalSetup failed ($RC)"
    tail -40 setup.log
    exit "$RC"
fi
asetup AthGeneration,23.6.63 >> setup.log 2>&1
RC=$?
if [ "$RC" -ne 0 ]; then
    echo "ERROR: asetup failed ($RC)"
    tail -40 setup.log
    exit "$RC"
fi
if ! command -v Gen_tf.py >/dev/null 2>&1; then
    echo 'ERROR: Gen_tf.py unavailable'
    exit 3
fi

# The successful 5k Grid test used the AthGeneration CVMFS Pythia8 static lib.
if [ ! -f "${PY8PATH:-}/lib/libpythia8.a" ]; then
    for CANDIDATE in /cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/LCG_108a_ATLAS_9/MCGenerators/pythia8/*/x86_64-el9-gcc14-opt; do
        if [ -f "$CANDIDATE/lib/libpythia8.a" ]; then
            export PY8PATH="$CANDIDATE"
            break
        fi
    done
fi
if [ ! -f "${PY8PATH:-}/lib/libpythia8.a" ]; then
    echo 'ERROR: Pythia8 static library missing'
    exit 3
fi
printf 'environment_setup_seconds=%s\n' "$(( $(date +%s) - ALL_START ))" >> "$TIMING"

EXTRACT_START=$(date +%s)
tar -xzf "$GP" > extract.log 2>&1
RC=$?
printf 'gridpack_extract_seconds=%s\n' "$(( $(date +%s) - EXTRACT_START ))" >> "$TIMING"
if [ "$RC" -ne 0 ] || [ ! -f madevent/bin/aMCatNLO ] || [ ! -f madevent/Cards/run_card.dat ]; then
    echo "ERROR: gridpack extraction failed ($RC)"
    tail -40 extract.log
    exit 4
fi

GEN_START=$(date +%s)
/usr/bin/time \
    -f 'gen_wall_seconds_gnu=%e\ngen_user_cpu_seconds=%U\ngen_system_cpu_seconds=%S\ngen_max_rss_kb=%M' \
    -o gen_tf_time.txt \
    Gen_tf.py \
        --ecmEnergy=13000 \
        --maxEvents="$EVTS" \
        --randomSeed="$SEED" \
        --firstEvent="$FIRST" \
        --jobConfig="$DSID" \
        --outputEVNTFile=EVNT.pool.root \
        > run.log 2>&1
RC=$?
printf 'gen_wall_seconds=%s\ngen_exit_code=%s\n' "$(( $(date +%s) - GEN_START ))" "$RC" >> "$TIMING"
if [ -f gen_tf_time.txt ]; then
    cat gen_tf_time.txt >> "$TIMING"
fi
cat "$TIMING"
if [ "$RC" -ne 0 ]; then
    echo "ERROR: Gen_tf failed ($RC)"
    tail -60 run.log
    exit "$RC"
fi
if [ ! -s EVNT.pool.root ] || [ ! -s log.generate ]; then
    echo 'ERROR: EVNT.pool.root or log.generate missing'
    exit 5
fi
echo 'AQP_GRID_PRODUCTION_JOB_SUCCESS'
