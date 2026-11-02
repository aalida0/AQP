# Zee +0,1,2j FxFx — standard111, HT2, PR426, req_acc=0.5

This **test** JobOption derives from the main branch's
`JOs/V+jets/Z+jets/Z(ee)/standard111/100000/` source.
The adjacent `dummy_fct.f` and `montecarlocounter_MINE.f`
are **bit-for-bit the canonical main sources**, alongside the
exact FxFx PR #426 patch. Before integration, the JO installs
HT2 `bias_wgt=H_T**2`, the Sudakov 100-epsilon tolerance
correction and PR #426 exclusive kT generation cut.

Matching: `USE_DELTA=False`.
Folding: `1, 1, 1`. Integration accuracy: `0.5`.
Physics: 13 TeV, Zee+0,1,2j NLO FxFx, Pythia8 A14,
FxFx qCut=20 GeV and `event_norm="bias"`.
These grids are for **workflow smoke tests only**, not
physics normalization or differential comparisons.

The previous successful standard111 gridpack was un-biased,
and the earlier Delta111 failed due to uncorrected Sudakov
rounding, so neither prior gridpack can be reused.

After confirming the associated setup, regression tests,
AF Condor requirements and that the old Delta jobs have ended:

```bash
cd ~/NWR
python3 scripts/check_sample.py tests/2jet/999998
bash scripts/gridpack.sh tests/2jet/999998 13000 10 34141
```

Use the corresponding shower validation script only with
the **new** generated HT2 gridpack. See `../README.md`.
