#!/usr/bin/env bash
# Preflight and stage Wenu Standard111 before-PR426 18k FxFx shower.
# Creates a fresh submit-side /data destination, no event generation.
set -Eeuo pipefail

REPO=/home/aalida/AQP/aqp-production-audit
SRC=/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_shower/before_accepted200_seed13311
OUT=/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_shower/before_accepted18000_seed13311
IWD="$REPO/.aqp_staged/fxfx_pr426_shower/returned/before_accepted18000_seed13311"
ROOTFILE="$OUT/wenu_pr426_before_accepted18000.EVNT.pool.root"
LHE="$SRC/source_50k_lhe.gz"
SHA="$SRC/source_50k_lhe.sha256"
JO="$REPO/joboptions/wenu_fxfx_pr426_shower/100007/mc.aMCPy8EG_Wenu_FxFx_2jets_PR426_shower.py"
RUNNER="$REPO/scripts/run_wenu_fxfx_pr426_condor_transfer.sh"
SUBMIT="$REPO/condor/wenu_fxfx_pr426_before_18000_shower.submit"

for path in "$LHE" "$SHA" "$JO" "$RUNNER" "$SUBMIT"; do
  [[ -s "$path" ]] || { echo "ERROR: missing required file: $path" >&2; exit 3; }
done

if condor_q 4059847.0 -af ClusterId ProcId 2>/dev/null | grep -q .; then
  echo "ERROR: original 4059847.0 is still queued (unmatchable FileSystemDomain)." >&2
  echo "Check it, then remove the idle job: condor_rm 4059847.0" >&2
  exit 4
fi

EXPECTED="$(awk 'NR==1 {print $1}' "$SHA")"
[[ "$EXPECTED" =~ ^[[:xdigit:]]{64}$ ]] || {
  echo "ERROR: invalid recorded compressed LHE checksum" >&2; exit 5;
}
ACTUAL="$(sha256sum "$LHE" | awk '{print $1}')"
[[ "$ACTUAL" == "$EXPECTED" ]] || {
  echo "ERROR: archived 50k LHE checksum mismatch" >&2; exit 5;
}
gzip -t "$LHE"
bash -n "$RUNNER"
python3 -m py_compile "$JO"

# The earlier rejected job submission already created the /data folder
# containing only stage_manifest.txt. Reuse that safe preflight directory.
# Never reuse a destination with ROOT data or transfer artifacts.
[[ ! -e "$ROOTFILE" && ! -e "$IWD/shower_artifacts" ]] || {
  echo "ERROR: EVNT or returned diagnostics already exist; audit before retry" >&2
  exit 6
}
if [[ -d "$OUT" ]]; then
  if find "$OUT" -mindepth 1 -maxdepth 1 ! -name stage_manifest.txt | grep -q .; then
    echo "ERROR: /data destination contains unexpected files: $OUT" >&2
    exit 6
  fi
  echo "AQP_FXFX_PR426_REUSING_REJECTED_SUBMISSION_STAGE=$OUT"
elif [[ ! -e "$OUT" && ! -L "$OUT" ]]; then
  mkdir -p "$(dirname "$OUT")"
  mkdir "$OUT"
else
  echo "ERROR: non-directory or symlink destination: $OUT" >&2
  exit 6
fi
if [[ -d "$IWD" ]]; then
  if find "$IWD" -mindepth 1 -maxdepth 1 | grep -q .; then
    echo "ERROR: /home transfer IWD not empty: $IWD" >&2
    exit 6
  fi
elif [[ ! -e "$IWD" && ! -L "$IWD" ]]; then
  mkdir -p "$IWD"
else
  echo "ERROR: cannot create /home IWD: $IWD" >&2
  exit 6
fi
mkdir -p "$REPO/.aqp_staged/fxfx_pr426_shower/logs"
{
  echo "AQP_FXFX_PR426_BEFORE_18000_TRANSFER_STAGE_PASS"
  echo "SOURCE=$LHE"
  echo "LHE_SHA256=$EXPECTED"
  echo "TRANSFER=HTCondor YES"
  echo "EVNT_OUTPUT=$ROOTFILE"
  echo "DIAGNOSTIC_OUTPUT=$IWD/shower_artifacts/"
  echo "SUBMIT_INITIALDIR=$IWD"
  echo "SCRIPT=$RUNNER"
  git -C "$REPO" rev-parse HEAD | sed 's/^/GIT_COMMIT=/'
} | tee "$OUT/stage_manifest.txt"

echo
echo "Check intended matchmaking: condor_submit -dry-run /tmp/pr426-dryrun.ads $SUBMIT"
echo "Then submit: condor_submit $SUBMIT"
