# Minimal Zee 0,1j Delta111 HT2 PR426 FxFx JobOption

**Validated reference:** `tests/1jet/999995/`.
**Minimized candidate:** `tests/1jet/999994/`.

The validated reference generated 20 Pythia8-showered EVNT events with
`GRIDPACK_RECOMPILE=0` and `store_rwgt_info=True` during gridpack
integration. The candidate preserves all process, run-card, PDF, matching,
folding, custom Fortran source and Pythia8 settings.

Differences:
- Shorter comments and code.
- Removes diagnostic *text* checks for existing, byte-identical
  `dummy_fct.f`, `montecarlocounter_MINE.f` and PR426 output. The
  `patch --dry-run` and real patch application remain mandatory.
- Fixes `gridpack_compile=False` instead of permitting a diagnostic
  `GRIDPACK_RECOMPILE=1` override.

No sources, integration grids, or existing gridpack archives are modified.
The test DSID 999994 is deliberately separate so the known-working
999995 JO is retained. No new integration is needed for the FIRST check.

## Offline static preflight

```bash
cd ~/NWR
git switch test/fxfx-pr426-zee2jets
git pull --ff-only
python3 scripts/check_sample.py tests/1jet/999994
python3 -m unittest discover -s tests -p 'test_zee1jet_rwgt_minimal.py' -v
bash -n scripts/validate_zee1jet_rwgt_min.sh
```

The regression tests compare the new JO's actual Python AST run-card
settings, process, PDF settings, config-card settings and Pythia8 chain
against the successful reference. They verify the three auxiliary
files are byte-identical.

## Event-mode smoke with the ALREADY WORKING 999995 gridpack

Set `GP` to the existing gridpack previously validated with zero
recompilation. Do **not** build another gridpack for this initial test.

```bash
setupATLAS
asetup 23.6.63,AthGeneration
find /data/aalida/NWR/gridpacks/tests-1jet-999995 -name 'mc_13TeV*.GRID.tar.gz'
GP=/absolute/path/to/existing/999995/mc_13TeV....GRID.tar.gz
bash scripts/validate_zee1jet_rwgt_min.sh "$GP" 20 34303
```

Run the validation on a suitable batch worker, not a shared login node.
The wrapper hashes a copy of the input and uses a fresh local working
directory. Expected markers:
`EVNT_EVENTS 20`, `EVNT_EVENT_COUNT_PASS`,
`ZEE_1JET_RWGT_MIN_LHE_PYTHIA8_SMOKE_PASS`.

This proves the minimized JO can **consume** the validated archive.
It does NOT yet prove that a new gridpack can be integrated and packed
from this minimized JO. For a later integration test, use only
`bash scripts/gridpack.sh tests/1jet/999994 13000 20 34304`
and confirm the resulting run card retains `store_rwgt_info=True`.

**Status:** Committed and source-reviewed. Athena runtime verification
must be carried out on the AF; no job has been submitted.
