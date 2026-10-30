# Compose validated Condor fixes with original Wenu bundled backends

**DELTA441 PATCH WARNING:** The bundled `cluster.py` candidate for `delta441_backup` is based on the backup, not the validated `delta441_cleaned_v1` gridpack. Do not install it into the cleaned process. See [wenu-delta441-validated-production.md](wenu-delta441-validated-production.md).


**Status:** sandbox candidates only. No production patch, no live HTCondor integration, no changes to the four original processes.

## Verified import resolution

The user executed a read-only import in the AthGeneration environment against `standard111`, obtaining:

    IMPORT_MODE bundled
    CLUSTER_MODULE internal.cluster
    CLUSTER_FILE .../standard111/PROCNLO_loop_sm-no_b_mass_0/bin/internal/cluster.py
    MISC_FILE .../standard111/PROCNLO_loop_sm-no_b_mass_0/bin/internal/misc.py

The messages `No module named 'madgraph'` and `No hepmc reader` occurred before successful fallback. They did not abort the import. Other configurations have identical `bin/aMCatNLO` and `bin/internal/amcatnlo_run_interface.py` hashes, but only standard111 was directly tested for module selection.

The four local `cluster.py` files differ from the central version **only** by per-configuration timing-log destinations in `submit` and `submit2`. The `control` and `control_one_job` methods are unchanged.

Timing directory checks:
- `standard111`, `delta111`, `delta221`: writable.
- `delta441_backup`: the hardcoded old path `WENU/delta441/aqp_condor_timing` is missing or unwritable. Treat as **operational blocker for any future live use**, not a reason to modify historical results.

## 2026-10-30 formatting-only preflight failure and fix

The first read-only dry run was correctly rejected, even though all six initial unit tests passed. The strict reconstruction omitted **one blank line** between the `step = str(argument[3])...` assignment and `if step in ('0', '1'):` inside each timing block. The actual `standard111` diff showed only those two added blank lines. With `--write`, no candidate files were generated, so the subsequent mocks could not find the expected paths; this was **not a scheduler or Condor failure**.

The bundled timing reconstruction now preserves those blank lines and a regression fixture tests that their absence is rejected. **Re-run validation** before trying to generate candidates. Run unit tests and dry run first; use `&&` or `set -e` to avoid attempting mocks after failure.

```bash
cd ~/AQP/aqp-production-audit
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_aqp_prepare_bundled_condor_patch.py' -v
MG=/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt
python3 scripts/aqp_prepare_bundled_condor_patch.py \
  --base "$HOME/AQP/Wjets/WENU" \
  --central "$MG/madgraph/various/cluster.py"
```

Do not proceed to the `--write` or mock steps unless all four configurations print `VERIFIED`.

## Candidate patch design

`scripts/aqp_prepare_bundled_condor_patch.py` requires:

1. Central ATLAS `cluster.py` with exact SHA256 `feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe`.
2. Each bundled `cluster.py` with its exact recorded original SHA256.
3. The entire bundled source must match **central + precisely the two known timing-log modifications** (full source equality).

Only then it composes the previously reviewed status and submission fixes. The timing instrumentation is preserved byte-for-byte, including the obsolete Delta441 destination. It writes nothing without `--write` and does not overwrite files.

## Run on UChicago

From the audit checkout:

```bash
cd ~/AQP/aqp-production-audit
git fetch origin
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_aqp_prepare_bundled_condor_patch.py' -v

MG=/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt
python3 scripts/aqp_prepare_bundled_condor_patch.py \
  --base "$HOME/AQP/Wjets/WENU" \
  --central "$MG/madgraph/various/cluster.py"
```

The dry run prints VERIFIED with source and candidate SHA256 for each configuration. No file writes.

After the dry run succeeds, generate **new, isolated** candidate copies:

```bash
TMP_PATCHES="$(mktemp -d "${TMPDIR:-/tmp}/aqp-wenu-condor.XXXXXX")"
python3 scripts/aqp_prepare_bundled_condor_patch.py \
  --base "$HOME/AQP/Wjets/WENU" \
  --central "$MG/madgraph/various/cluster.py" \
  --outdir "$TMP_PATCHES" --write
```

Test the copied standard111 implementation (no scheduler calls):

```bash
python3 scripts/aqp_condor_status_mock.py \
  --cluster-file "$TMP_PATCHES/standard111/cluster.py"
python3 scripts/aqp_condor_submit_mock.py \
  --cluster-file "$TMP_PATCHES/standard111/cluster.py"
```

The mocks should yield FAIL_CLOSED for both status methods, NORMAL_PASS and fail-closed outcomes for both submission methods. The **actual bundled candidate** must pass before attempting any deployment.

## Important distinction

The patch removes generic automatic retries on ambiguous submissions; it does not implement durable submission IDs, scheduler reconciliation or recovery after a controller crash. It does not address successful-but-partial `condor_q` responses or all possible missing-output cases. Those remain explicit release gates. A successful offline mock is not a production acceptance test.

**Never copy these files into a live or historical process.** First prepare a fresh, disposable **non-physics Condor pilot** with the module import path explicitly checked, reconciliation policy designed, and the timing-log destination guaranteed writable. Production JOs and PMG-approved HT2 / Sudakov code remain unchanged; FxFx mismatch is deferred.
