#!/usr/bin/env bash
# Non-destructive 1,982-file Wenu D441 equivalent remerge after excluding
# two identified -1 pb cross-section records. Run via Condor (one job).
# Explicit exit-status checks; no global shell strict-mode flags.
VIEW=/cvmfs/sft.cern.ch/lcg/views/LCG_108a_ATLAS_9/x86_64-el9-gcc14-opt/setup.sh
if [ ! -r "$VIEW" ]; then
    echo "ERROR: coherent LCG Rivet/YODA view unavailable: $VIEW" >&2
    exit 3
fi
source "$VIEW" || exit $?
command -v rivet-merge || exit 3
python3 -c 'import rivet, yoda; print("AQP_RIVET_YODA_IMPORT_OK")' || exit 3

# The worker runs in a transferred sandbox containing the three Python files.
python3 aqp_vjets_remerge_wenu_d441.py --execute \
    --json /data/aalida/AQP_Rivet_full/outputs/wenu_d441_xsec_full_20261123.json \
    --outdir /data/aalida/AQP_Rivet_full/outputs/physics_remerge_Wenu_D441_validXS_20261123
RC=$?
echo "AQP_D441_REMERGE_RC=$RC"
exit "$RC"
