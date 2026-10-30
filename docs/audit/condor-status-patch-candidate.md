# MG5 3.5.11 internal HTCondor status patch — isolated candidate

Purpose: fix the demonstrated error-status suppression in the installed ATLAS 3.5.11 CondorCluster.control and control_one_job methods without touching CVMFS, production process trees or existing gridpacks.

NOT DEPLOYED. Separate ambiguous condor_submit acknowledgment and duplicate-writer handling remains unresolved.

## Exact source and patch scope

Expected ATLAS cluster.py SHA256:

    feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe

The patcher checks the precise source fingerprint and original status-check code. It modifies only two methods:
- Obtain stdout, stderr, and returncode through communicate() before making scheduler decisions.
- Fail closed on any nonzero condor_q exit status before calling check_termination.
- Reject malformed one-job or aggregate queue responses.
- Preserve valid empty-query handling and the existing scheduler retry decorators.

It does NOT make submissions idempotent or solve every recovery issue.

## On UChicago: validate WITHOUT modifying production

    cd ~/AQP/aqp-production-audit
    git fetch origin
    git pull --ff-only

    python3 -m unittest discover -s tests -p 'test_aqp_*condor*.py' -v
    python3 -m unittest discover -s tests -p 'test_aqp_prepare_condor_status_patch.py' -v

Review a dry-run diff from the exact installed source:

    MG=/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt
    python3 scripts/aqp_prepare_condor_status_patch.py --source "$MG/madgraph/various/cluster.py"

Create a new candidate under temporary storage (not CVMFS, original MG or production):

    PATCHDIR="$(mktemp -d "${TMPDIR:-/tmp}/aqp-condor-status.XXXXXX")"
    python3 scripts/aqp_prepare_condor_status_patch.py \
      --source "$MG/madgraph/various/cluster.py" \
      --output "$PATCHDIR/cluster.py" --write

Re-run the installed-method mock against the isolated candidate:

    python3 scripts/aqp_condor_status_mock.py --cluster-file "$PATCHDIR/cluster.py"

Expected for the candidate: both control_one_job and control print FAIL_CLOSED, mock_rc=42, output_checks=0.

## Acceptance criteria and limitations

- Synthetic tests pass under the ATLAS Python environment.
- The patch produces a syntactically valid candidate based on the pinned file and no other files.
- Failed scheduler queries never trigger output checking.
- Successful idle/running/finished queries behave consistently with the baseline.
- Malformed replies fail closed.
- The test is NOT a real Condor pilot. A separately approved end-to-end test remains necessary.
- Do not copy the candidate into CVMFS or production process trees.
- Keep FxFx and PMG-approved Fortran settings out of scope.

Review first, deploy later with explicit approval.
