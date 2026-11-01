# Standard111 — corrected Zee + 0,1,2 jets FxFx gridpack

This directory builds a **fresh** standard MC@NLO FxFx 0,1,2-jet
gridpack with the exact upstream PR #426 exclusive-kT ME-cut fix.

Configuration: `USE_DELTA=False`, folding `1,1,1`,
`req_acc=0.5`, 13 TeV, `qCut=20 GeV`, Pythia8 `nJetMax=2`.
The small integration accuracy target is a **functional smoke test**,
not a physics-quality setting. The existing one-jet gridpack is untouched.

For the full standard-vs-Delta111 instructions, see
[the shared 2-jet README](../README.md).

With AthGeneration/23.6.63 configured on AF, submit:

```bash
cd ~/NWR
python3 scripts/check_sample.py tests/2jet/999998
bash scripts/gridpack.sh tests/2jet/999998 13000 10 34131
```

After successful integration, take the exact `*GRID.tar.gz` path printed
in OUTPUT and validate via `scripts/validate_zee2jet_pr426_gridpack.sh`
with `20 34132 --recompile`.
