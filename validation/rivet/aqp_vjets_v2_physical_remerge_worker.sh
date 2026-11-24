#!/usr/bin/env bash
# Run in Condor scratch. The originals and previous merged YODA remain unchanged.
VIEW=/cvmfs/sft.cern.ch/lcg/views/LCG_108a_ATLAS_9/x86_64-el9-gcc14-opt/setup.sh
if [ ! -r "$VIEW" ]; then
  echo "Missing LCG Rivet view $VIEW" >&2
  exit 3
fi
source "$VIEW" || exit $?
python3 -c 'import rivet, yoda; print("RIVET_IMPORT_OK")' || exit 3
python3 aqp_vjets_v2_physical_remerge.py \
  --report /home/aalida/AQP/v2_log_yoda_xsec_match_FULL.json \
  --sample "$1" \
  --max-files "$2" \
  --logdir "$PWD" \
  --execute
RC=$?
echo "AQP_V2_XSEC_REMERGE_RC=$RC"
exit "$RC"
