# Independent 0+1-jet MC@NLO-Delta FxFx gridpack pilot

**Branch:** `test/fxfx-pr426-zee2jets`; **new illustrative DSID:** `999996`.
This is a diagnostic sample, **not** an official ATLAS production JO or a
physics-quality NWF study. It does not replace the existing standard-MC@NLO
`tests/1jet/999999/` smoke test.

## Physics configuration and why

- `pp > e+e- [QCD] @0` and `pp > e+e- j [QCD] @1` at 13 TeV:
  a genuine **0,1j NLO FxFx merged** setup, not a single inclusive 1j sample.
- `USE_DELTA=True`, `FOLDING="1, 1, 1"`, `ickkw=3`, `ptj=8`,
  `Pythia8_nJetMax=1`, `PYTHIA8_qCut=20`.
- The same **HT² generation bias** `dummy_fct.f`, **MC@NLO-Delta Sudakov
  tolerance** `montecarlocounter_MINE.f`, and **PR426 exclusive-kT cut**
  `fxfx_exclusive_kt.patch` as the working 0,1,2j test; byte-for-byte
  copies, kept process local.
- `event_norm="bias"`, central PDF 325100. The new gridpack must be built
  from **this exact JO**; a pre-existing 1j/2j archive could be incompatible.
- `req_acc=0.5` for a short technical smoke; cannot be used for quantitative
  cross sections, negative-weight fractions, or jet comparisons.
- `GRIDPACK_RECOMPILE=0` is default; `1` forces rebuild of the **extracted**
  gridpack, without reintegrating it. Keep the original archive immutable.
- For generation, the same PDF/scale recipe and `store_rwgt_info=True`
  as the existing 2j Delta111 JO are intentionally preserved. Do **not**
  suppress NLO reweighting to make a smoke test pass.

The aim is a controlled A/B comparison of *precompiled* vs *recompiled*
NLO event writers in a **fresh smaller-multiplicity gridpack**, not
to claim that a successful 1j result automatically repairs 2j.

## Prepare and build a fresh diagnostic gridpack

On an AF login node, use only for setup and job submission; the Condor
integration runs on batch workers.

```bash
cd ~/NWR
git switch test/fxfx-pr426-zee2jets
git pull --ff-only
setupATLAS
asetup 23.6.63,AthGeneration

python3 scripts/check_sample.py tests/1jet/999996
python3 -m unittest discover -s tests -p test_zee1jet_delta111_jo.py -v
bash -n scripts/validate_zee1jet_delta111_gridpack.sh
test -f "${PY8PATH:?PY8PATH not configured}/lib/libpythia8.a"

# New gridpack integration (not event generation). The launcher uses
# /home for Condor work and archives in /data/$USER/NWR/gridpacks/.
bash scripts/gridpack.sh tests/1jet/999996 13000 20 34261
```

The launcher prints `RUN`, `OUTPUT`, and a `tmux -L ... attach`
command. On completion check `OUTPUT/timing.txt` has `result_exit=0`
and that a unique nonempty `mc_13TeV*.GRID.tar.gz` exists in `OUTPUT`.
Check the JO prints `ZEE_HT2_BIAS_AND_DELTA_TOLERANCE_VERIFIED`
and `FXFX_PR426_EXCLUSIVE_KT_VERIFIED` during integration.

## A/B event-generation and shower test (local worker)

On a suitable Condor worker with the same AthGeneration release,
set `GP` to the new archive printed by the gridpack launcher.
`validate_zee1jet_delta111_gridpack.sh` stages a **fresh copy** for each
run, hashes it, preserves failed working directories and logs, checks
EVNT integrity and exactly 20 output events.

```bash
cd ~/NWR
setupATLAS
asetup 23.6.63,AthGeneration

GP=/data/aalida/NWR/gridpacks/tests-1jet-999996/<OUTPUT_RUN>/mc_13TeV.<new1jet>.GRID.tar.gz

# A: use the new gridpack's existing compiled executables.
bash scripts/validate_zee1jet_delta111_gridpack.sh "$GP" 20 34262

# B: same archive and seed, rebuild the unpacked executables only.
bash scripts/validate_zee1jet_delta111_gridpack.sh "$GP" 20 34262 --recompile
```

Run B even if A succeeds if the goal is to benchmark recompilation;
for the simple smoke, run B only if A fails. **Do not run compilations
on shared login nodes.** Each attempt gets its own
`~/gridpack-validation/zee1jet_delta111.recompile[01].*` directory.

If A fails, capture the printed `RUN` and diagnose it:

```bash
python3 scripts/diagnose_gridpack_reweight.py "$RUN" --focus P1_ --max-logs 8
python3 scripts/audit_gridpack_reweight_build.py "$RUN" --focus P1_...
```

The audit's `--focus` should be replaced by a real `P*/GF*` path from
the failed run; do not literally include ellipsis in a command.

### Acceptance criteria

- Both runs use the **same gridpack SHA256**, same JO, same seed and release.
- A successful attempt has `Gen_tf.py` exit 0, an LHE stream, Pythia8
  FxFx matching, and `EVNT_EVENT_COUNT_PASS` with 20 events.
- If A fails with all reweight logs reporting `This event file cannot be
  reweighted [1]` and missing `#aMCatNLO`, but B succeeds, the 2j
  precompiled-binary inconsistency is reproduced in the 1j control.
- If A succeeds, it shows a *fresh* 1j gridpack can be distributed without
  recompilation. This still does not identify the defective 2j binary.
- If B also fails, do not assume recompilation alone is a reliable fix.
- Only after a no-recompile local PASS, consider Rucio/PanDA using a new
  dataset and the new JO, with the unmodified `mc_13TeV*` basename.

**No Rucio upload, PanDA submission, gridpack repacking, or integration
job is started automatically by this README or these commits.**
