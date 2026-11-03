#!/usr/bin/env bash
# Controlled test of NEW Zee 0,1j Delta111 FxFx gridpack built with
# store_rwgt_info=True during the integration/gridpack-creation phase.
# First try without recompilation; rebuild only if that still fails.
# Run only on a dedicated batch worker, not on an AF login node.
# Never changes the archived gridpack; stage/extract into a fresh workdir.
set -euo pipefail

if (( $# < 1 || $# > 4 )); then
    echo "Usage: bash scripts/validate_zee1jet_rwgtgridpack.sh GRIDPACK [maxEvents=100] [seed=34124] [--recompile]" >&2
    exit 2
fi

if (( $# == 4 )) && [[ "$4" != "--recompile" ]]; then
    echo "The fourth argument, if supplied, must be --recompile" >&2
    exit 2
fi

archive=$(realpath -e "$1")
max_events="${2:-100}"
seed="${3:-34124}"
# Leave the standard no-recompile pathway unchanged unless explicitly requested.
# MadGraphControl will recompile only the unpacked copy in this new run dir.
export GRIDPACK_RECOMPILE=0
if (( $# == 4 )); then
    export GRIDPACK_RECOMPILE=1
fi
[[ -f "$archive" && "$archive" == *GRID.tar.gz ]] || {
    echo "Expected a readable MadGraph GRID.tar.gz archive" >&2; exit 2;
}
[[ "$max_events" =~ ^[1-9][0-9]*$ && "$seed" =~ ^[1-9][0-9]*$ ]] || {
    echo "maxEvents and seed must be positive integers" >&2; exit 2;
}
command -v Gen_tf.py >/dev/null || {
    echo "Missing Gen_tf.py; run setupATLAS and asetup 23.6.63,AthGeneration" >&2; exit 2;
}

repo=$(cd "$(dirname "$0")/.." && pwd -P)
jo="$repo/tests/1jet/999995"
python3 "$repo/scripts/check_sample.py" "$jo"

# Only stage the complete, archived gridpack. Never edit it in /data.
base="$HOME/gridpack-validation"
mkdir -p "$base"
run=$(mktemp -d "$base/zee1jet_rwgtgridpack.recompile${GRIDPACK_RECOMPILE}.XXXXXXXX")
staged="$run/$(basename "$archive")"
cp -- "$archive" "$staged"
echo "RUN=$run"
echo "SOURCE_GRIDPACK=$archive"
echo "STAGED_GRIDPACK=$staged"
echo "GRIDPACK_RECOMPILE=$GRIDPACK_RECOMPILE"

# If the archive is accompanied by a cleanup manifest, require its
# recorded content hash and archive name to match the staged copy.
python3 - "$archive" "$staged" <<'PY'
import hashlib
import json
import pathlib
import sys

src, staged = map(pathlib.Path, sys.argv[1:])
manifest = src.parent / "provenance" / "cleanup_manifest.json"
h = hashlib.sha256()
with staged.open("rb") as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b""):
        h.update(chunk)
actual = h.hexdigest()
print("STAGED_SHA256", actual)
if manifest.is_file():
    info = json.loads(manifest.read_text())
    if info.get("gridpack") != src.name or info.get("gridpack_sha256") != actual:
        raise SystemExit("GRIDPACK_CHECKSUM_MISMATCH: preserved manifest disagrees")
    print("GRIDPACK_MANIFEST_CHECK_PASS")
else:
    print("WARNING: no cleanup manifest; only staged checksum recorded")
(run := staged.parent / "gridpack.sha256").write_text(actual + "  " + staged.name + "\n")
PY

export DATAPATH="$jo:${DATAPATH:-}"
export ATHENA_CORE_NUMBER=1
# Guard against accidentally validating with different physics configurations.
grep -Fq 'USE_DELTA = True' "$jo"/mc.*.py
grep -Fq 'PYTHIA8_nJetMax = 1' "$jo"/mc.*.py
grep -Fq 'event_norm": "bias"' "$jo"/mc.*.py
cd "$run"
printf 'ecmEnergy=13000\nmaxEvents=%s\nrandomSeed=%s\nJO=%s\nsourceGridpack=%s\nrecompile=%s\n' \
    "$max_events" "$seed" "$jo" "$archive" "$GRIDPACK_RECOMPILE" > validation_parameters.txt

set +e
Gen_tf.py --ecmEnergy=13000 --maxEvents="$max_events" \
    --firstEvent=1 --randomSeed="$seed" \
    --inputGeneratorFile="$staged" \
    --outputEVNTFile=zee1jet.EVNT.pool.root \
    --jobConfig="$jo" \
    2>&1 | tee generation_shower.log
rc=${PIPESTATUS[0]}
set -e
printf 'transform_exit=%s\n' "$rc" >> validation_parameters.txt
if (( rc != 0 )); then
    echo "GEN_TF_FAILED exit=$rc; logs retained in $run" >&2
    echo "DIAGNOSE: python3 $repo/scripts/diagnose_gridpack_reweight.py '$run' --focus P1_" >&2
    exit "$rc"
fi

[[ -s zee1jet.EVNT.pool.root ]] || {
    echo "EVNT_MISSING: Gen_tf exited zero but no nonempty EVNT was found in $run" >&2; exit 1;
}
grep -q 'Pythia8' generation_shower.log || {
    echo "PYTHIA8_LOG_MISSING: inspect $run/generation_shower.log" >&2; exit 1;
}

# EVNT POOL has one CollectionTree entry per accepted output event.
python3 - "$max_events" <<'PY'
import sys
import ROOT

wanted = int(sys.argv[1])
root_file = ROOT.TFile.Open("zee1jet.EVNT.pool.root", "READ")
if not root_file or root_file.IsZombie():
    raise SystemExit("EVNT_OPEN_FAILED")
tree = root_file.Get("CollectionTree")
if tree is None:
    raise SystemExit("EVNT_COLLECTIONTREE_MISSING")
got = int(tree.GetEntries())
print("EVNT_EVENTS", got)
if got != wanted:
    raise SystemExit("EVNT_EVENT_COUNT_MISMATCH expected=%d observed=%d" % (wanted, got))
print("EVNT_EVENT_COUNT_PASS")
root_file.Close()
PY

# Record that the ROOT CollectionTree event-count check above passed.
printf '%s\n' "$max_events" > evnt_count_verified.txt

# Make a reproducible, conservative physics-statistics summary.
# Failure to parse statistics must not invalidate a successful EVNT smoke test.
if ! python3 "$repo/scripts/summarize_zee1jet_validation.py" "$run" \
     --json "$run/validation_summary.json" \
     > "$run/validation_summary.log" 2>&1; then
    echo "WARNING: summary extraction failed; see $run/validation_summary.log" >&2
else
    echo "VALIDATION_SUMMARY=$run/validation_summary.json"
    echo "VALIDATION_SUMMARY_LOG=$run/validation_summary.log"
fi

echo "ZEE_1JET_RWGTGRIDPACK_LHE_PYTHIA8_SMOKE_PASS"
echo "VALIDATION_DIR=$run"
echo "EVNT_FILE=$run/zee1jet.EVNT.pool.root"
echo "LOG_FILE=$run/generation_shower.log"
