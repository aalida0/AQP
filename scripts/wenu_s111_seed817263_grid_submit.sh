#!/usr/bin/env bash
# PanDA Grid 2M Wenu S111 seed817263 (not the anomalous original S111).
# Uses a NEW Rucio GRIDPACK DID; stage immutable JO/worker from a pinned Git SHA.
# --check (read-only), --full (400x5k; requires successful 1k pilot).
# No set -e, set -u, or pipefail.

MODE="${1:---check}"
case "$MODE" in
    --check|--full) ;;
    *) echo "Usage: bash $0 --check|--full" >&2; exit 2 ;;
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
FULL_DS="$OUT_BASE.FxFx2M.v1"
OUTDS="$FULL_DS"
NJOBS=400
BASE=280081700

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
if [[ "$FILE_MATCHES" != "1" ]] || \
   ! grep -Eq 'Total files[[:space:]]*:[[:space:]]*1[[:space:]]*$' <<< "$VERIFY"; then
    echo "ERROR: expected a Rucio dataset with exactly one corrected gridpack file" >&2
    exit 2
fi
if [[ "$MODE" == "--check" ]]; then
    echo "INPUT_DATASET_VERIFIED"
    echo "Next: verify the completed 1k pilot and run --full"
    exit 0
fi
if ! command -v prun >/dev/null 2>&1; then
    echo "ERROR: prun unavailable. Run setupATLAS and lsetup panda." >&2
    exit 2
fi
if [[ "${AQP_WENU_S111_GRID_PILOT_VERIFIED:-}" != "YES" ]]; then
    echo "ERROR: verify completed task 53690423 (1k Pilot v2), then export AQP_WENU_S111_GRID_PILOT_VERIFIED=YES" >&2
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
# Athena's physicsShort is derived from mc.<physicsShort>.py (<=50 chars).
JOS=( "$DEST"/200000/mc.*.py )
if (( ${#JOS[@]} != 1 )) || [[ ! -f "${JOS[0]}" ]]; then
    echo "ERROR: expected exactly one staged mc.*.py JobOption" >&2
    exit 3
fi
JONAME=$(basename "${JOS[0]}")
PHYSICS_SHORT="${JONAME#mc.}"
PHYSICS_SHORT="${PHYSICS_SHORT%.py}"
if (( ${#PHYSICS_SHORT} > 50 )); then
    echo "ERROR: Athena physicsShort exceeds 50 characters: $PHYSICS_SHORT" >&2
    exit 3
fi
echo "PHYSICS_SHORT_OK=$PHYSICS_SHORT (${#PHYSICS_SHORT} characters)"
if [[ "$JONAME" != "mc.aMCPy8EG_Wenu_FxFx_2j_S111_s817263.py" ]]; then
    echo "ERROR: unexpected JobOption filename: $JONAME" >&2
    exit 3
fi
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
