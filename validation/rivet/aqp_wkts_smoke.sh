#!/usr/bin/env bash
# Run on an AF worker; no set -e, set -u, or FileSystemDomain requirements.
# Compiles the isolated plugin using the same Rivet used by Athena.
BASE="$HOME/AQP/validation/rivet"
ROOT="/data/aalida/AQP_Rivet_full"
PLUGINS="$BASE/_wkts_probe"
RESULTS="$ROOT/outputs/_wkts_probe"
INPUTS="$ROOT/inputs/Wenu/delta441"

export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh"
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR ATLAS_LOCAL_SETUP=$RC"; exit "$RC"; fi

asetup AthGeneration,23.6.63
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR ASETUP=$RC"; exit "$RC"; fi

for TOOL in rivet-build athena.py; do
    command -v "$TOOL"
    RC=$?
    if [ "$RC" -ne 0 ]; then echo "ERROR MISSING_TOOL=$TOOL"; exit "$RC"; fi
done

if [ ! -f "$BASE/AQP_WKTSPLITTINGS.cc" ]; then
    echo "ERROR source not found: $BASE/AQP_WKTSPLITTINGS.cc"
    exit 2
fi

mkdir -p "$PLUGINS" "$RESULTS"
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR MKDIR=$RC"; exit "$RC"; fi

rivet-build "$PLUGINS/RivetAQP_WKTSPLITTINGS.so" "$BASE/AQP_WKTSPLITTINGS.cc"
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR RIVET_BUILD=$RC"; exit "$RC"; fi

INPUT=$(find "$INPUTS" -type f -name '*.EVNT.pool.root' -print -quit)
if [ -z "$INPUT" ]; then echo "ERROR NO_WENU_D441_EVNT=$INPUTS"; exit 3; fi

OUT="$RESULTS/AQP_WKTSPLITTINGS_Wenu_delta441_smoke.yoda.gz"
if [ -e "$OUT" ]; then
    echo "ERROR OUTPUT_ALREADY_EXISTS=$OUT"
    echo "Inspect or move the previous smoke output before rerunning."
    exit 4
fi

export AQP_RIVET_INPUT="$INPUT"
export AQP_RIVET_OUTPUT="$OUT"
export AQP_RIVET_PLUGIN_DIR="$PLUGINS"
export RIVET_ANALYSIS_PATH="$PLUGINS"
echo "AQP_WKTS_EVNT=$INPUT"
echo "AQP_WKTS_SHARED_LIBRARY=$PLUGINS/RivetAQP_WKTSPLITTINGS.so"

cd "$PLUGINS"
athena.py "$BASE/aqp_wkts_smoke_evnt.py"
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
