# Zee + 0,1,2j FxFx PR426: standard111 and Delta111

**Source of truth:** `main/JOs/V+jets/Z+jets/Z(ee)/standard111/100000/`.
The two complete test JobOptions were rebuilt from that JO after
confirming its original Fortran auxiliary files. All new files remain
on the **test/fxfx-pr426-zee2jets** branch; main is unchanged.

Each test DSID directory now includes:

- **dummy_fct.f**: exact canonical main source; active HT2 bias
  `bias_wgt=H_T**2`.
- **montecarlocounter_MINE.f**: exact canonical main source; MC@NLO-Delta
  Sudakov tolerance `eps=100*epsilon(1)`, clipping probabilities
  in the roundoff interval immediately above one.
- **fxfx_exclusive_kt.patch**: exact canonical main PR #426 patch.
- **Complete JO**: installs both sources in `SubProcesses/`, patches
  `cuts.f` before grid integration, sets `event_norm="bias"`.

These are **new HT2-biased integrations**: do not reuse either
previously generated un-biased gridpack, even though standard111
completed successfully earlier.

| Config | DSID (illustrative) | Matching | Folding | req_acc |
| --- | --- | --- | --- | --- |
| standard111 | 999998 | MC@NLO | 111 | 0.5 |
| delta111 | 999997 | MC@NLO-Delta | 111 | 0.5 |

Both: 13 TeV, Zee +0,1,2j at NLO QCD FxFx, MG5_aMC
3.5.11.atlas13 in AthGeneration/23.6.63, `ptj=8 GeV`,
`ickkw=3`, Pythia8 `nJetMax=2`, `qCut=20 GeV`, central
PDF 325100 for gridpack integration. Delta requires an installed
Pythia8 static library via `PY8PATH`. The event mode retains the
ATLAS gridpack-recompile workaround and its separate shower runners.

## Diagnosed cause of earlier Delta111 failure

The prior Delta111 run `tests-2jet-999997.kehGRv` omitted the
canonical `montecarlocounter_MINE.f`. Multiple MINT0 worker logs
showed `Error in MC@NLO-Delta: Sudakov larger than 1`, with
`probne=1.0000000000000002`, causing workers to terminate. The
subsequent Condor history-verification exception was a downstream
controller symptom. The Sudakov correction is now present in both
test configurations. A clean integration is required to apply the
Fortran changes; do not patch compiled workers in place.

## Setup and preflight on UChicago AF

```bash
cd ~/NWR
git fetch origin
git switch test/fxfx-pr426-zee2jets
git pull --ff-only
setupATLAS
asetup 23.6.63,AthGeneration

python3 -m unittest discover -s tests -p 'test_zee2jet_pr426.py' -v
python3 scripts/check_sample.py tests/2jet/999998
python3 scripts/check_sample.py tests/2jet/999997
bash -n scripts/gridpack.sh
test -f "${PY8PATH:?missing PY8PATH}/lib/libpythia8.a"
```

Verify all checks pass before submitting either run.
Check that the old failed Delta Condor jobs are not still active
before launching a new Delta integration.

## Launch fresh gridpack integrations

```bash
# New HT2-biased standard111
bash scripts/gridpack.sh tests/2jet/999998 13000 10 34141

# New HT2-biased delta111
bash scripts/gridpack.sh tests/2jet/999997 13000 10 34143
```

The gridpack launcher prints separate RUN, OUTPUT and ATTACH values.
The archived outputs go to distinct directories:
`/data/$USER/NWR/gridpacks/tests-2jet-999998/`
and `/data/$USER/NWR/gridpacks/tests-2jet-999997/`.

Each JO must print:
`ZEE_HT2_BIAS_AND_DELTA_TOLERANCE_VERIFIED`
and `FXFX_PR426_EXCLUSIVE_KT_VERIFIED`
before MINT integration. For a gridpack success, inspect the
corresponding `timing.txt` (result_exit=0) and a nonempty GRID.tar.gz.

## Shower smoke tests once new gridpacks exist

Use their **actual** full archive paths, not older un-biased ones:

```bash
bash scripts/validate_zee2jet_pr426_gridpack.sh \
  /absolute/path/to/new_standard_HT2_GRID.tar.gz 20 34142 --recompile

bash scripts/validate_zee2jet_pr426_delta111_gridpack.sh \
  /absolute/path/to/new_delta_HT2_GRID.tar.gz 20 34144 --recompile
```

All current integrations use req_acc=0.5, deliberately too loose
for physical cross-section, negative-weight or differential DeltaRjj
validation. They serve to verify compilation, Condor integration,
gridpack packing, LHE generation and Pythia8 EVNT showering.
