#!/usr/bin/env bash
# PanDA Grid 2M Wenu S111 seed817263 (not the anomalous original S111).
# Uses a NEW Rucio GRIDPACK DID; stage immutable JO/worker from a pinned Git SHA.
# --check (read-only), --pilot (one 5k job), --full (400x5k; requires pilot signoff).
# No set -e, set -u, or pipefail.

MODE="${1:---check}"
case "$MODE" in
    --check|--pilot|--full) ;;
    *) echo "Usage: bash $0 --check|--pilot|--full" >&2; exit 2 ;;
esac

REPO="${AQP_REPO:-$HOME/NWR}"
BRANCH="study/vjets-grid-2m-20261109"
SOURCE_JO="tests/wenu_s111_seed817263_grid_2m/200000"
SOURCE_WORKER="scripts/wenu_s111_seed817263_grid_worker.sh"
SCOPE="user.aalida"
DATASET="user.aalida.mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2_standard111_seed817263.MG3511.GRIDPACK"
GRID_FILE="mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2_standard111_seed817263.MG3511.GRID.tar.gz"
DID="$SCOPE:$DATASET"
OUT_BASE="user.aalida.AQP.Wenu.standard111.seed817263"
PILOT_DS="$OUT_BASE.5kPilot.v1"
FULL_DS="$OUT_BASE.FxFx2M.v1"
OUTDS="$PILOT_DS"
NJOBS=1
BASE=928431
if [[ "$MODE" == "--full" ]]; then
    OUTDS="$FULL_DS"
    NJOBS=400
    BASE=280081700
fi

if [[ ! -d "$REPO/.git" ]]; then
    echo "ERROR: expected AQP Git checkout at $REPO" >&2
    exit 2
fi
for cmd in git rucio python3; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: missing $cmd" >&2; exit 2; }
done

REV=$(git -C "$REPO" rev-parse "refs/remotes/origin/$BRANCH" 2>/dev/null) || {
    echo "ERROR: git fetch origin $BRANCH first" >&2
    exit 2
}
if ! git -C "$REPO" cat-file -e "$REV:$SOURCE_WORKER"; then
    echo "ERROR: pinned worker is not on origin/$BRANCH" >&2
    exit 2
fi
python3 "$REPO/scripts/check_sample.py" "$REPO/$SOURCE_JO" || exit 2
if [[ ! -f "$REPO/$SOURCE_WORKER" ]]; then
    echo "ERROR: restore the isolated Wenu Grid worker script" >&2
    exit 2
fi

echo "JO_REF=$REV"
echo "GRIDPACK_DID=$DID"
echo "EXPECTED_GRID_FILE=$GRID_FILE"
echo "OUTPUT=$SCOPE:$OUTDS"
echo "JOBS=$NJOBS EVENTS_PER_JOB=5000"

if ! rucio list-files "$DID" > /dev/null 2>&1; then
    echo "ERROR: corrected gridpack dataset not registered in Rucio." >&2
    echo "Upload first: bash scripts/wenu_s111_seed817263_grid_upload.sh --upload RSE_NAME" >&2
    exit 2
fi
VERIFY=$(rucio list-files "$DID")
rc=$?
if (( rc != 0 )) || ! grep -Fq -- "$GRID_FILE" <<< "$VERIFY"; then
    echo "ERROR: expected corrected gridpack filename absent from Rucio dataset" >&2
    exit 2
fi
FILE_MATCHES=$(grep -Fc -- "$GRID_FILE" <<< "$VERIFY")
if [[ "$FILE_MATCHES" != "1" ]]; then
    echo "ERROR: expected exactly one matching gridpack file, found $FILE_MATCHES" >&2
    exit 2
fi
if [[ "$MODE" == "--check" ]]; then
    echo "INPUT_DATASET_VERIFIED"
    echo "Next: bash scripts/wenu_s111_seed817263_grid_submit.sh --pilot"
    exit 0
fi
if ! command -v prun >/dev/null 2>&1; then
    echo "ERROR: prun unavailable. Run setupATLAS and lsetup panda." >&2
    exit 2
fi
if [[ "$MODE" == "--full" && "${AQP_WENU_S111_GRID_PILOT_VERIFIED:-}" != "YES" ]]; then
    echo "ERROR: inspect the 5k Grid pilot and set AQP_WENU_S111_GRID_PILOT_VERIFIED=YES" >&2
    exit 2
fi
if rucio list-files "$SCOPE:$OUTDS" >/dev/null 2>&1; then
    echo "ERROR: output DID already exists: $SCOPE:$OUTDS" >&2
    exit 2
fi

STAGE_ROOT="$HOME/AQP_grid_2m/Wenu/standard111_seed817263"
mkdir -p "$STAGE_ROOT" || exit 3
DEST=$(mktemp -d "$STAGE_ROOT/${MODE#--}.XXXXXX") || exit 3
git -C "$REPO" archive "$REV" "$SOURCE_JO" "$SOURCE_WORKER" | tar -xf - -C "$DEST"
states=("${PIPESTATUS[@]}")
if (( states[0] != 0 || states[1] != 0 )); then
    echo "ERROR: staging immutable Git archive failed" >&2
    exit 3
fi
mv "$DEST/$SOURCE_JO" "$DEST/200000" || exit 3
mv "$DEST/$SOURCE_WORKER" "$DEST/worker.sh" || exit 3
rm -rf -- "$DEST/tests" "$DEST/scripts"
python3 "$REPO/scripts/check_sample.py" "$DEST/200000" || exit 3
(
    cd "$DEST" || exit 3
    echo "$REV" > source_git_commit.txt
    sha256sum 200000/mc.*.py worker.sh > code.sha256
    printf 'gridpack_did=%s\noutput=%s\nn_jobs=%s\nseed_base=%s\n' \
        "$DID" "$OUTDS" "$NJOBS" "$BASE" > submit_manifest.txt
    prun \
        --exec "bash worker.sh %GP 200000 %RNDM:$BASE $BASE" \
        --secondaryDSs "GP:1:$DATASET" \
        --nJobs="$NJOBS" \
        --outDS "$OUTDS" \
        --forceStaged \
        --noBuild \
        --outputs 'EVNT.pool.root,run.log,log.generate,generation_timing.txt,jo.sha256'
) 2>&1 | tee "$DEST/prun_submit.log"
states=("${PIPESTATUS[@]}")
if (( states[0] != 0 || states[1] != 0 )); then
    echo "ERROR: PanDA prun submission failed. Inspect $DEST/prun_submit.log" >&2
    exit 4
fi
echo "SUBMITTED_OUTDS=$SCOPE:$OUTDS"
echo "SUBMISSION_RECORD=$DEST"
