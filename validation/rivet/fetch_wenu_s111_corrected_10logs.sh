#!/usr/bin/env bash
# Fetch ONLY 10 log.generate archives from the corrected Wenu S111 seed817263
# production. Never fall back to old wrong-seed Wenu S111 v2.
#
# Usage: bash validation/rivet/fetch_wenu_s111_corrected_10logs.sh
# Run after lsetup rucio and authentication, on AF/lxplus.
SCOPE="user.aalida"
DID="$SCOPE:user.aalida.AQP.Wenu.standard111.seed817263.FxFx2M.v1_log.generate/"
ROOT="/data/aalida/AQP/aqp_log_comparison"
DEST="$ROOT/Wenu/standard111/v1"

if ! command -v rucio >/dev/null 2>&1; then
  echo "ERROR: rucio not on PATH; run setupATLAS; lsetup rucio"
  exit 2
fi
if ! rucio whoami >/dev/null 2>&1; then
  echo "ERROR: Rucio authentication unavailable"
  exit 2
fi
if ! rucio list-content "$DID" >/dev/null 2>&1; then
  echo "ERROR: corrected Wenu S111 log container not found: $DID"
  echo "Check Rucio task output; do NOT substitute the wrong-seed v2 dataset."
  exit 3
fi

mkdir -p "$DEST"
echo "CORRECTED_WENU_S111_LOG_DID=$DID"
echo "WENU_S111_LOG_DEST=$DEST"
rucio download --nrandom 10 --no-subdir --dir "$DEST" "$DID"
RC=$?
if [ "$RC" -ne 0 ]; then
  echo "ERROR: corrected sample Rucio download exited $RC"
  exit "$RC"
fi

echo "WENU_S111_CORRECTED_AVAILABLE_LOGS:"
find "$DEST" -type f \( -name '*.log.generate' -o -name '*.log.generate.gz' \
    -o -name '*.log.generate.txt' -o -name '*.log.generate.txt.gz' \) \
    -printf '%f\n' | sort | head -n 15

echo "REBUILDING_8_CONFIGURATION_NWF_TABLE"
python3 /home/aalida/AQP/validation/rivet/aqp_nwf_10logs.py "$ROOT"
RC=$?
echo "NWF_TABLE_EXIT=$RC"
exit "$RC"
