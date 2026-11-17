#!/usr/bin/env bash
# Wenu FxFx patched S111 5k-event pilot, integration seed 817263.
# Submit from /home; execute under Condor worker-local scratch; copy results to /data.
# Intentionally avoid set -e, set -u, and pipefail.

if [[ "${1:-}" == "--worker" ]]; then
    STAGE="${2:-}"
    GP="${3:-}"
    OUT="${4:-}"
    SCRATCH="${_CONDOR_SCRATCH_DIR:-}"

    if [[ ! -d "$STAGE/299901" || ! -s "$GP" || -z "$SCRATCH" ]]; then
        echo "ERROR: missing JO, gridpack, or Condor scratch directory" >&2
        exit 2
    fi
    case "$SCRATCH" in
        /home/*|/data/*)
            echo "ERROR: refusing to generate events in shared storage: $SCRATCH" >&2
            exit 2
            ;;
    esac

    mkdir -p "$OUT" || exit 2
    cd "$SCRATCH" || exit 2
    cp -a "$STAGE/299901" "$SCRATCH/" || exit 2

    # Save whatever diagnostics exist, even when the transform fails.
    save_logs() {
        local file
        for file in setup.log gridpack_extract.log run.log log.generate pilot_metadata.txt; do
            if [[ -f "$file" ]]; then
                cp -f "$file" "$OUT/" || echo "WARNING: could not save $file" >&2
            fi
        done
    }

    export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
    source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" > setup.log 2>&1
    rc=$?
    if (( rc != 0 )); then save_logs; tail -50 setup.log; exit "$rc"; fi
    asetup AthGeneration,23.6.63 >> setup.log 2>&1
    rc=$?
    if (( rc != 0 )); then save_logs; tail -50 setup.log; exit "$rc"; fi

    if [[ ! -f "${PY8PATH:-}/lib/libpythia8.a" ]]; then
        for CANDIDATE in /cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/LCG_108a_ATLAS_9/MCGenerators/pythia8/*/x86_64-el9-gcc14-opt; do
            if [[ -f "$CANDIDATE/lib/libpythia8.a" ]]; then
                export PY8PATH="$CANDIDATE"
                break
            fi
        done
    fi
    if [[ ! -f "${PY8PATH:-}/lib/libpythia8.a" ]]; then
        echo "ERROR: Pythia8 static library unavailable" >&2
        save_logs
        exit 3
    fi

    export DATAPATH="$SCRATCH/299901:${DATAPATH:-}"

    # The input gridpack remains read-only on /data; unpack it locally.
    tar -xzf "$GP" > gridpack_extract.log 2>&1
    rc=$?
    if (( rc != 0 )) || [[ ! -s madevent/Cards/run_card.dat ]]; then
        echo "ERROR: gridpack extraction failed" >&2
        save_logs
        tail -50 gridpack_extract.log
        exit 4
    fi

    printf 'input_gridpack=%s\nworkdir=%s\nshower_seed=928431\nrequested_events=5000\nfirst_event=1\n' \
        "$GP" "$SCRATCH" > pilot_metadata.txt
    started=$(date +%s)

    Gen_tf.py --ecmEnergy=13000 --maxEvents=5000 --randomSeed=928431 \
        --firstEvent=1 --jobConfig=299901 --outputEVNTFile=EVNT.pool.root \
        > run.log 2>&1
    rc=$?

    printf 'wall_seconds=%s\ntransform_exit=%s\n' \
        "$(( $(date +%s) - started ))" "$rc" >> pilot_metadata.txt
    save_logs

    if (( rc != 0 )); then
        echo "ERROR: Gen_tf.py failed with status $rc" >&2
        tail -60 run.log
        exit "$rc"
    fi
    if [[ ! -s EVNT.pool.root || ! -s log.generate ]]; then
        echo "ERROR: missing EVNT.pool.root or log.generate" >&2
        exit 5
    fi

    if [[ -e "$OUT/EVNT.pool.root" ]]; then
        echo "ERROR: output already exists, refusing overwrite" >&2
        exit 6
    fi
    cp -p EVNT.pool.root "$OUT/EVNT.pool.root.partial" || exit 7
    mv "$OUT/EVNT.pool.root.partial" "$OUT/EVNT.pool.root" || exit 7

    echo "WENU_S111_SEED817263_PILOT_SUCCESS"
    exit 0
fi

if [[ "${1:-}" != "--submit" || $# -ne 1 ]]; then
    echo "Usage: bash scripts/wenu_s111_seed817263_pilot.sh --submit" >&2
    exit 2
fi

REPO=$(cd "$(dirname "$0")/.." && pwd -P) || exit 2
JO="$REPO/tests/wenu_s111_patched_explicit_seed/299901"
STAGE="$HOME/AQP_condor_runs/Wenu_S111_seed817263_pilot_5k"
OUT="/data/$USER/AQP/Wenu_S111_seed817263_pilot_5k"
GP="/data/$USER/gridpacks/tests-wenu_s111_patched_explicit_seed-299901/tests-wenu_s111_patched_explicit_seed-299901.5ZTi6X/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2_standard111_seedcheck.MG3511.GRID.tar.gz"

if [[ ! -d "$JO" || ! -s "$GP" ]]; then
    echo "ERROR: JO or gridpack is missing" >&2
    exit 2
fi
if ! command -v condor_submit >/dev/null 2>&1; then
    echo "ERROR: condor_submit is unavailable" >&2
    exit 2
fi
if [[ -e "$OUT/EVNT.pool.root" ]]; then
    echo "ERROR: pilot EVNT already exists; refusing to resubmit" >&2
    exit 2
fi
if [[ -e "$STAGE/submitted.ok" ]]; then
    echo "ERROR: previous pilot submission recorded; inspect condor_q before resubmitting" >&2
    exit 2
fi

mkdir -p "$STAGE" "$OUT" || exit 2
cp -a "$JO" "$STAGE/" || exit 2
cp "$0" "$STAGE/worker.sh" || exit 2

cat > "$STAGE/pilot.sub" <<EOF
universe = vanilla
executable = /bin/bash
arguments = $STAGE/worker.sh --worker $STAGE $GP $OUT
initialdir = $STAGE
getenv = True
should_transfer_files = NO
request_cpus = 1
request_memory = 8192 MB
request_disk = 32000 MB
output = $STAGE/condor.out
error = $STAGE/condor.err
log = $STAGE/condor.log
+JobBatchName = "WenuS111Seed817263Pilot"
queue 1
EOF

condor_submit "$STAGE/pilot.sub"
rc=$?
if (( rc != 0 )); then exit "$rc"; fi
printf 'submitted_at=%s\n' "$(date -Is)" > "$STAGE/submitted.ok"
printf 'SUBMISSION_DIR=%s\nWORKER_SCRATCH=_CONDOR_SCRATCH_DIR\nOUTPUT=%s\n' "$STAGE" "$OUT"
