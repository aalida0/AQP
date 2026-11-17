#!/usr/bin/env bash
# Wenu Standard111 seed817263: one PanDA pilot of exactly 1000 events.
# Does not modify the 400x5000 production workflow.
# No set -e, set -u, or pipefail.
REPO="$HOME/NWR"
BRANCH="study/vjets-grid-2m-20261109"
JOPATH="tests/wenu_s111_seed817263_grid_2m/200000"
WORKER="scripts/wenu_s111_seed817263_grid_worker_1k.sh"
DATASET="user.aalida.mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2_standard111_seed817263.MG3511.GRIDPACK"
EXPECTED_FILE="mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2_standard111_seed817263.MG3511.GRID.tar.gz"
OUTDS="user.aalida.AQP.Wenu.standard111.seed817263.1kPilot.v1"
SCOPE="user.aalida"
BASE=928431
if [[ ! -d "$REPO/.git" ]]; then echo "Missing $REPO checkout"; exit 2; fi
for command_name in git rucio prun python3; do
    command -v "$command_name" >/dev/null 2>&1 || { echo "Missing $command_name"; exit 2; }
done
REV=$(git -C "$REPO" rev-parse "refs/remotes/origin/$BRANCH") || exit 2
FILE_LIST=$(rucio list-files "$SCOPE:$DATASET")
RC=$?
if (( RC != 0 )) || ! grep -Fq "$EXPECTED_FILE" <<< "$FILE_LIST"; then
    echo "Corrected input GRIDPACK dataset is not registered in Rucio."
    exit 2
fi
if rucio list-files "$SCOPE:$OUTDS" >/dev/null 2>&1; then
    echo "Output dataset already exists; refusing duplicate submission: $OUTDS"
    exit 2
fi
ROOT="$HOME/AQP_grid_2m/Wenu/seed817263"
mkdir -p "$ROOT" || exit 3
RUN=$(mktemp -d "$ROOT/pilot1k.XXXXXX") || exit 3
git -C "$REPO" archive "$REV" "$JOPATH" "$WORKER" | tar -xf - -C "$RUN"
pstat=("${PIPESTATUS[@]}")
if (( pstat[0] != 0 || pstat[1] != 0 )); then echo "Cannot stage pinned files"; exit 3; fi
mv "$RUN/$JOPATH" "$RUN/200000" || exit 3
mv "$RUN/$WORKER" "$RUN/worker.sh" || exit 3
rm -r "$RUN/tests" "$RUN/scripts"
python3 "$REPO/scripts/check_sample.py" "$RUN/200000" || exit 3
cd "$RUN" || exit 3
echo "$REV" > source_git_commit.txt
sha256sum 200000/mc.*.py worker.sh > code.sha256
printf 'dataset=%s\nseed=%s\nevents=1000\njobs=1\n' "$DATASET" "$BASE" > pilot_manifest.txt
prun \
    --exec "bash worker.sh %GP 200000 %RNDM:$BASE $BASE" \
    --secondaryDSs "GP:1:$DATASET" \
    --nJobs=1 \
    --outDS "$OUTDS" \
    --forceStaged \
    --noBuild \
    --outputs 'EVNT.pool.root,run.log,log.generate,generation_timing.txt,jo.sha256' \
    2>&1 | tee prun_submit.log
pstat=("${PIPESTATUS[@]}")
if (( pstat[0] != 0 || pstat[1] != 0 )); then
    echo "PanDA submission failed. See $RUN/prun_submit.log"
    exit 4
fi
echo "SUBMITTED=$SCOPE:$OUTDS"
echo "RECORD=$RUN"
