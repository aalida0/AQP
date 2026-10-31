#!/usr/bin/env bash
# Prepare Wenu Standard111 before-PR426 18k shower for AF submit-policy limits.
# Ceph source is kept unchanged; temporary transfer input is on /home.
# The worker returns EVNT to /home; finalize moves verified EVNT to /data.
set -Eeuo pipefail

REPO=/home/aalida/AQP/aqp-production-audit
SRC=/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_shower/before_accepted200_seed13311
OUT=/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_shower/before_accepted18000_seed13311
IWD="$REPO/.aqp_staged/fxfx_pr426_shower/returned/before_accepted18000_seed13311"
ROOTFILE="$OUT/wenu_pr426_before_accepted18000.EVNT.pool.root"
TEMP_EVNT="$IWD/wenu_pr426_before_accepted18000.EVNT.pool.root"
LHE="$SRC/source_50k_lhe.gz"
SHA="$SRC/source_50k_lhe.sha256"
JO="$REPO/joboptions/wenu_fxfx_pr426_shower/100007/mc.aMCPy8EG_Wenu_FxFx_2jets_PR426_shower.py"
RUNNER="$REPO/scripts/run_wenu_fxfx_pr426_condor_transfer.sh"
SUBMIT="$REPO/condor/wenu_fxfx_pr426_before_18000_shower.submit"

for path in "$LHE" "$SHA" "$JO" "$RUNNER" "$SUBMIT"; do
  [[ -s "$path" ]] || { echo "ERROR: missing $path" >&2; exit 3; }
done
# Original 4059847.0 was the old unmatchable shared-filesystem job.
# Never silently submit a second job while the old one is still queued.
if condor_q 4059847.0 -af ClusterId ProcId 2>/dev/null | grep -q .; then
  echo "ERROR: job 4059847.0 still queued; inspect and remove it first" >&2
  exit 4
fi

EXPECTED="$(awk 'NR==1 {print $1}' "$SHA")"
[[ "$EXPECTED" =~ ^[0-9a-fA-F]{64}$ ]] || {
  echo "ERROR: invalid archived LHE SHA256" >&2; exit 5;
}
[[ "$(sha256sum "$LHE" | awk '{print $1}')" == "$EXPECTED" ]] || {
  echo "ERROR: permanent /data compressed LHE failed SHA256" >&2; exit 5;
}
gzip -t "$LHE"
bash -n "$RUNNER"
python3 -m py_compile "$JO"

# The earlier rejected submit left OUT with only stage_manifest.txt.
# Preserve that directory; prohibit overwriting anything else.
if [[ -d "$OUT" ]]; then
  if find "$OUT" -mindepth 1 -maxdepth 1 ! -name stage_manifest.txt | grep -q .; then
    echo "ERROR: /data target already holds unexpected files: $OUT" >&2
    exit 6
  fi
elif [[ ! -e "$OUT" && ! -L "$OUT" ]]; then
  mkdir -p "$(dirname "$OUT")"
  mkdir "$OUT"
else
  echo "ERROR: unexpected /data target: $OUT" >&2; exit 6
fi

if [[ -d "$IWD" ]]; then
  if find "$IWD" -mindepth 1 -maxdepth 1 \
     ! -name source_50k_lhe.gz ! -name source_50k_lhe.sha256 | grep -q .; then
    echo "ERROR: /home transfer directory has non-input files: $IWD" >&2
    exit 6
  fi
elif [[ ! -e "$IWD" && ! -L "$IWD" ]]; then
  mkdir -p "$IWD"
else
  echo "ERROR: cannot create /home transfer directory: $IWD" >&2
  exit 6
fi
[[ ! -e "$TEMP_EVNT" && ! -e "$ROOTFILE" ]] || {
  echo "ERROR: previous EVNT exists; refuse duplicate submission" >&2; exit 6
}

# Reuse a previous verified temporary copy, or create a fresh copy on /home.
if [[ -e "$IWD/source_50k_lhe.gz" ]]; then
  [[ -f "$IWD/source_50k_lhe.gz" && ! -L "$IWD/source_50k_lhe.gz" ]] || {
    echo "ERROR: staged source must be a regular file" >&2; exit 7
  }
else
  tmp="$(mktemp "$IWD/.source_50k_lhe.gz.tmp.XXXXXX")"
  trap 'rm -f "$tmp"' EXIT
  cp -p "$LHE" "$tmp"
  [[ "$(sha256sum "$tmp" | awk '{print $1}')" == "$EXPECTED" ]] || {
    echo "ERROR: staged compressed LHE checksum differs from /data source" >&2
    exit 7
  }
  mv "$tmp" "$IWD/source_50k_lhe.gz"
  trap - EXIT
fi
[[ "$(sha256sum "$IWD/source_50k_lhe.gz" | awk '{print $1}')" == "$EXPECTED" ]] || {
  echo "ERROR: existing /home LHE checksum mismatch" >&2; exit 7;
}
printf '%s  %s\n' "$EXPECTED" source_50k_lhe.gz > "$IWD/source_50k_lhe.sha256"
mkdir -p "$REPO/.aqp_staged/fxfx_pr426_shower/logs"

{
  echo "AQP_FXFX_PR426_BEFORE_18000_TRANSFER_STAGE_PASS"
  echo "PERMANENT_SOURCE=$LHE"
  echo "STAGED_SOURCE=$IWD/source_50k_lhe.gz"
  echo "SHA256=$EXPECTED"
  echo "TRANSFER_INPUT_FROM=/home"
  echo "TRANSFER_OUTPUT_TO=/home"
  echo "EVNT_FINAL_DESTINATION=$ROOTFILE"
  echo "SUBMIT_INITIALDIR=$IWD"
  echo "FINALIZER=$REPO/scripts/finalize_wenu_fxfx_pr426_before_18000_transfer.sh"
  git -C "$REPO" rev-parse HEAD | sed 's/^/GIT_COMMIT=/'
} | tee "$OUT/stage_manifest.txt"

echo
echo "Ready: condor_submit $SUBMIT"
echo "After job completes: bash scripts/finalize_wenu_fxfx_pr426_before_18000_transfer.sh"
