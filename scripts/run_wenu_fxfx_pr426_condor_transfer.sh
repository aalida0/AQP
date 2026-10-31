#!/usr/bin/env bash
# AQP Wenu Standard111 FxFx PR426 shower-only, native HTCondor file transfer.
# This worker NEVER accesses the user's absolute /home or /data paths.
# Input: transferred 50k LHE and 100007 shower-only JO in Condor scratch.
# Output: shower_artifacts directory automatically transferred to initialdir.
set -Eeuo pipefail

CASE="${1:-}"
TARGET="${2:-}"
SEED="${3:-}"
case "$CASE" in before|after) ;; *) echo "ERROR: CASE must be before|after" >&2; exit 2;; esac
case "$TARGET" in 18000) ;; *) echo "ERROR: target must be 18000 accepted events" >&2; exit 2;; esac
case "$SEED" in ''|*[!0-9]*) echo "ERROR: seed must be an integer" >&2; exit 2;; esac

SCRATCH="${_CONDOR_SCRATCH_DIR:-}"
[[ -n "$SCRATCH" && -d "$SCRATCH" ]] || {
    echo "ERROR: expected an outer HTCondor execute-node scratch dir" >&2
    exit 3
}
SCRATCH="$(realpath "$SCRATCH")"
cd "$SCRATCH"
mkdir -p shower_artifacts
ARTIFACTS="$SCRATCH/shower_artifacts"
SOURCE="source_50k_lhe.gz"
SHA_FILE="source_50k_lhe.sha256"
JO="$SCRATCH/100007/mc.aMCPy8EG_Wenu_FxFx_2jets_PR426_shower.py"
EVNT="wenu_pr426_${CASE}_accepted${TARGET}.EVNT.pool.root"

finish() {
    local rc=$?
    trap - EXIT
    set +e
    for file in Gen_tf_shower.log log.generate jobReport.json runargs.generate.py \
                prmon.summary.generate.json atlas_setup.log; do
        [[ -f "$SCRATCH/$file" ]] && cp -p "$SCRATCH/$file" "$ARTIFACTS/" || true
    done
    if (( rc == 0 )); then
        if [[ -s "$SCRATCH/$EVNT" ]]; then
            mv "$SCRATCH/$EVNT" "$ARTIFACTS/$EVNT" || rc=81
        else
            echo "ERROR: Gen_tf returned 0 but EVNT was not produced" >&2
            rc=82
        fi
    fi
    printf '%s\n' "$rc" > "$ARTIFACTS/runner_exit_code"
    echo "AQP_PR426_CONDOR_SHOWER_EXIT=$rc case=$CASE target=$TARGET"
    exit "$rc"
}
trap finish EXIT
trap 'exit 143' TERM

stage() {
    printf 'AQP_PR426_SHOWER_STAGE=%s\n' "$1" | tee -a "$ARTIFACTS/stages.log"
}

[[ -s "$SOURCE" && -s "$SHA_FILE" && -s "$JO" ]] || {
    echo "ERROR: transferred compressed LHE, source hash, or shower JO is missing" >&2
    exit 4
}
EXPECTED_SHA="$(awk 'NR==1 {print $1}' "$SHA_FILE")"
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{64}$ ]] || {
    echo "ERROR: malformed source SHA256" >&2; exit 4
}
ACTUAL_SHA="$(sha256sum "$SOURCE" | awk '{print $1}')"
[[ "$ACTUAL_SHA" == "$EXPECTED_SHA" ]] || {
    echo "ERROR: source 50k LHE checksum mismatch" >&2; exit 5
}
printf '%s  %s\n' "$ACTUAL_SHA" "$SOURCE" > "$ARTIFACTS/source_lhe.sha256"
stage VERIFIED_LHE_SHA256

gzip -t "$SOURCE"
gzip -cd "$SOURCE" > input.events
stage LHE_DECOMPRESSED

python3 - input.events <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
openings, endings, closed = 0, 0, False
with path.open(encoding="utf-8", errors="replace") as f:
    for line in f:
        value = line.strip()
        openings += bool(re.fullmatch(r"<event(?:\s[^>]*)?>", value))
        endings += bool(re.fullmatch(r"</event\s*>", value))
        closed = closed or "</LesHouchesEvents>" in value
if openings != 50000 or endings != 50000 or not closed:
    raise SystemExit(
        f"ERROR: source LHE invalid openings={openings} endings={endings} closed={closed}"
    )
print(f"AQP_PR426_SOURCE_LHE_EVENTS={openings}")
PY
stage LHE_COUNT_VALIDATED

export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
set +e
set +u
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" > atlas_setup.log 2>&1
atlas_rc=$?
if (( atlas_rc == 0 )); then
    asetup AthGeneration,23.6.63 >> atlas_setup.log 2>&1
    asetup_rc=$?
else
    asetup_rc=99
fi
set -u
set -e
if (( atlas_rc != 0 || asetup_rc != 0 )); then
    echo "ERROR: ATLAS setup failure atlas=$atlas_rc asetup=$asetup_rc" >&2
    tail -n 40 atlas_setup.log >&2
    exit 12
fi
command -v Gen_tf.py >/dev/null || {
    echo "ERROR: Gen_tf.py not found after AthGeneration setup" >&2
    exit 12
}
stage ATLAS_READY

export AQP_FXFX_PR426_CASE="$CASE"
export OMP_NUM_THREADS=1
unset ATHENA_CORE_NUMBER
stage START_GEN_TF

set +e
Gen_tf.py \
    --ecmEnergy=13000 \
    --maxEvents="$TARGET" \
    --firstEvent=1 \
    --randomSeed="$SEED" \
    --jobConfig="$SCRATCH/100007" \
    --inputGeneratorFile=input.events \
    --outputEVNTFile="$EVNT" \
    --outputFileValidation=False \
    > Gen_tf_shower.log 2>&1
gen_rc=$?
set -e
if (( gen_rc != 0 )); then
    tail -n 80 Gen_tf_shower.log >&2
    exit "$gen_rc"
fi
[[ -s "$EVNT" && -s log.generate ]] || {
    echo "ERROR: missing showered EVNT or log.generate" >&2; exit 20
}
for marker in \
    "AQP_FXFX_PR426_SHOWER_CASE=$CASE" \
    "AQP_FXFX_PR426_SHOWER_MADGRAPH_NOT_INVOKED" \
    "AQP_FXFX_PR426_SHOWER_FXFX_NJETMAX=2_QCUT=20_A14" \
    "Adding user hook JetMatchingMadgraph"
do
    grep -Fq "$marker" log.generate || {
        echo "ERROR: missing FxFx shower log marker: $marker" >&2
        exit 21
    }
done
stage MATCHED_EVNT_READY
echo "AQP_PR426_FXFX_SHOWER_PASS case=$CASE accepted=$TARGET"
