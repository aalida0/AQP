#!/usr/bin/env bash
# AQP Zee FxFx smoke: one existing gridpack -> one Rucio dataset -> one PanDA EVNT job.
# Adapted from vv-jets-production/Scripts/run.sh. No gridpack integration is performed.
# Requires explicit upload / submit action; "plan" is local and read-only.
set -euo pipefail

usage() {
    cat <<'HELP'
Usage:
  bash scripts/aqp_zee_grid_rucio.sh plan   standard111|delta111 GRID.tar.gz TAG
  bash scripts/aqp_zee_grid_rucio.sh upload standard111|delta111 GRID.tar.gz TAG
  bash scripts/aqp_zee_grid_rucio.sh verify standard111|delta111 GRID.tar.gz TAG
  bash scripts/aqp_zee_grid_rucio.sh submit standard111|delta111 GRID.tar.gz TAG

Environment (use your actual account and a writable RSE):
  setupATLAS; asetup 23.6.63,AthGeneration; lsetup rucio panda
  voms-proxy-init -voms atlas

Optional:
  AQP_REPO=$HOME/NWR                # source checkout
  AQP_RUCIO_USER=aalida             # your Rucio account (default: RUCIO_ACCOUNT / USER)
  AQP_RSE=CERN-PROD_SCRATCHDISK    # writable Rucio storage element
  AQP_EVENTS=20                     # output events in the single pilot job
  AQP_GRIDPACK_RECOMPILE=0         # reuse compiled gridpack (optional 1 to rebuild)
  AQP_JO_DIR=/path/to/matching/JO  # mandatory for standard111 submit
  AQP_EXPECT_EVENT_NORM=average|bias  # checks event_norm in event-mode JO
  AQP_GRID_STAGE_DIR=$HOME/aqp-grid-stage  # outside the repository checkout

Use a unique TAG for each attempt. No real upload/submission in plan mode.
For a 13 TeV gridpack, its Rucio LFN MUST retain the mc_13TeV* basename.
Gen_tf.py rejects a renamed GRID.tar.gz before running the JO.
This is a small workflow test, not a physics-quality production submission.
HELP
}

[[ $# -eq 4 ]] || { usage >&2; exit 2; }
MODE=$1 CONFIG=$2 GRIDPACK=$3 TAG=$4
case "$MODE" in plan|upload|verify|submit) ;; *) usage >&2; exit 2;; esac
case "$CONFIG" in
    standard111) DSID=999998 ;;
    delta111)    DSID=999997 ;;
    *) usage >&2; exit 2;;
esac
[[ "$TAG" =~ ^[A-Za-z0-9_]+$ ]] || { echo "Invalid TAG: letters/digits/underscore only" >&2; exit 2; }
[[ -s "$GRIDPACK" && "$GRIDPACK" == *GRID.tar.gz ]] || {
    echo "Expected nonempty GRID.tar.gz: $GRIDPACK" >&2; exit 2;
}
GRIDPACK=$(realpath -e -- "$GRIDPACK")

REPO=${AQP_REPO:-$HOME/NWR}
ACCOUNT=${AQP_RUCIO_USER:-${RUCIO_ACCOUNT:-${USER:-}}}
RSE=${AQP_RSE:-CERN-PROD_SCRATCHDISK}
EVENTS=${AQP_EVENTS:-20}
RECOMPILE=${AQP_GRIDPACK_RECOMPILE:-0}
[[ "$ACCOUNT" =~ ^[A-Za-z0-9_]+$ && "$EVENTS" =~ ^[1-9][0-9]*$ && "$RECOMPILE" =~ ^[01]$ ]] || {
    echo "Invalid AQP_RUCIO_USER, AQP_EVENTS or AQP_GRIDPACK_RECOMPILE" >&2; exit 2;
}

JO_DIR=${AQP_JO_DIR:-$REPO/tests/2jet/$DSID}
[[ -d "$JO_DIR" ]] || { echo "Missing JO directory: $JO_DIR" >&2; exit 2; }
shopt -s nullglob
JOS=("$JO_DIR"/mc.*.py)
[[ ${#JOS[@]} -eq 1 ]] || { echo "Expected one complete JO under $JO_DIR" >&2; exit 2; }
JO=${JOS[0]}
grep -Fq 'gridpack_compile=RECOMPILE_GRIDPACK' "$JO" || {
    echo "JO does not support GRIDPACK_RECOMPILE: $JO" >&2; exit 2;
}
# The original successful standard111 gridpack was NO-HT2. The later
# branch JO is HT2-biased. Do not silently mismatch gridpack and event JO.
if [[ "$MODE" == submit && "$CONFIG" == standard111 && -z "${AQP_JO_DIR:-}" ]]; then
    echo "Set AQP_JO_DIR to the event JO matching your NO-HT2 standard gridpack." >&2
    exit 2
fi
if [[ -n "${AQP_EXPECT_EVENT_NORM:-}" ]]; then
    [[ "$AQP_EXPECT_EVENT_NORM" =~ ^(average|bias)$ ]] || {
        echo "AQP_EXPECT_EVENT_NORM must be average or bias" >&2; exit 2;
    }
    grep -Eq "[\"']event_norm[\"'][[:space:]]*:[[:space:]]*[\"']${AQP_EXPECT_EVENT_NORM}[\"']" "$JO" || {
        echo "JO lacks event_norm=$AQP_EXPECT_EVENT_NORM: $JO" >&2; exit 2;
    }
fi

SHA256=$(sha256sum -- "$GRIDPACK" | awk '{print $1}')
SCOPE="user.$ACCOUNT"

# ATLAS Gen_tf.py checks the gridpack filename *before* executing the JO.
# It requires an mc_13TeV*.GRID.tar.gz file for --ecmEnergy=13000.
# Never replace the basename with a dataset tag or checksum-based LFN:
# PanDA stages the Rucio LFN verbatim, and the resulting transform fails
# before Athena starts if the staged name is not recognized.
FILE_NAME=$(basename -- "$GRIDPACK")
[[ "$FILE_NAME" == mc_13TeV*.GRID.tar.gz ]] || {
    echo "Invalid ATLAS 13 TeV gridpack filename: $FILE_NAME" >&2
    echo "Expected mc_13TeV*.GRID.tar.gz; retain the original gridpack basename." >&2
    exit 2
}
DATASET="${SCOPE}.AQP.Zee2jet.PR426.${CONFIG}.GRID.${TAG}"
DID="$SCOPE:$DATASET"
OUTDS="${SCOPE}.AQP.Zee2jet.PR426.${CONFIG}.EVNT${EVENTS}.${TAG}"

# Stage the JO at the root of an otherwise empty sandbox outside the Git
# checkout for pathena. Gen_tf's 23.6 skeleton checks the first directory in
# JOBOPTSEARCHPATH (./ on the worker) for EXACTLY ONE mc*.py file.
# Submitting from the repo packages multiple JOs nested under tests/ and JOs/,
# causing "You must supply one and only one jobOption file in DSID directory".
#
# Do not pass --jobConfig=tests/2jet/999997: pathena controls the worker
# layout. Instead copy a single JO into the submission sandbox root and pass
# --jobConfig=./, which refers to that root on the worker.
#
# pathena expands %IN to the Rucio-staged gridpack filename.
# 'env VAR=VALUE Gen_tf.py' sets the worker environment; passing
# '--env' *inside* Gen_tf.py arguments would be incorrect.
TRF="env GRIDPACK_RECOMPILE=$RECOMPILE Gen_tf.py --ecmEnergy=13000 --maxEvents=$EVENTS --firstEvent=1 --randomSeed=%RNDM:34151 --inputGeneratorFile=%IN --outputEVNTFile=%OUT.EVNT.pool.root --jobConfig=./"

printf 'MODE=%s\nCONFIG=%s\nGRIDPACK=%s\nSHA256=%s\nJO=%s\nRSE=%s\nIN_DID=%s\nGRIDPACK_LFN=%s:%s\nOUT_DS=%s\n' \
    "$MODE" "$CONFIG" "$GRIDPACK" "$SHA256" "$JO" "$RSE" "$DID" "$SCOPE" "$FILE_NAME" "$OUTDS"

if [[ "$MODE" == plan ]]; then
    printf '\nUpload command:\n'
    printf 'rucio upload --rse %q --scope %q --name %q %q %q\n' \
        "$RSE" "$SCOPE" "$FILE_NAME" "$DID" "$GRIDPACK"
    printf '\nSubmission (JO staged as the only mc*.py at a fresh root outside Git):\n'
    printf 'SOURCE_JO=%q\n' "$JO"
    printf 'STAGING_PARENT=%q\n' "${AQP_GRID_STAGE_DIR:-$HOME/aqp-grid-stage}"
    printf 'TRF=%s\n' "$TRF"
    printf 'pathena --trf %q --inDS %q --outDS %q --nFilesPerJob=1 --nCore=1 --noBuild\n' \
        "$TRF" "$DATASET" "$OUTDS"
    exit 0
fi

for cmd in rucio voms-proxy-info; do
    command -v "$cmd" >/dev/null || { echo "Missing $cmd; set up ATLAS/Rucio environment" >&2; exit 2; }
done
voms-proxy-info -exists >/dev/null || {
    echo "No valid ATLAS VOMS proxy; run voms-proxy-init -voms atlas" >&2; exit 2;
}

verify_dataset() {
    local listing total
    listing=$(rucio list-files "$DID") || return 1
    printf '%s\n' "$listing"
    grep -Fq -- "$FILE_NAME" <<<"$listing" || {
        echo "Missing expected gridpack LFN $FILE_NAME in $DID" >&2; return 1;
    }
    # Refuse if output format changes: never submit more than one input file.
    total=$(sed -nE 's/.*Total files[[:space:]]*:[[:space:]]*([0-9]+).*/\1/p' <<<"$listing" | tail -1)
    [[ "$total" == 1 ]] || {
        echo "Expected exactly one Rucio file (found: ${total:-unknown}); check output" >&2; return 1;
    }
    echo "RUCIO_ONE_FILE_VERIFIED=$DID"
}

if [[ "$MODE" == upload ]]; then
    if rucio get-metadata "$DID" >/dev/null 2>&1; then
        echo "Dataset already exists; refuse to overwrite: $DID" >&2
        echo "Use verify/submit or choose a new TAG." >&2
        exit 2
    fi
    rucio list-rses | grep -Fxq -- "$RSE" || {
        echo "RSE not advertised: $RSE (confirm write permission)" >&2; exit 2;
    }
    # --name preserves the ATLAS mc_13TeV* filename in the Rucio LFN.
    # The dataset TAG provides separation between test submissions.
    # Never rename the staged generator archive to AQP.*.GRID.tar.gz.
    rucio upload --rse "$RSE" --scope "$SCOPE" --name "$FILE_NAME" "$DID" "$GRIDPACK"
    verify_dataset
    exit 0
fi

verify_dataset
[[ "$MODE" == verify ]] && exit 0
command -v pathena >/dev/null || { echo "Missing pathena; run lsetup panda" >&2; exit 2; }
# Keep the pathena work area independent of the Git worktree: otherwise the
# client may bundle the whole repository, rather than the single Grid JO.
STAGING_PARENT=${AQP_GRID_STAGE_DIR:-$HOME/aqp-grid-stage}
mkdir -p -- "$STAGING_PARENT"
STAGING_PARENT=$(realpath -e -- "$STAGING_PARENT")
REPO_ABS=$(realpath -e -- "$REPO")
case "$STAGING_PARENT/" in
    "$REPO_ABS/"*) echo "Staging must be OUTSIDE the AQP checkout: $STAGING_PARENT" >&2; exit 2 ;;
esac
STAGE=$(mktemp -d "$STAGING_PARENT/${CONFIG}.${TAG}.XXXXXX")
cp -- "$JO" "$STAGE/$(basename -- "$JO")"
mapfile -t STAGED_JOS < <(find "$STAGE" -maxdepth 1 -type f -name 'mc*.py' -print)
[[ ${#STAGED_JOS[@]} -eq 1 ]] || { echo "Need exactly one top-level Grid JO in $STAGE" >&2; exit 2; }
[[ $(find "$STAGE" -mindepth 1 -maxdepth 1 -type f | wc -l) -eq 1 ]] || {
    echo "Unexpected files in isolated staging directory: $STAGE" >&2; exit 2;
}
printf 'ISOLATED_STAGE=%s\nSTAGED_JO=%s\n' "$STAGE" "${STAGED_JOS[0]}"
printf 'JOB_CONFIG=./ (first JOBOPTSEARCHPATH directory: ./)\n'
read -r -p "Submit ONE $CONFIG PanDA job producing $EVENTS events? Type SUBMIT: " answer
[[ "$answer" == SUBMIT ]] || { echo "Cancelled; stage retained: $STAGE"; exit 2; }
cd "$STAGE"
pathena --trf "$TRF" --inDS "$DATASET" --outDS "$OUTDS" \
    --nFilesPerJob=1 --nCore=1 --noBuild
