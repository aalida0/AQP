#!/usr/bin/env bash
# Isolated W kT "MET" lookup-key control, not full production.
# Uses the same Wenu D441 EVNT as cluster 4303710.
# No 'set -e', 'set -u', or 'pipefail': Athena setup uses shell variables.
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh"
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR ATLAS_LOCAL_SETUP=$RC"; exit "$RC"; fi
asetup AthGeneration,23.6.63
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR ASETUP=$RC"; exit "$RC"; fi

AQP_WKTS_SOURCE_DIR="/home/aalida/AQP/validation/rivet"
AQP_WKTS_OUTPUT_DIR="/data/aalida/AQP_Rivet_full/outputs/_wkts_probe"
AQP_WKTS_INPUT_DIR="/data/aalida/AQP_Rivet_full/inputs/Wenu/delta441"
AQP_WKTS_PLUGIN_DIR="$AQP_WKTS_SOURCE_DIR/_wkts_probe"
AQP_WKTS_YODA="$AQP_WKTS_OUTPUT_DIR/AQP_WKTSPLITTINGS_METKEY_Wenu_delta441.yoda.gz"

if [ ! -f "$AQP_WKTS_SOURCE_DIR/AQP_WKTSPLITTINGS_METKEY.cc" ] ||
   [ ! -f "$AQP_WKTS_SOURCE_DIR/aqp_wkts_smoke_evnt.py" ]; then
  echo "ERROR METKEY_SOURCE_MISSING=$AQP_WKTS_SOURCE_DIR"
  exit 2
fi
if [ -e "$AQP_WKTS_YODA" ]; then
  echo "ERROR METKEY_OUTPUT_EXISTS=$AQP_WKTS_YODA"
  exit 3
fi
AQP_WKTS_INPUT=$(find "$AQP_WKTS_INPUT_DIR" -type f -name '*.EVNT.pool.root' -print -quit)
if [ -z "$AQP_WKTS_INPUT" ]; then
  echo "ERROR METKEY_INPUT_MISSING=$AQP_WKTS_INPUT_DIR"
  exit 4
fi
mkdir -p "$AQP_WKTS_PLUGIN_DIR" "$AQP_WKTS_OUTPUT_DIR"
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR MKDIR=$RC"; exit "$RC"; fi

cd "$AQP_WKTS_PLUGIN_DIR"
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR CD_PLUGIN_DIR=$RC"; exit "$RC"; fi

rivet-build "$AQP_WKTS_PLUGIN_DIR/RivetAQP_WKTSPLITTINGS_METKEY.so" \
  "$AQP_WKTS_SOURCE_DIR/AQP_WKTSPLITTINGS_METKEY.cc"
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR METKEY_BUILD=$RC"; exit "$RC"; fi

export AQP_RIVET_INPUT="$AQP_WKTS_INPUT"
export AQP_RIVET_PLUGIN_DIR="$AQP_WKTS_PLUGIN_DIR"
export RIVET_ANALYSIS_PATH="$AQP_WKTS_PLUGIN_DIR"
export AQP_RIVET_OUTPUT="$AQP_WKTS_YODA"
export AQP_WKTS_ANALYSIS="AQP_WKTSPLITTINGS_METKEY"

echo "AQP_METKEY_INPUT=$AQP_WKTS_INPUT"
athena.py "$AQP_WKTS_SOURCE_DIR/aqp_wkts_smoke_evnt.py"
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR METKEY_ATHENA=$RC"; exit "$RC"; fi
if [ ! -s "$AQP_WKTS_YODA" ]; then echo "ERROR METKEY_OUTPUT_MISSING"; exit 5; fi
gzip -t "$AQP_WKTS_YODA"
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR METKEY_GZIP=$RC"; exit "$RC"; fi
gzip -cd "$AQP_WKTS_YODA" | grep -m 1 -F 'AQP_WKTSPLITTINGS_METKEY:LMODE=EL/log10_d_01'
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR METKEY_HISTOGRAM_MISSING"; exit 6; fi

echo "AQP_WKTS_METKEY_PASS=$AQP_WKTS_YODA"
