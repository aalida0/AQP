#!/usr/bin/env bash
# Merge Rivet outputs for one completed v2 sample (Condor worker).
# No set -e, no set -u and no HTCondor filesystem-domain constraint.
PROC="$1"
CFG="$2"
case "$PROC:$CFG" in
 Zee:standard111|Zee:delta111|Zee:delta221|Wenu:standard111|Wenu:delta111|Wenu:delta221) ;;
 *) echo "ERROR: invalid completed-v2 process/config: $PROC $CFG"; exit 2 ;;
esac

export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" >/dev/null 2>&1
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR: ATLAS setup failed ($RC)"; exit "$RC"; fi

# Use Rivet/YODA from the same LCG build as Athena 23.6.63.
# Prefer the coherent LCG view, fallback to AthGeneration with matching modules.
ARCH=x86_64-el9-gcc14-opt
LCG=LCG_108a_ATLAS_9
VIEW="/cvmfs/sft.cern.ch/lcg/views/$LCG/$ARCH/setup.sh"
BASE="/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/$LCG"

if [ -r "$VIEW" ]; then
    echo "RIVET_ENV=LCG_VIEW $VIEW"
    source "$VIEW"
    RC=$?
    if [ "$RC" -ne 0 ]; then echo "ERROR: LCG view setup failed ($RC)"; exit "$RC"; fi
else
    echo "RIVET_ENV=ATHGEN_FALLBACK"
    asetup AthGeneration,23.6.63 >/dev/null 2>&1
    RC=$?
    if [ "$RC" -ne 0 ]; then echo "ERROR: AthGeneration setup failed ($RC)"; exit "$RC"; fi

    RIVET_PREFIX=""
    for CANDIDATE in "$BASE"/MCGenerators/rivet/*/"$ARCH"; do
        if [ -f "$CANDIDATE/bin/rivet-merge" ]; then
            RIVET_PREFIX="$CANDIDATE"
            break
        fi
    done
    if [ -z "$RIVET_PREFIX" ]; then
        echo "ERROR: rivet-merge not found under $BASE/MCGenerators/rivet"
        exit 3
    fi
    export PATH="$RIVET_PREFIX/bin:$PATH"
    export LD_LIBRARY_PATH="$RIVET_PREFIX/lib:${LD_LIBRARY_PATH:-}"

    YODA_PREFIX=""
    for CANDIDATE in "$BASE"/MCGenerators/yoda/*/"$ARCH" "$BASE"/MCGenerators/YODA/*/"$ARCH"; do
        if [ -x "$CANDIDATE/bin/yoda-config" ]; then
            YODA_PREFIX="$CANDIDATE"
            break
        fi
    done
    if [ -n "$YODA_PREFIX" ]; then
        export PATH="$YODA_PREFIX/bin:$PATH"
        export LD_LIBRARY_PATH="$YODA_PREFIX/lib:$LD_LIBRARY_PATH"
    fi

    # rivet-merge is a Python script: both imports must succeed.
    for PREFIX in "$RIVET_PREFIX" "$YODA_PREFIX"; do
        if [ -z "$PREFIX" ]; then continue; fi
        for PYPATH in "$PREFIX"/lib/python*/site-packages "$PREFIX"/lib64/python*/site-packages; do
            if [ -d "$PYPATH" ]; then export PYTHONPATH="$PYPATH:${PYTHONPATH:-}"; fi
        done
    done
    if command -v rivet-config >/dev/null 2>&1; then
        PYPATH=$(rivet-config --pythonpath 2>/dev/null)
        if [ -d "$PYPATH" ]; then export PYTHONPATH="$PYPATH:${PYTHONPATH:-}"; fi
    fi
    if command -v yoda-config >/dev/null 2>&1; then
        PYPATH=$(yoda-config --pythonpath 2>/dev/null)
        if [ -d "$PYPATH" ]; then export PYTHONPATH="$PYPATH:${PYTHONPATH:-}"; fi
    fi
fi

command -v rivet-merge
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR: missing rivet-merge after setup"; exit 3; fi

python3 -c 'import rivet, yoda; print("RIVET_YODA_PYTHON_IMPORT_OK")'
RC=$?
if [ "$RC" -ne 0 ]; then
    echo "ERROR: matching Rivet/YODA Python modules unavailable; refusing an incompatible merge"
    exit "$RC"
fi

python3 aqp_rivet_stream.py \
    --root /data/aalida/AQP_Rivet \
    --job-options "$PWD/aqp_rivet_evnt_job.py" \
    --process "$PROC" \
    --config "$CFG" \
    --versions v2 \
    --merge-only
RC=$?
echo "AQP_RIVET_MERGE_EXIT=$RC process=$PROC config=$CFG"
exit "$RC"
