# Minimal Zee 0,1j Delta111 HT2 PR426 FxFx JobOption

**Validated reference:** `tests/1jet/999995/`.
**Minimized candidate:** `tests/1jet/999994/`.

The validated reference generated 20 Pythia8-showered EVNT events with
`GRIDPACK_RECOMPILE=0` and `store_rwgt_info=True` during gridpack
integration. The candidate preserves the process, run card, matching,
folding, custom Fortran sources, and Pythia8 settings, but **restores the
complete PMG-validated PDF/scale uncertainty recipe in event mode**.

Differences:
- Shorter comments and code.
- Removes diagnostic *text* checks for existing, byte-identical
  `dummy_fct.f`, `montecarlocounter_MINE.f` and PR426 output. The
  `patch --dry-run` and real patch application remain mandatory.
- Fixes `gridpack_compile=False` instead of permitting a diagnostic
  `GRIDPACK_RECOMPILE=1` override.
- Restores the complete PMG-validated event-mode recipe:
  `pdf_variations=[325100,93300]`, eleven alternative PDFs, and
  `scale_variations=[0.5,1,2]`.
- During gridpack integration, only central PDF 325100 is configured;
  that phase does not request uncertainty weights. Crucially,
  `store_rwgt_info=True` remains enabled **in both modes** to support
  no-recompile NLO reweighting.

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
settings, process, config-card settings and Pythia8 chain against the
successful reference, and verify the **full event-mode PDF recipe against
the existing PMG-configured `tests/1jet/999999/` JO**. They verify the three auxiliary
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

If successful, this confirms the updated JO can **consume** the validated
archive. Check the LHE/EVNT weight metadata for the complete PMG variation
set; an EVNT count alone does not prove the requested weights are present.
Since the previous 20-event smoke used a reduced PDF list, this full-PMG
variant still requires fresh runtime validation.
It does NOT yet prove that a new gridpack can be integrated and packed
from this minimized JO. For a later integration test, use only
`bash scripts/gridpack.sh tests/1jet/999994 13000 20 34304`
and confirm the resulting run card retains `store_rwgt_info=True`.

**Status:** Committed and source-reviewed. Athena runtime verification
must be carried out on the AF; no job has been submitted.
