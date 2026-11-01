# Delta111 — corrected Zee + 0,1,2 jets FxFx gridpack

This directory builds an independent MC@NLO-Delta FxFx 0,1,2-jet
gridpack with the exact upstream PR #426 exclusive-kT ME-cut fix.

Configuration: `USE_DELTA=True`, folding `1,1,1`,
`req_acc=0.5`, 13 TeV, `qCut=20 GeV`, Pythia8 `nJetMax=2`.
All physics settings besides the matching mode match standard111.
The small integration accuracy target is a **functional smoke test**,
not physics-grade integration.

For both configurations and validation stages, see
[the shared 2-jet README](../README.md).

With AthGeneration/23.6.63 configured on AF, submit:

```bash
cd ~/NWR
python3 scripts/check_sample.py tests/2jet/999997
bash scripts/gridpack.sh tests/2jet/999997 13000 10 34133
```

After successful integration, take the exact `*GRID.tar.gz` path printed
in OUTPUT and validate via
`scripts/validate_zee2jet_pr426_delta111_gridpack.sh`
with `20 34134 --recompile`.
