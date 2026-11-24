#!/usr/bin/env bash
# One complete EVNT per configuration. Condor logs stay in /home.
AQP_SCRATCH="$PWD"
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" || exit $?
asetup AthGeneration,23.6.63 || exit $?
lsetup rucio || exit $?
cd "$AQP_SCRATCH" || exit $?
rucio whoami || exit $?
python3 aqp_rivet_fresh_pilot.py "$1" "$2" "$3"
RC=$?
echo "AQP_FRESH_PILOT_RC=$RC"
exit "$RC"
