#!/usr/bin/env bash
# After a smoke gridpack completes, consume it with no recompilation.
# Run on an AF worker in AthGeneration/23.6.63.
set -euo pipefail
if (( $# < 2 || $# > 4 )); then
    echo "Usage: bash scripts/validate_vjets_1jet_smoke.sh DSID GRIDPACK [maxEvents=20] [seed=DSID+1000]" >&2
    exit 2
fi
repo=$(cd "$(dirname "$0")/.." && pwd -P)
dsid="$1"
case "$dsid" in 910101|910102) ;; *)
    echo "Expected test DSID 910101 or 910102" >&2; exit 2 ;;
esac
sample="$repo/tests/1jet/$dsid"
archive=$(realpath -e "$2")
count=${3:-20}
seed=${4:-$((dsid+1000))}
[[ $(basename "$archive") == mc_13TeV*.GRID.tar.gz ]] || { echo "Unexpected gridpack name" >&2; exit 2; }
[[ "$count" =~ ^[1-9][0-9]*$ && "$seed" =~ ^[1-9][0-9]*$ ]] || exit 2
command -v Gen_tf.py >/dev/null || { echo "asetup 23.6.63,AthGeneration first" >&2; exit 2; }
python3 "$repo/scripts/check_sample.py" "$sample"
mkdir -p "$HOME/gridpack-validation"
run=$(mktemp -d "$HOME/gridpack-validation/vjets_1jet_$dsid.XXXXXXXX")
cp -- "$archive" "$run/$(basename "$archive")"
sha256sum "$run/$(basename "$archive")" > "$run/input.sha256"
echo "RUN=$run"
export GRIDPACK_RECOMPILE=0
export ATHENA_CORE_NUMBER=1
export DATAPATH="$sample:${DATAPATH:-}"
cd "$run"
set +e
Gen_tf.py --ecmEnergy=13000 --maxEvents="$count" --firstEvent=1 \
    --randomSeed="$seed" --inputGeneratorFile="$(basename "$archive")" \
    --jobConfig="$sample" --outputEVNTFile=vjets.EVNT.pool.root \
    2>&1 | tee generation_shower.log
rc=${PIPESTATUS[0]}
set -e
echo "GEN_TF_EXIT=$rc"
if (( rc != 0 )); then echo "FAILED_RUN=$run" >&2; exit "$rc"; fi
python3 - "$count" <<'PY'
import ROOT
import sys
f = ROOT.TFile.Open("vjets.EVNT.pool.root")
if not f or f.IsZombie():
    raise SystemExit("EVNT_OPEN_FAILED")
t = f.Get("CollectionTree")
if t is None:
    raise SystemExit("EVNT_COLLECTIONTREE_MISSING")
n = int(t.GetEntries())
print("EVNT_EVENTS", n)
if n != int(sys.argv[1]):
    raise SystemExit("EVNT_COUNT_MISMATCH")
print("EVNT_EVENT_COUNT_PASS")
f.Close()
PY
grep -q 'Found all required weights!' generation_shower.log || {
    echo "PMG_REQUIRED_WEIGHTS_NOT_CONFIRMED" >&2
    exit 1
}
grep -q '163 weights have been written to the LHE file' generation_shower.log || {
    echo "PMG_163_LHE_WEIGHTS_NOT_CONFIRMED" >&2
    exit 1
}
grep -q 'HepMCWeightSvc' generation_shower.log || {
    echo "EVNT_WEIGHT_METADATA_NOT_CONFIRMED" >&2
    exit 1
}
grep -q 'Pythia8' generation_shower.log || {
    echo "PYTHIA8_SHOWER_NOT_CONFIRMED" >&2
    exit 1
}
echo "VJETS_1JET_NO_RECOMPILE_AND_PMG_SMOKE_PASS"
echo "VALIDATION_DIR=$run"
