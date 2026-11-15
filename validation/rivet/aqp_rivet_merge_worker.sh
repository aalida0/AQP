#!/usr/bin/env bash
# Merge Rivet YODA files for one of the six completed v2 samples.
# Runs on a Condor worker. Uses neither set -e nor set -u.
PROC="$1"
CFG="$2"
case "$PROC:$CFG" in
 Zee:standard111|Zee:delta111|Zee:delta221|Wenu:standard111|Wenu:delta111|Wenu:delta221) ;;
 *) echo "ERROR: invalid completed-v2 process/config: $PROC $CFG"; exit 2 ;;
esac

export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh"
RC=$?
if [ "$RC" -ne 0 ]; then
 echo "ERROR: AtlasLocalRootBase setup failed: $RC"
 exit "$RC"
fi

asetup AthGeneration,23.6.63
RC=$?
if [ "$RC" -ne 0 ]; then
 echo "ERROR: Athena setup failed: $RC"
 exit "$RC"
fi
for EXE in python3 rivet-merge; do
 command -v "$EXE"
 RC=$?
 if [ "$RC" -ne 0 ]; then echo "ERROR: missing $EXE"; exit "$RC"; fi
done

python3 aqp_rivet_stream.py \
 --root /data/aalida/AQP_Rivet \
 --job-options "$PWD/aqp_rivet_evnt_job.py" \
 --process "$PROC" \
 --config "$CFG" \
 --versions v2 \
 --merge-only
RC=$?
echo "AQP_RIVET_MERGE_EXIT=$RC process=$PROC config=$CFG"
exit "$RC"
