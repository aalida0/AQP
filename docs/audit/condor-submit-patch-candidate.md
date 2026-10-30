# MG5 internal HTCondor: fail-closed submission candidate

**Audit branch only; no production deployment.** The UChicago source-pinned mock reproduced two real implementation weaknesses in ATLAS MG5 3.5.11:

- `submit()` and `submit2()` are wrapped by generic `multiple_try`. If HTCondor accepts a job but the acknowledgment is lost, the generic retry can submit a second worker; the first ID is not tracked.
- Both functions accept the parsed cluster ID without testing `condor_submit`'s exit status. The mock used exit 42 with a parseable ID and demonstrated this.

The four previously scanned Wenu integrations showed 1+5+5+15 historical MINT1 bad-real logs. **The mock does not prove these were caused by the submit implementation.**

## Minimal change

`scripts/aqp_prepare_condor_submit_patch.py` makes a **candidate copy** of `cluster.py` from one of two pinned sources:

- ATLAS 3.5.11 original SHA256 `feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe`;
- Earlier isolated **status-only fix** SHA256 `bbddb6eedd5c68be6070d3cbc8d3efff20d49851f7eb328932e81d3a8cddb6f9`.

It makes only the following changes inside `CondorCluster.submit` and `CondorCluster.submit2`:

1. Remove the non-idempotent `@multiple_try()` decorator for submission (keep `@store_input()` intact).
2. Reject a nonzero `condor_submit` process exit before recording any cluster ID.
3. Reject malformed/empty cluster IDs.
4. Preserve the original calls and ordinary success paths otherwise.

**Not solved:** If HTCondor accepted a job but the acknowledgment was lost, the *first attempt may still run*. The new behavior **stops automatic retries** and leaves reconciliation to the operator. A higher-level caller or repeated manual command can still launch another worker. Never rerun after an ambiguous result until the scheduler and existing stage output have been checked.

## Manual UChicago test (NO live scheduler)

```bash
cd ~/AQP/aqp-production-audit
git fetch origin && git pull --ff-only
python3 -m unittest discover -s tests -p 'test_aqp_prepare_condor_submit_patch.py' -v

MG=/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt
STATUS_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aqp-status.XXXXXX")"
SAFE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aqp-safe.XXXXXX")"

python3 scripts/aqp_prepare_condor_status_patch.py \
  --source "$MG/madgraph/various/cluster.py" \
  --output "$STATUS_DIR/cluster.py" --write

python3 scripts/aqp_prepare_condor_submit_patch.py \
  --source "$STATUS_DIR/cluster.py" \
  --output "$SAFE_DIR/cluster.py" --write

python3 scripts/aqp_condor_status_mock.py --cluster-file "$SAFE_DIR/cluster.py"
python3 scripts/aqp_condor_submit_mock.py --cluster-file "$SAFE_DIR/cluster.py"
```

Expected behavior: status mock returns **FAIL_CLOSED** twice, with no output check; submission mock reports **NORMAL_PASS**, **AMBIGUOUS_ACK_FAIL_CLOSED**, and **NONZERO_EXIT_FAIL_CLOSED** for both `submit` and `submit2`.

The generated `$SAFE_DIR/cluster.py` is not installed, imported by production, or automatically deployed. The original `cluster.py` and all GF/grids/JobOptions remain unchanged.

## Acceptance update (user-run UChicago tests, 2026-10-30)

The user reports all **8/8** `test_aqp_prepare_condor_submit_patch.py` tests passed. Two source-pinned patching steps succeeded:

- Status-only candidate SHA256 `bbddb6eedd5c68be6070d3cbc8d3efff20d49851f7eb328932e81d3a8cddb6f9`.
- **Combined candidate SHA256 `2bef98ea8b4abb69460a1d669870a9c0f35b21576b8a8759b92f1d004b6f3524`.**

Combined candidate tests: `control_one_job` and `control` returned FAIL_CLOSED (mock exit 42, no output checks). Both `submit` and `submit2` returned NORMAL_PASS, AMBIGUOUS_ACK_FAIL_CLOSED (one attempt, zero tracked), NONZERO_EXIT_FAIL_CLOSED (one attempt, zero tracked). **Only synthetic tests; no live scheduler or physics production.**

## Required gate: verify actual MadGraph import path before deployment

The generated process may execute a **bundled** copy `bin/internal/cluster.py`, not `madgraph/various/cluster.py` from the central ATLAS installation. See v3.5.11 `madgraph/interface/amcatnlo_run_interface.py`: it tries `import madgraph`, then selects either `internal.cluster` or `madgraph.various.cluster`. A patch that is only staged against the centrally installed source may be unused during an actual integration.

Run manually in UChicago (read-only):

```bash
BASE="$HOME/AQP/Wjets/WENU"
for cfg in standard111 delta111 delta221 delta441_backup; do
  proc="$BASE/$cfg/PROCNLO_loop_sm-no_b_mass_0"
  echo "=== $cfg ==="
  for f in "$proc/bin/internal/cluster.py" "$proc/bin/internal/misc.py" \
           "$proc/bin/aMCatNLO" "$proc/bin/internal/amcatnlo_run_interface.py"; do
    if [[ -f "$f" ]]; then
      ls -l "$f"
      sha256sum "$f"
    else
      echo "MISSING: $f"
    fi
  done
done
```

If the expected paths do not exist, locate local copies with a constrained search:

```bash
find "$HOME/AQP/Wjets/WENU/standard111/PROCNLO_loop_sm-no_b_mass_0" \
  -type f \( -name cluster.py -o -name amcatnlo_run_interface.py \) -print
```

**Do not infer which copy actually loaded merely from its presence.** After locating candidates, inspect the launcher import statements and any environment setup that changes `PYTHONPATH`. A subsequent zero-physics sandbox import check can establish `cluster.__file__` without altering production. Never replace either original or bundled file before explicit review.

## Remaining acceptance gates before integration

1. All unit tests and source-extracted mocks pass. Confirm the combined candidate SHA256 and review unified diff.
2. Verify output parsing and expected behavior when Condor returns no rows, partial rows, or a successful job missing from the active queue; do not mistake lack of current queue visibility for proof a worker is gone.
3. Design *idempotent reconciliation* of an ambiguously submitted job. At minimum assign a unique request identifier, record attempted requests durably, and check `condor_q` **and** `condor_history` before any retry. Keep one active writer per (stage, GF) directory.
4. Audit worker delivery, `check_termination`, and stage-output contract; a non-empty output file alone does not establish completion.
5. Run a separately approved **small, non-physics** live HTCondor pilot after verifying the generated patch can be loaded from an isolated copy. Do not touch CVMFS or prior integration directories.
6. Only then consider another event-generation campaign. FxFx matching and accepted Fortran modifications remain out of scope.

The patch is a **protective failure behavior**, not a complete restart protocol; refusing an uncertain submission is safer than accidentally running the same GF twice.
