#!/usr/bin/env bash
# ATLAS-style plotting only. No Athena setup, Rivet execution, or YODA merge.
# No set -e, set -u, or pipefail (ATLAS shells may inject unset variables).
AQP_MPLHEP_PYTHON="/home/aalida/.venvs/aqp-mplhep/bin/python"
AQP_MPLHEP_SCRIPT="/home/aalida/AQP/validation/rivet/aqp_vjets_mplhep_plot.py"
AQP_MPLHEP_SOURCE="/data/aalida/AQP_Rivet_full/outputs/Vjets_final_plots_20261118"
AQP_MPLHEP_OUTPUT="/data/aalida/AQP_Rivet_full/outputs/Vjets_mplhep_rivet_preserved_20261120"

if [ ! -x "$AQP_MPLHEP_PYTHON" ]; then
  echo "ERROR MPLHEP_PYTHON_MISSING=$AQP_MPLHEP_PYTHON"
  exit 2
fi
if [ ! -f "$AQP_MPLHEP_SCRIPT" ]; then
  echo "ERROR MPLHEP_SCRIPT_MISSING=$AQP_MPLHEP_SCRIPT"
  exit 2
fi
if [ ! -d "$AQP_MPLHEP_SOURCE" ]; then
  echo "ERROR MPLHEP_SOURCE_MISSING=$AQP_MPLHEP_SOURCE"
  exit 2
fi

"$AQP_MPLHEP_PYTHON" -c "import mplhep, matplotlib, numpy"
RC=$?
if [ "$RC" -ne 0 ]; then echo "ERROR MPLHEP_IMPORT=$RC"; exit "$RC"; fi
"$AQP_MPLHEP_PYTHON" "$AQP_MPLHEP_SCRIPT" \
  --source "$AQP_MPLHEP_SOURCE" \
  --output "$AQP_MPLHEP_OUTPUT"
RC=$?
echo "AQP_MPLHEP_PLOT_EXIT=$RC"
if [ "$RC" -ne 0 ]; then exit "$RC"; fi
if [ ! -s "$AQP_MPLHEP_OUTPUT/index.html" ]; then
  echo "ERROR MPLHEP_INDEX_MISSING"
  exit 5
fi
echo "AQP_MPLHEP_PLOTS_PASS=$AQP_MPLHEP_OUTPUT/index.html"
