#!/usr/bin/env bash
# Finalize before-PR426 Wenu FxFx 18k shower returned by HTCondor to /home.
# Verify shower success and EVNT checksum; persist EVNT on Ceph /data.
# Remove only temporary large /home files after completed verification.
# This script never changes the original MadGraph grids or original /data LHE.
set -Eeuo pipefail

REPO=/home/aalida/AQP/aqp-production-audit
IWD="$REPO/.aqp_staged/fxfx_pr426_shower/returned/before_accepted18000_seed13311"
A="$IWD/shower_artifacts"
OUT=/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_shower/before_accepted18000_seed13311
SRC=/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_shower/before_accepted200_seed13311/source_50k_lhe.gz
EVNT=wenu_pr426_before_accepted18000.EVNT.pool.root
TEMP_EVNT="$IWD/$EVNT"
FINAL_EVNT="$OUT/$EVNT"

[[ -d "$IWD" && -d "$OUT" && -d "$A" ]] || {
  echo "ERROR: missing submitted job staging or returned diagnostics" >&2
  exit 3
}
[[ -f "$A/runner_exit_code" && "$(cat "$A/runner_exit_code")" == 0 ]] || {
  echo "ERROR: shower worker did not complete with exit code 0" >&2
  exit 4
}
[[ -f "$A/evnt_transfer_status.txt" &&
   "$(cat "$A/evnt_transfer_status.txt")" == "EVNT_NONEMPTY" ]] || {
  echo "ERROR: worker did not report a valid, nonempty EVNT" >&2
  exit 4
}
[[ -s "$A/log.generate" ]] || {
  echo "ERROR: missing returned log.generate" >&2
  exit 4
}
for marker in \
    "AQP_FXFX_PR426_SHOWER_CASE=before" \
    "AQP_FXFX_PR426_SHOWER_MADGRAPH_NOT_INVOKED" \
    "AQP_FXFX_PR426_SHOWER_FXFX_NJETMAX=2_QCUT=20_A14" \
    "Adding user hook JetMatchingMadgraph"
do
  grep -Fq "$marker" "$A/log.generate" || {
    echo "ERROR: shower diagnostic marker missing: $marker" >&2
    exit 4
  }
done

EXPECTED_SHA="$(awk 'NR==1 {print $1}' "$A/evnt_source.sha256")"
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{64}$ ]] || {
  echo "ERROR: missing/invalid worker EVNT source SHA256" >&2; exit 5;
}
if [[ -s "$TEMP_EVNT" && ! -L "$TEMP_EVNT" ]]; then
  READ_SHA="$(sha256sum "$TEMP_EVNT" | awk '{print $1}')"
  [[ "$READ_SHA" == "$EXPECTED_SHA" ]] || {
    echo "ERROR: returned EVNT differs from worker source SHA256" >&2
    exit 5
  }
elif [[ -s "$FINAL_EVNT" && ! -L "$FINAL_EVNT" ]]; then
  READ_SHA="$(sha256sum "$FINAL_EVNT" | awk '{print $1}')"
  [[ "$READ_SHA" == "$EXPECTED_SHA" ]] || {
    echo "ERROR: existing final EVNT has mismatched SHA256" >&2
    exit 5
  }
else
  echo "ERROR: no complete returned or finalized EVNT" >&2
  exit 5
fi

if [[ -e "$FINAL_EVNT" ]]; then
  [[ -f "$FINAL_EVNT" && ! -L "$FINAL_EVNT" ]] || {
    echo "ERROR: final EVNT is not a regular file" >&2; exit 6;
  }
  [[ "$(sha256sum "$FINAL_EVNT" | awk '{print $1}')" == "$EXPECTED_SHA" ]] || {
    echo "ERROR: existing final EVNT has incorrect checksum" >&2; exit 6
  }
else
  [[ -s "$TEMP_EVNT" ]] || {
    echo "ERROR: returned EVNT missing before copy" >&2; exit 6;
  }
  TMP_FINAL="$OUT/.$EVNT.copying"
  [[ ! -e "$TMP_FINAL" ]] || {
    echo "ERROR: unfinished previous copy exists; inspect: $TMP_FINAL" >&2
    exit 6
  }
  cp -p "$TEMP_EVNT" "$TMP_FINAL"
  COPIED_SHA="$(sha256sum "$TMP_FINAL" | awk '{print $1}')"
  [[ "$COPIED_SHA" == "$EXPECTED_SHA" ]] || {
    echo "ERROR: copied /data EVNT checksum mismatch; source preserved" >&2
    exit 6
  }
  mv "$TMP_FINAL" "$FINAL_EVNT"
fi

printf '%s  %s\n' "$EXPECTED_SHA" "$FINAL_EVNT" > "$OUT/evnt.sha256"
printf '%s\n' "AQP_FXFX_PR426_BEFORE_18000_EVNT_SHA256_PASS" > "$OUT/finalize_status.txt"
printf '%s\n' "AQP_FXFX_PR426_BEFORE_18000_EVNT=$FINAL_EVNT" >> "$OUT/finalize_status.txt"

# Clear only temporary /home copies with verified, identical permanent source.
if [[ -f "$IWD/source_50k_lhe.gz" && ! -L "$IWD/source_50k_lhe.gz" ]]; then
  [[ -s "$SRC" ]] || {
    echo "ERROR: archived source disappeared; temporary source retained" >&2; exit 7
  }
  STAGED_SHA="$(sha256sum "$IWD/source_50k_lhe.gz" | awk '{print $1}')"
  ORIGINAL_SHA="$(sha256sum "$SRC" | awk '{print $1}')"
  [[ "$STAGED_SHA" == "$ORIGINAL_SHA" ]] || {
    echo "ERROR: original compressed source differs; temporary copy retained" >&2
    exit 7
  }
  rm -- "$IWD/source_50k_lhe.gz"
fi
if [[ -f "$TEMP_EVNT" && ! -L "$TEMP_EVNT" ]]; then
  [[ "$(sha256sum "$TEMP_EVNT" | awk '{print $1}')" == "$EXPECTED_SHA" ]] || {
    echo "ERROR: returned EVNT differs; refuse removal" >&2
    exit 7
  }
  rm -- "$TEMP_EVNT"
fi

echo "AQP_FXFX_PR426_BEFORE_18000_FINALIZE_PASS"
echo "EVNT=$FINAL_EVNT"
echo "DIAGNOSTICS=$A"
echo "Only validated temporary large files removed from /home."
