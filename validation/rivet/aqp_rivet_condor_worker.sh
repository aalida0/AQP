#!/usr/bin/env bash
# One Condor job per AQP process/config; incremental and restartable.
# No set -e, set -u, or pipefail.
PROC="$1"
CFG="$2"
case "$PROC:$CFG" in
  Zee:standard111|Zee:delta111|Zee:delta221|Zee:delta441|Wenu:standard111|Wenu:delta111|Wenu:delta221|Wenu:delta441) ;;
  *) echo "ERROR: invalid process/config $PROC $CFG"; exit 2 ;;
esac

export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh"
RC=$?
if [ "$RC" -ne 0 ]; then echo "atlasLocalSetup error=$RC"; exit "$RC"; fi
asetup AthGeneration,23.6.63
RC=$?
if [ "$RC" -ne 0 ]; then echo "asetup error=$RC"; exit "$RC"; fi
lsetup rucio
RC=$?
if [ "$RC" -ne 0 ]; then echo "lsetup rucio error=$RC"; exit "$RC"; fi

for EXE in python3 rucio athena.py; do
  command -v "$EXE" || exit 3
done

echo "Starting incremental EVNT->Rivet job for $PROC $CFG"
echo "hostname=$(hostname) user=$(id -un)"
echo "Rucio account:"
rucio whoami
RC=$?
if [ "$RC" -ne 0 ]; then
  echo "ERROR: Rucio authentication unavailable on Condor worker; check proxy/token forwarding."
  exit "$RC"
fi

python3 aqp_rivet_stream.py \
  --root /data/aalida/AQP_Rivet \
  --job-options "$PWD/aqp_rivet_evnt_job.py" \
  --process "$PROC" \
  --config "$CFG"
RC=$?
echo "RIVET_CONDOR_EXIT=$RC"
exit "$RC"
