#!/usr/bin/env bash
# One-job Wenu FxFx patched S111 5k pilot: transfer inputs to worker scratch.
# No set -e, set -u, or pipefail. Condor submit/logs in /home, not /data.

PACK="mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2_standard111_seedcheck.MG3511.GRID.tar.gz"

if [[ "${1:-}" == "--worker" ]]; then
    # With should_transfer_files=YES, current directory is Condor local scratch.
    # The stage directory, JO, and gridpack arrive as transfer_input_files.
    finish() {
        rc=$?
        trap - EXIT
        printf 'worker_exit_code=%s\n' "$rc" >> pilot_metadata.txt
        files=(pilot_metadata.txt setup.log gridpack_extract.log run.log log.generate)
        if [[ -s EVNT.pool.root ]]; then
            files+=(EVNT.pool.root)
        fi
        tar -cf pilot_output.tar "${files[@]}"
        save_rc=$?
        if (( save_rc != 0 )); then
            echo "ERROR: could not package Condor output files" >&2
            exit 90
        fi
        exit "$rc"
    }
    touch pilot_metadata.txt setup.log gridpack_extract.log run.log log.generate
    trap finish EXIT

    if [[ ! -d 299901 || ! -s "$PACK" ]]; then
        echo "ERROR: Condor did not transfer JO or gridpack to worker scratch" >&2
        exit 2
    fi
    SCRATCH="$(pwd -P)"
    printf 'input_gridpack=%s\nworkdir=%s\nshower_seed=928431\nrequested_events=5000\nfirst_event=1\n' \
        "$PACK" "$SCRATCH" > pilot_metadata.txt

    export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
    source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" > setup.log 2>&1
    rc=$?
    if (( rc != 0 )); then echo "ERROR: ATLAS environment setup failed" >&2; tail -50 setup.log; exit "$rc"; fi
    asetup AthGeneration,23.6.63 >> setup.log 2>&1
    rc=$?
    if (( rc != 0 )); then echo "ERROR: AthGeneration setup failed" >&2; tail -50 setup.log; exit "$rc"; fi

    if [[ ! -f "${PY8PATH:-}/lib/libpythia8.a" ]]; then
        for CANDIDATE in /cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/LCG_108a_ATLAS_9/MCGenerators/pythia8/*/x86_64-el9-gcc14-opt; do
            if [[ -f "$CANDIDATE/lib/libpythia8.a" ]]; then
                export PY8PATH="$CANDIDATE"
                break
            fi
        done
    fi
    if [[ ! -f "${PY8PATH:-}/lib/libpythia8.a" ]]; then
        echo "ERROR: Pythia8 static library missing" >&2
        exit 3
    fi

    export DATAPATH="$SCRATCH/299901:${DATAPATH:-}"
    tar -xzf "$PACK" > gridpack_extract.log 2>&1
    rc=$?
    if (( rc != 0 )) || [[ ! -s madevent/Cards/run_card.dat ]]; then
        echo "ERROR: gridpack extraction failed ($rc)" >&2
        tail -50 gridpack_extract.log
        exit 4
    fi

    started=$(date +%s)
    Gen_tf.py --ecmEnergy=13000 --maxEvents=5000 --randomSeed=928431 \
        --firstEvent=1 --jobConfig=299901 --outputEVNTFile=EVNT.pool.root \
        > run.log 2>&1
    rc=$?
    printf 'wall_seconds=%s\ntransform_exit=%s\n' \
        "$(( $(date +%s) - started ))" "$rc" >> pilot_metadata.txt
    if (( rc != 0 )); then
        echo "ERROR: Gen_tf.py failed with status $rc" >&2
        tail -60 run.log
        exit "$rc"
    fi
    if [[ ! -s EVNT.pool.root || ! -s log.generate ]]; then
        echo "ERROR: EVNT or log.generate missing" >&2
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
JO="$REPO/tests/wenu_s111_patched_explicit_seed/299901"
STAGE="$HOME/AQP_condor_runs/Wenu_S111_seed817263_pilot_5k_transfer"
OUT="/data/$USER/AQP/Wenu_S111_seed817263_pilot_5k"
GRID="/data/$USER/gridpacks/tests-wenu_s111_patched_explicit_seed-299901/tests-wenu_s111_patched_explicit_seed-299901.5ZTi6X/$PACK"

if [[ ! -d "$JO" || ! -s "$GRID" ]]; then
    echo "ERROR: JO directory or gridpack missing" >&2
    exit 2
fi
if ! command -v condor_submit >/dev/null 2>&1; then
    echo "ERROR: condor_submit unavailable" >&2
    exit 2
fi
if [[ -e "$STAGE/submitted.ok" || -e "$OUT/pilot_output.tar" ]]; then
    echo "ERROR: submission or output already exists; inspect before retrying" >&2
    exit 2
fi
mkdir -p "$STAGE" "$OUT" || exit 2
cp -a "$JO" "$STAGE/" || exit 2
cp "$0" "$STAGE/worker.sh" || exit 2

cat > "$STAGE/pilot.sub" <<EOF
universe = vanilla
executable = /bin/bash
arguments = worker.sh --worker
initialdir = $STAGE
getenv = True
should_transfer_files = YES
when_to_transfer_output = ON_EXIT
transfer_input_files = $STAGE/worker.sh,$STAGE/299901,$GRID
transfer_output_files = pilot_output.tar
request_cpus = 1
request_memory = 8192 MB
request_disk = 32000 MB
output = $STAGE/condor.out
error = $STAGE/condor.err
log = $STAGE/condor.log
+JobBatchName = "WenuS111Seed817263PilotTransfer"
queue 1
EOF

condor_submit "$STAGE/pilot.sub"
rc=$?
if (( rc != 0 )); then exit "$rc"; fi
printf 'submitted_at=%s\n' "$(date -Is)" > "$STAGE/submitted.ok"
printf 'SUBMISSION_DIR=%s\nOUTPUT_ARCHIVE=%s\nFINAL_OUTPUT_DIR=%s\n' "$STAGE" "$STAGE/pilot_output.tar" "$OUT"
