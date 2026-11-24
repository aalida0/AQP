#!/usr/bin/env bash
# Each job processes one deterministic shard of the frozen EVNT/log manifest.
AQP_SCRATCH="$PWD"
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" || exit $?
asetup AthGeneration,23.6.63 || exit $?
lsetup rucio || exit $?
cd "$AQP_SCRATCH" || exit $?
rucio whoami || exit $?
python3 aqp_rivet_fresh_full.py --sample "$1" --shard "$2"
RC=$?
echo "AQP_FRESH_FULL_RC=$RC"
exit "$RC"
