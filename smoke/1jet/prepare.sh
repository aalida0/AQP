#!/usr/bin/env bash
set -euo pipefail

# Preflight only. This script does NOT launch integration or submit Condor jobs.
# First run: asetup 23.6.68,AthGeneration (or the known-working AthGeneration release).

BASE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORKTREE=$(cd "$BASE/../.." && pwd)
CANDIDATE=${AQP_CLUSTER_CANDIDATE:-"$HOME/AQP/aqp-condor-minimal/.aqp_staged/minimal_v2/cluster.py"}
MG_ROOT=${AQP_MG_ROOT:-"/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt"}
EXPECTED_SHA=2286e475b32323f1e391fb8e64af06fa8e41531abccd4d2c701b7746a22cc5bd

[[ -f "$CANDIDATE" ]] || { echo "Missing candidate: $CANDIDATE" >&2; exit 2; }
[[ -f "$MG_ROOT/madgraph/various/cluster.py" ]] || { echo "Missing MG_ROOT: $MG_ROOT" >&2; exit 2; }
[[ "$(sha256sum "$CANDIDATE" | awk '{print $1}')" == "$EXPECTED_SHA" ]] || {
  echo "Unexpected candidate SHA256; no jobs submitted" >&2
  exit 2
}
command -v Gen_tf.py >/dev/null || {
  echo "Gen_tf.py unavailable; run asetup AthGeneration first" >&2
  exit 2
}

RUN_BASE=${AQP_SMOKE_RUN_BASE:-"/data/$USER/AQP/condor-smoke"}
mkdir -p "$RUN_BASE"
RUN=$(mktemp -d "$RUN_BASE/MG1jet-smoke.XXXXXX")
mkdir -p "$RUN/guard"

export AQP_CLUSTER_CANDIDATE="$(readlink -f "$CANDIDATE")"
export AQP_CONDOR_GUARD_DIR="$RUN/guard"
export AQP_MG_ROOT="$(readlink -f "$MG_ROOT")"
export PYTHONPATH="$BASE/bootstrap:$AQP_MG_ROOT:${PYTHONPATH:-}"

cd "$RUN"
echo "AQP_RUN=$RUN" | tee preflight.log
echo "AQP_CLUSTER_CANDIDATE=$AQP_CLUSTER_CANDIDATE" | tee -a preflight.log

python3 - <<'PY2' 2>&1 | tee -a preflight.log
import os
import madgraph.various.cluster as cluster
original=os.path.realpath(cluster.__file__)
expected=os.path.realpath(os.path.join(os.environ['AQP_MG_ROOT'], 'madgraph/various/cluster.py'))
print('PRECHECK_ORIGINAL_CLUSTER_PATH', original)
assert original == expected, 'Wrong MadGraph installation imported'
assert hasattr(cluster,'_aqp_claim') and hasattr(cluster,'_aqp_states'), 'Patched backend not loaded'
print('PRECHECK_PATCH_ACTIVE PASS')
PY2

echo
echo 'PRECHECK PASSED. Run the printed command ONLY when you want to submit the one 1-jet smoke test:'
printf 'cd %q && AQP_CONDOR_GUARD_DIR=%q AQP_CLUSTER_CANDIDATE=%q AQP_MG_ROOT=%q PYTHONPATH=%q Gen_tf.py --ecmEnergy=13000 --maxEvents=10 --firstEvent=1 --randomSeed=34123 --outputTXTFile=smoke_lhe_events.tar.gz --jobConfig=%q 2>&1 | tee generation.log\n' \
  "$RUN" "$AQP_CONDOR_GUARD_DIR" "$AQP_CLUSTER_CANDIDATE" "$AQP_MG_ROOT" "$PYTHONPATH" "$BASE/JO"
