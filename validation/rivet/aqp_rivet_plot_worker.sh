#!/usr/bin/env bash
# Compare three merged Rivet v2 YODA files from one process (Condor worker).
# No set -e, no set -u and no HTCondor filesystem-domain constraint.
PROC="$1"
case "$PROC" in
 Zee|Wenu) ;;
 *) echo "ERROR: invalid process $PROC"; exit 2 ;;
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


ROOT="/data/aalida/AQP_Rivet"
STD="$ROOT/$PROC/standard111/merged/${PROC}_standard111_v2_nominal_shapes.yoda.gz"
D111="$ROOT/$PROC/delta111/merged/${PROC}_delta111_v2_nominal_shapes.yoda.gz"
D221="$ROOT/$PROC/delta221/merged/${PROC}_delta221_v2_nominal_shapes.yoda.gz"
PLOTDIR="$ROOT/$PROC/plots/shape_comparison_v2"

for F in "$STD" "$D111" "$D221"; do
    if [ ! -s "$F" ]; then
        echo "ERROR: Missing or empty merged YODA: $F"
        exit 4
    fi
done

command -v rivet-mkhtml
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR: rivet-mkhtml missing"; exit "$RC"; fi

# Confirm same analyses are present in the three outputs.
python3 - "$STD" "$D111" "$D221" <<'PY'
import sys
import yoda
collections = []
for file_name in sys.argv[1:]:
    result = yoda.read(file_name)
    keys = {key for key in result if key.startswith(("/MC_ZJETS/", "/MC_ZINC/", "/MC_WJETS/", "/MC_WINC/"))}
    print(f"YODA_CHECK {file_name} total_objects={len(result)} mc_histograms={len(keys)}")
    if not keys:
        raise RuntimeError("No MC_Z/W analysis histograms found")
    collections.append(keys)
common = set.intersection(*collections)
print(f"YODA_COMMON_HISTOGRAMS={len(common)}")
if not common:
    raise RuntimeError("No common histograms across Standard111, Delta111, Delta221")
PY
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR: merged YODA integrity check failed"; exit "$RC"; fi

mkdir -p "$(dirname "$PLOTDIR")"
echo "AQP_RIVET_PLOT_DIR=$PLOTDIR"

# Unit-area normalized comparisons. Histograms with zero/negative integral
# may be non-normalizable: inspect the Rivet warnings and skip their interpretation.
# Cross section in the Rivet-i production JO was 1.0 (not physical pb).
rivet-mkhtml \
    -o "$PLOTDIR" \
    "$STD:Title=Standard111" \
    "$D111:Title=Delta111" \
    "$D221:Title=Delta221" \
    "PLOT:NormalizeToIntegral=1" \
    > "$ROOT/$PROC/plots/rivet_mkhtml_v2.log" 2>&1
RC=$?
echo "AQP_RIVET_PLOT_EXIT=$RC process=$PROC output=$PLOTDIR"
if [ "$RC" -ne 0 ]; then
    tail -60 "$ROOT/$PROC/plots/rivet_mkhtml_v2.log"
    exit "$RC"
fi
if [ ! -s "$PLOTDIR/index.html" ]; then
    echo "WARNING: plot command returned success but index.html was not found; inspect output directory"
    ls -la "$PLOTDIR" | head -30
fi
