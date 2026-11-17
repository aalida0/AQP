#!/usr/bin/env bash
# Single-job Wenu FxFx S111 5k-event pilot from the seed-817263 patched gridpack.
# No set -e, set -u, or pipefail; no Condor log on /data.

if [[ "${1:-}" == "--worker" ]]; then
    WORK="${2:-}"
    GP="${3:-}"
    if [[ ! -d "$WORK" || ! -s "$GP" || ! -f "$WORK/299901/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2_standard111_seedcheck.py" ]]; then
        echo "ERROR: missing workdir, gridpack, or staged JO" >&2
        exit 2
    fi
    cd "$WORK" || exit 2
    export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
    source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" > setup.log 2>&1
    rc=$?
    if (( rc != 0 )); then tail -60 setup.log; exit "$rc"; fi
    asetup AthGeneration,23.6.63 >> setup.log 2>&1
    rc=$?
    if (( rc != 0 )); then tail -60 setup.log; exit "$rc"; fi

    if [[ ! -f "${PY8PATH:-}/lib/libpythia8.a" ]]; then
        for CANDIDATE in /cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/LCG_108a_ATLAS_9/MCGenerators/pythia8/*/x86_64-el9-gcc14-opt; do
            if [[ -f "$CANDIDATE/lib/libpythia8.a" ]]; then
                export PY8PATH="$CANDIDATE"
                break
            fi
        done
    fi
    if [[ ! -f "${PY8PATH:-}/lib/libpythia8.a" ]]; then
        echo "ERROR: missing Pythia8 static library" >&2
        exit 3
    fi

    export DATAPATH="$WORK/299901:${DATAPATH:-}"
    if [[ -e "$WORK/madevent" || -e "$WORK/EVNT.pool.root" ]]; then
        echo "ERROR: pre-existing gridpack extraction or EVNT; refuse to overwrite" >&2
        exit 4
    fi
    tar -xzf "$GP" > gridpack_extract.log 2>&1
    rc=$?
    if (( rc != 0 )) || [[ ! -s madevent/Cards/run_card.dat ]]; then
        echo "ERROR: gridpack extraction failed" >&2
        tail -60 gridpack_extract.log
        exit 4
    fi

    printf 'input_gridpack=%s\nshower_seed=928431\nrequested_events=5000\nfirst_event=1\n' "$GP" > pilot_metadata.txt
    started=$(date +%s)
    Gen_tf.py --ecmEnergy=13000 --maxEvents=5000 --randomSeed=928431 \
        --firstEvent=1 --jobConfig=299901 --outputEVNTFile=EVNT.pool.root \
        > run.log 2>&1
    rc=$?
    printf 'wall_seconds=%s\nexit_code=%s\n' "$(( $(date +%s) - started ))" "$rc" >> pilot_metadata.txt
    if (( rc != 0 )); then
        echo "ERROR: Gen_tf failed with status $rc" >&2
        tail -70 run.log
        exit "$rc"
    fi
    if [[ ! -s EVNT.pool.root || ! -s log.generate ]]; then
        echo "ERROR: missing EVNT.pool.root or log.generate" >&2
        exit 5
    fi
    echo "WENU_S111_SEED817263_PILOT_SUCCESS"
    exit 0
fi

if [[ "${1:-}" != "--submit" || $# -ne 1 ]]; then
    echo "Usage: bash scripts/wenu_s111_seed817263_pilot.sh --submit" >&2
    exit 2
fi

REPO=$(cd "$(dirname "$0")/.." && pwd -P) || exit 2
SAMPLE="$REPO/tests/wenu_s111_patched_explicit_seed/299901"
PACKDIR="/data/$USER/gridpacks/tests-wenu_s111_patched_explicit_seed-299901/tests-wenu_s111_patched_explicit_seed-299901.5ZTi6X"
WORK="/data/$USER/AQP/Wenu_S111_seed817263_pilot_5k"
LOGDIR="$HOME/AQP_condor_logs"
GP="$PACKDIR/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2_standard111_seedcheck.MG3511.GRID.tar.gz"
if [[ ! -d "$SAMPLE" || ! -s "$GP" ]]; then
    echo "ERROR: JO directory or gridpack missing" >&2
    exit 2
fi
if ! command -v condor_submit >/dev/null 2>&1; then
    echo "ERROR: condor_submit unavailable" >&2
    exit 2
fi
if [[ -e "$WORK/EVNT.pool.root" || -e "$WORK/madevent" ]]; then
    echo "ERROR: pilot already started; not resubmitting" >&2
    exit 2
fi
mkdir -p "$WORK" "$LOGDIR" || exit 2
cp -a "$SAMPLE" "$WORK/" || exit 2
cp "$0" "$WORK/worker.sh" || exit 2

cat > "$WORK/pilot.sub" <<EOF
universe = vanilla
executable = /bin/bash
arguments = $WORK/worker.sh --worker $WORK $GP
initialdir = $WORK
getenv = True
should_transfer_files = NO
request_cpus = 1
request_memory = 8192 MB
request_disk = 16000 MB
output = $WORK/condor.out
error = $WORK/condor.err
log = $LOGDIR/Wenu_S111_seed817263_pilot_5k.log
+JobBatchName = "WenuS111Seed817263Pilot"
queue 1
EOF

condor_submit "$WORK/pilot.sub"
rc=$?
if (( rc != 0 )); then exit "$rc"; fi
printf 'WORK=%s\nGRIDPACK=%s\nLOG=%s\n' "$WORK" "$GP" "$LOGDIR/Wenu_S111_seed817263_pilot_5k.log"
