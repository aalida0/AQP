#!/usr/bin/env bash
set -euo pipefail

# Preflight only. This script does NOT launch integration or submit Condor jobs.
# First run: asetup 23.6.63,AthGeneration (pinned atlas13/GCC14 source).

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

# MGControl invokes $MADPATH/bin/mg5_aMC, not $AQP_MG_ROOT/bin/mg5_aMC.
# Refuse to run unless the actual generator is the pinned source used by
# the candidate. In particular, AthGeneration 23.6.68 currently selects
# atlas15-c33bd, whereas this candidate was made from atlas13-dbd05.
if [[ -z "${MADPATH:-}" || ! -f "$MADPATH/madgraph/various/cluster.py" ]]; then
  echo "PRECHECK_BLOCKED: MADPATH is unset or invalid (MADPATH=${MADPATH:-unset})" >&2
  exit 2
fi
ACTIVE_ROOT=$(readlink -f "$MADPATH")
ACTIVE_SHA=$(sha256sum "$MADPATH/madgraph/various/cluster.py" | awk '{print $1}')
PINNED_ROOT=$(readlink -f "$MG_ROOT")
PINNED_SHA=feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe
echo "PRECHECK_MADPATH=$ACTIVE_ROOT"
echo "PRECHECK_MADPATH_CLUSTER_SHA256=$ACTIVE_SHA"
if [[ "$ACTIVE_ROOT" != "$PINNED_ROOT" || "$ACTIVE_SHA" != "$PINNED_SHA" ]]; then
  echo "PRECHECK_BLOCKED: Athena MADPATH does not match the pinned patch source." >&2
  echo "No jobs submitted. Use a compatible Athena setup or audit and pin the active source." >&2
  exit 2
fi

# Condor submission and process generation MUST run from /scratch, never /data.
RUN_BASE=${AQP_SMOKE_RUN_BASE:-"/scratch/$USER/AQP/condor-smoke"}
case "$RUN_BASE" in
  /scratch|/scratch/*) ;;
  *) echo "PRECHECK_BLOCKED: smoke run directory must be under /scratch: $RUN_BASE" >&2; exit 2 ;;
esac
mkdir -p "$RUN_BASE"
RUN_BASE=$(readlink -f "$RUN_BASE")
case "$RUN_BASE" in
  /data|/data/*) echo "PRECHECK_BLOCKED: resolved smoke run directory is under /data" >&2; exit 2 ;;
esac
RUN=$(mktemp -d "$RUN_BASE/MG1jet-smoke.XXXXXX")
mkdir -p "$RUN/guard"

export AQP_CLUSTER_CANDIDATE="$(readlink -f "$CANDIDATE")"
export AQP_CONDOR_GUARD_DIR="$RUN/guard"
export AQP_MG_ROOT="$(readlink -f "$MG_ROOT")"
export PYTHONPATH="$BASE/bootstrap:$AQP_MG_ROOT:${PYTHONPATH:-}"

cd "$RUN"
echo "AQP_RUN=$RUN" | tee preflight.log
echo "AQP_CLUSTER_CANDIDATE=$AQP_CLUSTER_CANDIDATE" | tee -a preflight.log

# Gen_tf.py may use `python`, while shell `python3` points to a different
# interpreter. Match its shebang and check MadGraph's required dependency first.
GEN_SHEBANG=$(head -n 1 "$(command -v Gen_tf.py)")
case "$GEN_SHEBANG" in
  *python3*) PRECHECK_PYTHON=python3 ;;
  *python*) PRECHECK_PYTHON=python ;;
  *) PRECHECK_PYTHON=python3 ;;
esac
printf 'PRECHECK_GEN_TF_SHEBANG=%s\n' "$GEN_SHEBANG" | tee -a preflight.log
printf 'PRECHECK_PYTHON=%s\n' "$(command -v "$PRECHECK_PYTHON")" | tee -a preflight.log
if ! "$PRECHECK_PYTHON" -c 'import six; print("SIX_AVAILABLE", six.__file__)' 2>&1 | tee -a preflight.log; then
  echo "PRECHECK_BLOCKED: six is unavailable to the Python used by Gen_tf.py." | tee -a preflight.log
  echo "Inspect: command -v python python3 Gen_tf.py; python -c 'import six'; python3 -c 'import six'" | tee -a preflight.log
  echo "No Condor jobs or integration launched." | tee -a preflight.log
  exit 2
fi

"$PRECHECK_PYTHON" - <<'PY2' 2>&1 | tee -a preflight.log
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
printf 'cd %q && MADPATH=%q AQP_CONDOR_GUARD_DIR=%q AQP_CLUSTER_CANDIDATE=%q AQP_MG_ROOT=%q PYTHONPATH=%q Gen_tf.py --ecmEnergy=13000 --maxEvents=10 --firstEvent=1 --randomSeed=34123 --outputTXTFile=smoke_lhe_events.tar.gz --jobConfig=%q 2>&1 | tee generation.log\n' \
  "$RUN" "$ACTIVE_ROOT" "$AQP_CONDOR_GUARD_DIR" "$AQP_CLUSTER_CANDIDATE" "$AQP_MG_ROOT" "$PYTHONPATH" "$BASE/JO"
