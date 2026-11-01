# MG5_aMC PR #426: Zee + 0,1,2 jets FxFx smoke tests

This directory contains two **independent integrations** with exactly
the same two-jet FxFx ME-side exclusive-kT cut from
[upstream MG5_aMC PR #426](https://github.com/mg5amcnlo/mg5amcnlo/pull/426).
Both apply the patch **before integration/compilation**, not after
loading an old gridpack.

| Label | Test JO directory | Matching | Folding | req_acc |
| --- | --- | --- | --- | --- |
| standard111 | tests/2jet/999998 | MC@NLO | 1,1,1 | 0.5 |
| delta111 | tests/2jet/999997 | MC@NLO-Delta | 1,1,1 | 0.5 |

Physics setup for both: 13 TeV, Zee + 0,1,2 partons at NLO QCD;
MG5_aMC 3.5.11.atlas13 under AthGeneration/23.6.63;
FxFx ickkw=3, ptj=8 GeV, jet R=1, Pythia8 nJetMax=2,
qCut=20 GeV; central LHAPDF 325100 and the existing PMG
scale/PDF recipe; **no HT2 bias**.

**req_acc=0.5 is deliberately very loose.** These are fast functional
and integration/gridpack smoke tests, not usable for physics-quality
cross-section, DeltaR, or negative-weight comparisons. They must be
repeated with an appropriate integration accuracy once both pass.

## Submit both integrations on UChicago AF

The existing pinned Condor bootstrap (.condor/cluster.py and
.condor/bootstrap_v3/sitecustomize.py) is required by scripts/gridpack.sh.
Run from a compatible Athena environment:

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

# Standard MC@NLO + FxFx (req_acc=0.5)
bash scripts/gridpack.sh tests/2jet/999998 13000 10 34131

# MC@NLO-Delta + FxFx, folding 111 (req_acc=0.5)
bash scripts/gridpack.sh tests/2jet/999997 13000 10 34133
```

The launcher uses separate tmux sessions / Condor working directories,
and distinct destinations:

- standard111: /data/$USER/NWR/gridpacks/tests-2jet-999998/<run>/
- delta111: /data/$USER/NWR/gridpacks/tests-2jet-999997/<run>/

Capture the RUN, OUTPUT and ATTACH lines from **each** command.
It is safe to submit both when AF capacity permits; they are isolated.
Use each launcher-provided ATTACH command to monitor the tmux session.
Both jobs must print FXFX_PR426_EXCLUSIVE_KT_VERIFIED before MINT begins.
After completion, verify `result_exit=0` in each output timing.txt
and check that a nonempty `*GRID.tar.gz` was produced.

## Shower separately after successful gridpack creation

Provide the real path of each output archive (do not use the
angle-bracket placeholder literally). Run:

```bash
bash scripts/validate_zee2jet_pr426_gridpack.sh \
  "/data/aalida/NWR/gridpacks/tests-2jet-999998/<run>/<standard.GRID.tar.gz>" \
  20 34132 --recompile

bash scripts/validate_zee2jet_pr426_delta111_gridpack.sh \
  "/data/aalida/NWR/gridpacks/tests-2jet-999997/<run>/<delta.GRID.tar.gz>" \
  20 34134 --recompile
```

These create independent validation directories
(`~/gridpack-validation/zee2jet.*` and
`~/gridpack-validation/zee2jet_delta111.*`), recompile generation
executables in disposable copies of the archives, create LHE and
showered EVNT events, and check ROOT CollectionTree event counts.

If a 20-event test passes, repeat with 1000 EVNT events and a new seed.
The stage-1 smoke aims to validate the technical workflow; the main
DeltaR(j,j)<1 physics correction requires a matched old-vs-new 2-jet
comparison with production-grade grids and jet definitions.
