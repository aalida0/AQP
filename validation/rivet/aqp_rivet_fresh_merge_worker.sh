#!/usr/bin/env bash
VIEW=/cvmfs/sft.cern.ch/lcg/views/LCG_108a_ATLAS_9/x86_64-el9-gcc14-opt/setup.sh
source "$VIEW" || exit $?
python3 -c 'import rivet, yoda; print("RIVET_IMPORT_OK")' || exit 3
python3 aqp_rivet_fresh_merge.py --sample "$1"
RC=$?
echo "AQP_FRESH_MERGE_RC=$RC"
exit "$RC"
