#!/usr/bin/env bash
# Isolated 0,1j gridpack -> LHE/Pythia8/EVNT check; use an AF batch worker.
set -euo pipefail
if (( $# < 2 || $# > 4 )); then
  echo "Usage: bash scripts/validate_fxfx_1jet.sh TEST_DSID_DIR GRIDPACK [maxEvents=20] [seed=34315]" >&2
  exit 2
fi
repo=$(cd "$(dirname "$0")/.." && pwd -P)
jo=$(realpath -e "$1")
case "$jo" in "$repo"/tests/1jet/91000[1-6]) ;; *)
  echo "Use tests/1jet/910001..910006" >&2; exit 2;;
esac
archive=$(realpath -e "$2")
events=${3:-20}
seed=${4:-34315}
[[ $(basename "$archive") == mc_13TeV*.GRID.tar.gz ]] || { echo "Wrong 13 TeV gridpack name" >&2; exit 2; }
[[ "$events" =~ ^[1-9][0-9]*$ && "$seed" =~ ^[1-9][0-9]*$ ]] || exit 2
command -v Gen_tf.py >/dev/null || { echo "asetup 23.6.63,AthGeneration first" >&2; exit 2; }
python3 "$repo/scripts/check_sample.py" "$jo"
mkdir -p "$HOME/gridpack-validation"
run=$(mktemp -d "$HOME/gridpack-validation/fxfx_1jet_$(basename "$jo").XXXXXXXX")
cp -- "$archive" "$run/$(basename "$archive")"
sha256sum "$run/$(basename "$archive")" > "$run/input.sha256"
echo "RUN=$run"
echo "GRIDPACK_RECOMPILE=0"
export DATAPATH="$jo:${DATAPATH:-}"
export GRIDPACK_RECOMPILE=0 ATHENA_CORE_NUMBER=1
cd "$run"
set +e
Gen_tf.py --ecmEnergy=13000 --maxEvents="$events" --firstEvent=1 \
  --randomSeed="$seed" --inputGeneratorFile="$(basename "$archive")" \
  --jobConfig="$jo" --outputEVNTFile=fxfx_1jet.EVNT.pool.root \
  2>&1 | tee generation_shower.log
rc=${PIPESTATUS[0]}
set -e
echo "GEN_TF_EXIT=$rc"
if (( rc != 0 )); then echo "FAILED_RUN=$run" >&2; exit "$rc"; fi
python3 - "$events" <<'PYCODE'
import ROOT
import sys
f = ROOT.TFile.Open("fxfx_1jet.EVNT.pool.root")
if not f or f.IsZombie():
    raise SystemExit("EVNT_OPEN_FAILED")
t = f.Get("CollectionTree")
if t is None:
    raise SystemExit("EVNT_COLLECTIONTREE_MISSING")
got = int(t.GetEntries())
print("EVNT_EVENTS", got)
if got != int(sys.argv[1]):
    raise SystemExit("EVNT_EVENT_COUNT_MISMATCH")
print("EVNT_EVENT_COUNT_PASS")
f.Close()
PYCODE
grep -q 'Pythia8' generation_shower.log || { echo "PYTHIA8_SHOWER_NOT_FOUND" >&2; exit 1; }
echo "FXFX_1JET_GRIDPACK_LHE_PYTHIA8_SMOKE_PASS"
echo "VALIDATION_DIR=$run"
