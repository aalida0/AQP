#!/usr/bin/env bash
# Preflight and stage Wenu Standard111 before-PR426 18k FxFx shower.
# Creates a fresh submit-side /data destination, no event generation.
set -Eeuo pipefail

REPO=/home/aalida/AQP/aqp-production-audit
SRC=/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_shower/before_accepted200_seed13311
OUT=/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_shower/before_accepted18000_seed13311
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

# Fail closed: do not overwrite an existing output or pending transfer.
[[ ! -e "$OUT" && ! -L "$OUT" ]] || {
  echo "ERROR: target already exists: $OUT" >&2
  echo "Inspect it before any resubmission." >&2
  exit 6
}
mkdir -p "$REPO/.aqp_staged/fxfx_pr426_shower/logs"
mkdir "$OUT"
{
  echo "AQP_FXFX_PR426_BEFORE_18000_TRANSFER_STAGE_PASS"
  echo "SOURCE=$LHE"
  echo "LHE_SHA256=$EXPECTED"
  echo "TRANSFER=HTCondor YES"
  echo "OUTPUT=$OUT/shower_artifacts/"
  echo "SCRIPT=$RUNNER"
  git -C "$REPO" rev-parse HEAD | sed 's/^/GIT_COMMIT=/'
} | tee "$OUT/stage_manifest.txt"

echo
echo "Check intended matchmaking: condor_submit -dry-run /tmp/pr426-dryrun.ads $SUBMIT"
echo "Then submit: condor_submit $SUBMIT"
