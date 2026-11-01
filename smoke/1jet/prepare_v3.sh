#!/usr/bin/env bash
set -euo pipefail

# Experimental v3 NO-REWEIGHT preflight. No Condor jobs are submitted.
# Keep the original and previous test JobOptions unchanged.
# First run: asetup 23.6.63,AthGeneration (pinned atlas13/GCC14 source).

BASE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORKTREE=$(cd "$BASE/../.." && pwd)
CANDIDATE=${AQP_CLUSTER_CANDIDATE:-"$HOME/AQP/aqp-condor-minimal/.aqp_staged/minimal_v3/cluster.py"}
MG_ROOT=${AQP_MG_ROOT:-"/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt"}
EXPECTED_SHA=ab60358a273531522835cd64c0f76acaca91faed1d426374ae8c04796ca4ef3c

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

# UChicago AF Condor schedd cannot read login03's node-local /scratch.
# Use /home only for this disposable test (previous live canaries succeeded).
# Never submit from /data, and never use node-local /scratch as Initialdir.
RUN_BASE=${AQP_SMOKE_RUN_BASE:-"$HOME/AQP/condor-smoke"}
case "$RUN_BASE" in
  "$HOME"|"$HOME"/*) ;;
  *) echo "PRECHECK_BLOCKED: smoke run directory must be under HOME: $RUN_BASE" >&2; exit 2 ;;
esac
mkdir -p "$RUN_BASE"
RUN_BASE=$(readlink -f "$RUN_BASE")
HOME_REAL=$(readlink -f "$HOME")
case "$RUN_BASE" in
  "$HOME_REAL"|"$HOME_REAL"/*) ;;
  *) echo "PRECHECK_BLOCKED: resolved run directory escapes HOME: $RUN_BASE" >&2; exit 2 ;;
esac
case "$RUN_BASE" in
  /data|/data/*|/scratch|/scratch/*)
    echo "PRECHECK_BLOCKED: run directory is not Condor-accessible: $RUN_BASE" >&2; exit 2 ;;
esac
echo "PRECHECK_RUN_BASE=$RUN_BASE"
echo "PRECHECK_HOME_FILESYSTEM=$(df -T "$RUN_BASE" | tail -1)"
echo "PRECHECK_HOME_FREE=$(df -h "$RUN_BASE" | tail -1)"
RUN=$(mktemp -d "$RUN_BASE/MG1jet-v3norw.XXXXXX")
mkdir -p "$RUN/guard"

export AQP_CLUSTER_CANDIDATE="$(readlink -f "$CANDIDATE")"
export AQP_CONDOR_GUARD_DIR="$RUN/guard"
export AQP_MG_ROOT="$(readlink -f "$MG_ROOT")"
export PYTHONPATH="$BASE/bootstrap_v3:$AQP_MG_ROOT:${PYTHONPATH:-}"

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
assert all(hasattr(cluster, n) for n in ('_aqp_claim','_aqp_states','_aqp_output_contract')), 'V3 patched backend not loaded'
print('PRECHECK_PATCH_ACTIVE PASS')

# Validate the 23.6.63 PDF setup against the installed ATLAS helper before
# running expensive MINT jobs. Using {} here fails: missing central_pdf.
from MadGraphControl.MadGraphUtils import setup_pdf_and_systematic_weights
_pdf = dict(pdlabel='lhapdf', lhaid=325100, reweight_scale=False,
            reweight_pdf=False, store_rwgt_info=False,
            systematics_program='none')
setup_pdf_and_systematic_weights(None, _pdf, True)
print('PRECHECK_NORW_PDF_SETUP_PASS')
PY2


# Write a self-contained launcher to avoid copying a huge LCG PYTHONPATH.
# The launcher remains under shared /home and does not run during preflight.
{
  printf '#!/usr/bin/env bash\nset -euo pipefail\n'
  printf 'cd %q\n' "$RUN"
  printf 'export MADPATH=%q\n' "$ACTIVE_ROOT"
  printf 'export AQP_CONDOR_GUARD_DIR=%q\n' "$AQP_CONDOR_GUARD_DIR"
  printf 'export AQP_CLUSTER_CANDIDATE=%q\n' "$AQP_CLUSTER_CANDIDATE"
  printf 'export AQP_MG_ROOT=%q\n' "$AQP_MG_ROOT"
  printf 'export PYTHONPATH=%q\n' "$PYTHONPATH"
  printf 'Gen_tf.py --ecmEnergy=13000 --maxEvents=10 --firstEvent=1 --randomSeed=34123 --outputTXTFile=smoke_lhe_events.tar.gz --jobConfig=%q 2>&1 | tee generation.log\n' "$BASE/JO_v3_norw"
  printf 'if grep -Eq '\''Command .*interrupted with error:|Transform now exiting early|TransformValidationException'\'' generation.log; then echo "AQP_V3_GENERATION_FAILED: detected MadGraph/Athena error" >&2; exit 1; fi\n'
  printf 'test -s smoke_lhe_events.tar.gz || { echo "AQP_V3_GENERATION_FAILED: missing LHE archive" >&2; exit 1; }\n'
  printf 'tar -tzf smoke_lhe_events.tar.gz >/dev/null || { echo "AQP_V3_GENERATION_FAILED: invalid LHE archive" >&2; exit 1; }\n'
  printf 'if grep -Eq '\''Doing reweight|Running Systematics computation'\'' generation.log; then echo "AQP_V3_GENERATION_FAILED: unexpected reweighting/systematics" >&2; exit 1; fi\n'
  printf 'echo "AQP_V3_NORW_GEN_TF_ARCHIVE_PASS"\n'
} > "$RUN/launch.sh"
chmod 700 "$RUN/launch.sh"

echo
echo "V3 NO-REWEIGHT PRECHECK PASSED. No Condor jobs submitted."
echo "Review and launch this one 1-jet smoke test when ready:"
printf 'bash %q\n' "$RUN/launch.sh"
