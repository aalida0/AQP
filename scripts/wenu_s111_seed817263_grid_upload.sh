#!/usr/bin/env bash
# Upload the seed-817263 Wenu Standard111 GRID.tar.gz to a NEW Rucio dataset.
# Original gridpack stays untouched. No set -e, set -u, or pipefail.
# Usage: bash scripts/wenu_s111_seed817263_grid_upload.sh --check
#        bash scripts/wenu_s111_seed817263_grid_upload.sh --upload RSE_NAME

MODE="\${1:---check}"
RSE="\${2:-\${AQP_UPLOAD_RSE:-}}"
SCOPE="user.aalida"
DATASET="user.aalida.mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2_standard111_seed817263.MG3511.GRIDPACK"
DID="$SCOPE:$DATASET"
FILE="mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2_standard111_seed817263.MG3511.GRID.tar.gz"
SRC="/data/$USER/gridpacks/tests-wenu_s111_patched_explicit_seed-299901/tests-wenu_s111_patched_explicit_seed-299901.5ZTi6X/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2_standard111_seedcheck.MG3511.GRID.tar.gz"
STAGE="/data/$USER/gridpacks/wenu_s111_seed817263_upload"
TARGET="$STAGE/$FILE"
LOGDIR="$HOME/AQP_rucio_logs/wenu_s111_seed817263"

case "$MODE" in
    --check|--upload) ;;
    *) echo "Usage: bash $0 --check | --upload RSE_NAME" >&2; exit 2 ;;
esac
if [[ ! -s "$SRC" ]]; then
    echo "ERROR: original gridpack missing: $SRC" >&2
    exit 2
fi
if [[ "$(id -un)" != "aalida" ]]; then
    echo "ERROR: expected UNIX account aalida; refusing Rucio upload" >&2
    exit 2
fi
for cmd in rucio sha256sum cmp; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: missing $cmd" >&2; exit 2; }
done
echo "SOURCE=$SRC"
echo "SOURCE_SHA256=$(sha256sum "$SRC" | awk '{print $1}')"
echo "RUCIO_DID=$DID"
echo "FILE=$FILE"
echo "TARGET_RSE=\${RSE:-NOT_SELECTED}"
rucio whoami || { echo "ERROR: Rucio authentication unavailable" >&2; exit 2; }

if [[ "$MODE" == "--check" ]]; then
    echo "Candidate RSE names (verify quota and write permissions):"
    rucio list-rses | grep -E '(_LOCALGROUPDISK|_SCRATCHDISK)$' | head -30
    echo "To upload: bash scripts/wenu_s111_seed817263_grid_upload.sh --upload YOUR_RSE"
    exit 0
fi
if [[ -z "$RSE" ]] || ! rucio list-rses | grep -Fxq -- "$RSE"; then
    echo "ERROR: select an exact existing RSE name using rucio list-rses" >&2
    exit 2
fi
mkdir -p "$STAGE" "$LOGDIR" || exit 2
if [[ -e "$TARGET" ]]; then
    cmp -s "$SRC" "$TARGET" || {
        echo "ERROR: staged file exists but differs from source; refusing overwrite" >&2
        exit 3
    }
else
    echo "Staging uniquely named gridpack on Ceph for Rucio registration..."
    cp -p "$SRC" "$TARGET.partial" || exit 3
    cmp -s "$SRC" "$TARGET.partial" || {
        echo "ERROR: staged copy failed byte-for-byte verification" >&2
        rm -f -- "$TARGET.partial"
        exit 3
    }
    mv "$TARGET.partial" "$TARGET" || exit 3
fi
tar -tzf "$TARGET" >/dev/null || { echo "ERROR: gridpack archive corrupt" >&2; exit 3; }
echo "STAGED_SHA256=$(sha256sum "$TARGET" | awk '{print $1}')"
if rucio list-files "$DID" >/dev/null 2>&1; then
    echo "ERROR: Rucio dataset already exists: $DID; refusing to overwrite." >&2
    exit 4
fi
echo "Uploading to Rucio..."
rucio upload --register-after-upload --rse "$RSE" --scope "$SCOPE" \
    "$DID" "$TARGET" 2>&1 | tee "$LOGDIR/upload.log"
states=("\${PIPESTATUS[@]}")
if (( states[0] != 0 || states[1] != 0 )); then
    echo "ERROR: Rucio upload failed; inspect $LOGDIR/upload.log" >&2
    exit 5
fi
rucio list-files "$DID" > "$LOGDIR/list-files.txt"
rc=$?
if (( rc != 0 )) || ! grep -Fq -- "$FILE" "$LOGDIR/list-files.txt"; then
    echo "ERROR: uploaded dataset missing expected file: $DID" >&2
    exit 5
fi
rucio list-file-replicas "$SCOPE:$FILE" > "$LOGDIR/file-replicas.txt"
rc=$?
if (( rc != 0 )) || ! grep -Fq -- "$RSE" "$LOGDIR/file-replicas.txt"; then
    echo "ERROR: uploaded file replica not confirmed at $RSE" >&2
    exit 5
fi
{
    echo "DID=$DID"
    echo "FILE=$FILE"
    echo "RSE=$RSE"
    echo "SOURCE=$SRC"
    echo "SOURCE_SHA256=$(sha256sum "$SRC" | awk '{print $1}')"
    echo "STAGED_SHA256=$(sha256sum "$TARGET" | awk '{print $1}')"
    echo "UPLOADED_AT=$(date -Is)"
} > "$LOGDIR/manifest.txt" || exit 6
echo "UPLOAD_VERIFIED: $DID"
echo "MANIFEST=$LOGDIR/manifest.txt"
