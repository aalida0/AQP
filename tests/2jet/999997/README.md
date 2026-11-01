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

## Pythia8 dependency for MC@NLO-Delta

The first Delta111 gridpack attempt (2026-11-01,
`tests-2jet-999997.ao9bhO`) stopped **before MINT integration**:
MadGraph 3.5.11 reported
`Cannot find Pythia8 path in configuration file` while compiling
the internal MC@NLO-Delta Sudakov machinery. Standard111 correctly
does not need this dependency during compilation.

The Delta JO now passes `pythia8_path=os.environ["PY8PATH"]` into
`modify_config_card`, using a verified Pythia8 installation with
`lib/libpythia8.a`. This follows the original ATLAS MC@NLO-Delta
JobOptions. The failed run is not reusable as a gridpack and should
remain archived for diagnosis; relaunch into a new working directory.

Before relaunching, with AthGeneration/23.6.63 configured:

```bash
echo "PY8PATH=${PY8PATH:-UNSET}"
test -f "${PY8PATH:?PY8PATH is unset}/lib/libpythia8.a" \
  && echo "PYTHIA8_STATIC_LIBRARY_OK"
python3 -m unittest discover -s tests -p 'test_zee2jet_pr426.py' -v
bash scripts/gridpack.sh tests/2jet/999997 13000 10 34135
```

Do **not** interrupt or relaunch the independent standard111 integration
while it is running. The changed code applies to Delta111 only.
