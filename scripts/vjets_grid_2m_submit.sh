#!/usr/bin/env bash
# Stage immutable JOs from origin/main and submit 1 or 400 jobs/configuration.
# No set -e, set -u, or pipefail by request.

MODE="${1:---check}"
case "$MODE" in
    --check|--pilot|--full) ;;
    *) echo 'Usage: bash vjets_grid_2m_submit.sh --check|--pilot|--full'; exit 2 ;;
esac
REPO="${AQP_REPO:-$HOME/NWR}"
ROOT="${AQP_GRID_ROOT:-$HOME/AQP_grid_2m}"
SCOPE=user.aalida
if [ ! -d "$REPO/.git" ]; then
    echo "ERROR: not a Git repo: $REPO"
    exit 2
fi
if [ ! -f "$(dirname "${BASH_SOURCE[0]}")/vjets_grid_2m_worker.sh" ]; then
    echo 'ERROR: vjets_grid_2m_worker.sh must be next to this launcher'
    exit 2
fi
MAIN_SHA=$(git -C "$REPO" rev-parse origin/main 2>/dev/null)
if [ -z "$MAIN_SHA" ]; then
    echo 'ERROR: origin/main unavailable. Run git fetch origin main'
    exit 2
fi
if [ "$MODE" != '--check' ] && ! command -v prun >/dev/null 2>&1; then
    echo 'ERROR: prun missing. Run setupATLAS and lsetup panda.'
    exit 2
fi

FAILED=0
for PROC in Zee Wenu; do
    for IDX in 0 1 2 3; do
        case "$IDX" in
            0) CFG=standard111 ;;
            1) CFG=delta111 ;;
            2) CFG=delta221 ;;
            3) CFG=delta441 ;;
        esac
        if [ "$PROC" = Zee ]; then
            DSID=$((100000+IDX))
            JOPATH="JOs/V+jets/Z+jets/Z(ee)/$CFG/$DSID"
        else
            DSID=$((200000+IDX))
            JOPATH="JOs/V+jets/W+jets/W(ev)/$CFG/$DSID"
        fi
        DS="user.aalida.mc_13TeV.aMCPy8EG_${PROC}_FxFx_2jets_HT2_${CFG}.GRIDPACK"
        DEST="$ROOT/$PROC/$CFG"
        SEED_BASE=$(( DSID * 1000 + 100 ))
        NJOBS=400
        if [ "$MODE" = '--pilot' ]; then NJOBS=1; fi
        OUTDS="user.aalida.AQP.${PROC}.${CFG}.FxFx2M.v1"
        if [ "$MODE" = '--pilot' ]; then OUTDS="user.aalida.AQP.${PROC}.${CFG}.5kPilot.v1"; fi

        echo "====== $PROC $CFG / DSID $DSID / $MODE ======"
        echo "Input: $SCOPE:$DS"
        if ! rucio list-files "$SCOPE:$DS" 2>/dev/null | grep -Fq "mc_13TeV.aMCPy8EG_${PROC}_FxFx_2jets_HT2_${CFG}.MG3511.GRID.tar.gz"; then
            echo "ERROR: expected gridpack not present in $DS"
            FAILED=$((FAILED+1))
            continue
        fi
        if [ "$MODE" = '--check' ]; then
            echo "JO from main: $JOPATH"
            echo "Output: $OUTDS / jobs for full=400"
            continue
        fi

        mkdir -p "$DEST"
        if [ -f "$DEST/origin-main.sha" ] && [ "$(cat "$DEST/origin-main.sha")" != "$MAIN_SHA" ]; then
            echo "ERROR: main changed since staging $DEST. Inspect before continuing."
            FAILED=$((FAILED+1))
            continue
        fi
        if [ ! -d "$DEST/$DSID" ]; then
            git -C "$REPO" archive "$MAIN_SHA" "$JOPATH" | tar -xf - -C "$DEST"
            STATUS=("${PIPESTATUS[@]}")
            if [ "${STATUS[0]}" -ne 0 ] || [ "${STATUS[1]}" -ne 0 ]; then
                echo "ERROR: staging JO failed: $JOPATH"
                FAILED=$((FAILED+1))
                continue
            fi
            mv "$DEST/$JOPATH" "$DEST/$DSID"
            rm -rf "$DEST/JOs"
            printf '%s\n' "$MAIN_SHA" > "$DEST/origin-main.sha"
        fi
        cp "$(dirname "${BASH_SOURCE[0]}")/vjets_grid_2m_worker.sh" "$DEST/"
        if [ -d "$DEST/user.aalida" ] || [ -e "$DEST/EVNT.pool.root" ]; then
            echo "ERROR: suspicious old output files found in $DEST"
            FAILED=$((FAILED+1))
            continue
        fi
        (
            cd "$DEST" || exit 1
            prun \
              --exec "bash vjets_grid_2m_worker.sh %GP $DSID %RNDM:$SEED_BASE $SEED_BASE" \
              --secondaryDSs "GP:1:$DS" \
              --nJobs="$NJOBS" \
              --outDS "$OUTDS" \
              --forceStaged \
              --noBuild \
              --outputs 'EVNT.pool.root,run.log,log.generate,generation_timing.txt'
        )
        RC=$?
        if [ "$RC" -ne 0 ]; then
            echo "ERROR: prun failed for $PROC $CFG ($RC)"
            FAILED=$((FAILED+1))
        fi
    done
done
if [ "$FAILED" -ne 0 ]; then
    echo "ERROR: $FAILED configurations failed checks or submission"
    exit 1
fi
echo "ALL_CONFIGURATIONS_$MODE_COMPLETE"
