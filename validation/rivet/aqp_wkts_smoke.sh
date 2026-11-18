#!/usr/bin/env bash
# Run on an AF worker; no set -e, set -u, or FileSystemDomain requirements.
# Compiles the isolated plugin using the same Rivet used by Athena.
# Avoid the generic variable BASE: LCG/Athena setup overwrites it.
ROOT="/data/aalida/AQP_Rivet_full"
RESULTS="$ROOT/outputs/_wkts_probe"
INPUTS="$ROOT/inputs/Wenu/delta441"

export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh"
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR ATLAS_LOCAL_SETUP=$RC"; exit "$RC"; fi

asetup AthGeneration,23.6.63
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR ASETUP=$RC"; exit "$RC"; fi

# Define AQP-specific paths AFTER asetup so the toolchain cannot clobber them.
AQP_WKTS_SOURCE_DIR="/home/aalida/AQP/validation/rivet"
PLUGINS="$AQP_WKTS_SOURCE_DIR/_wkts_probe"

for TOOL in rivet-build athena.py; do
    command -v "$TOOL"
    RC=$?
    if [ "$RC" -ne 0 ]; then echo "ERROR MISSING_TOOL=$TOOL"; exit "$RC"; fi
done

if [ ! -d "$INPUTS" ]; then echo "ERROR NO_WENU_INPUT_DIR=$INPUTS"; exit 3; fi
INPUT=$(find "$INPUTS" -type f -name '*.EVNT.pool.root' -print -quit)
if [ -z "$INPUT" ]; then echo "ERROR NO_WENU_D441_EVNT=$INPUTS"; exit 3; fi

mkdir -p "$PLUGINS" "$RESULTS"
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR MKDIR=$RC"; exit "$RC"; fi

if [ ! -f "$AQP_WKTS_SOURCE_DIR/aqp_wkts_smoke_evnt.py" ]; then
    echo "ERROR ATHENA_JOBOPTIONS_MISSING=$AQP_WKTS_SOURCE_DIR/aqp_wkts_smoke_evnt.py"
    exit 2
fi
echo "AQP_WKTS_SOURCE_DIR=$AQP_WKTS_SOURCE_DIR"
echo "AQP_WKTS_RUNTIME_HOME=${HOME:-unset}"

export AQP_RIVET_INPUT="$INPUT"
export AQP_RIVET_PLUGIN_DIR="$PLUGINS"
export RIVET_ANALYSIS_PATH="$PLUGINS"
cd "$PLUGINS"
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR PLUGIN_CWD=$PLUGINS"; exit "$RC"; fi

# Control: does the official MC_WKTSPLITTINGS work in isolation?
OFFICIAL_OUT="$RESULTS/MC_WKTSPLITTINGS_Wenu_delta441_isolated.yoda.gz"
if [ -e "$OFFICIAL_OUT" ]; then
    echo "ERROR OUTPUT_ALREADY_EXISTS=$OFFICIAL_OUT"
    echo "Inspect or move the previous smoke output before rerunning."
    exit 4
fi
export AQP_WKTS_ANALYSIS=MC_WKTSPLITTINGS
export AQP_RIVET_OUTPUT="$OFFICIAL_OUT"
echo "AQP_WKTS_CONTROL=official analysis only"
echo "AQP_WKTS_EVNT=$INPUT"
athena.py "$AQP_WKTS_SOURCE_DIR/aqp_wkts_smoke_evnt.py"
RC=$?
if [ "$RC" -eq 0 ] && [ -s "$OFFICIAL_OUT" ]; then
    gzip -t "$OFFICIAL_OUT"
    GZ_RC=$?
    gzip -cd "$OFFICIAL_OUT" | grep -m 1 -E '^Path: /MC_WKTSPLITTINGS(:|/)'
    YODA_RC=$?
    if [ "$GZ_RC" -eq 0 ] && [ "$YODA_RC" -eq 0 ]; then
        echo "AQP_WKTS_OFFICIAL_ISOLATED_PASS=$OFFICIAL_OUT"
        echo "NEXT: use official plugin as a dedicated analysis (not co-scheduled)."
        exit 0
    fi
fi

echo "AQP_WKTS_OFFICIAL_ISOLATED_FAILED exit=$RC"
echo "Testing alternate AQP plugin with unique MET and lepton projection keys."

if [ ! -f "$AQP_WKTS_SOURCE_DIR/AQP_WKTSPLITTINGS.cc" ]; then
    echo "ERROR source not found: $AQP_WKTS_SOURCE_DIR/AQP_WKTSPLITTINGS.cc"
    exit 2
fi

rivet-build "$PLUGINS/RivetAQP_WKTSPLITTINGS.so" "$AQP_WKTS_SOURCE_DIR/AQP_WKTSPLITTINGS.cc"
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR RIVET_BUILD=$RC"; exit "$RC"; fi

OUT="$RESULTS/AQP_WKTSPLITTINGS_Wenu_delta441_smoke.yoda.gz"
if [ -e "$OUT" ]; then
    echo "ERROR OUTPUT_ALREADY_EXISTS=$OUT"
    echo "Inspect or move the previous smoke output before rerunning."
    exit 4
fi
export AQP_WKTS_ANALYSIS=AQP_WKTSPLITTINGS
export AQP_RIVET_OUTPUT="$OUT"
echo "AQP_WKTS_SHARED_LIBRARY=$PLUGINS/RivetAQP_WKTSPLITTINGS.so"
athena.py "$AQP_WKTS_SOURCE_DIR/aqp_wkts_smoke_evnt.py"
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR ATHENA_WKTS=$RC"; exit "$RC"; fi

if [ ! -s "$OUT" ]; then echo "ERROR NO_YODA_OUTPUT=$OUT"; exit 5; fi
gzip -t "$OUT"
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR BAD_GZIP=$RC"; exit "$RC"; fi

gzip -cd "$OUT" | grep -m 1 -E '^Path: /AQP_WKTSPLITTINGS(:|/)'
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR MISSING_WKTS_HISTOGRAM=$OUT"; exit 6; fi

echo "AQP_WKTS_SMOKE_PASS=$OUT"
exit 0
