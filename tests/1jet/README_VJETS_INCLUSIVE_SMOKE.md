# 0+1j Zee and W±→eν FxFx Δ111 gridpack smoke (2026-11-06)

This branch is based on the latest **main** after the Wenu physics
correction. It changes no production JOs.

| Channel | Test DSID and gridpack random seed | Main JO reference |
|---|---|---|
| Zee | 910101 | Zee Δ111 100001 |
| W±→eν | 910102 | Wenu Δ111 200001 |

The two diagnostic JOs are derived from their 0+1+2j parents by removing
only the `@2` subprocess, changing `PYTHIA8_nJetMax` from 2 to 1,
changing integration `REQUIRED_ACCURACY` from 0.001 to 0.5,
and correcting the description. **No changes to `dummy_fct.f`
or its installation** and no addition of `custom_fcts`.
The sources and PR426 patch are byte-identical to their full JOs.

Before running:

```bash
cd ~/NWR
git fetch origin
git switch test/vjets-inclusive-1jet-smoke-20261106
git pull --ff-only
setupATLAS
asetup 23.6.63,AthGeneration
python3 -m unittest discover -s tests -p 'test_vjets_1jet_smoke.py' -v
bash scripts/launch_vjets_1jet_smokes.sh
```

The launcher checks both JOs, then calls the existing `gridpack.sh`
twice. Each call creates **a unique detached tmux socket**, so both
gridpacks integrate concurrently and survive SSH disconnection.
It prints `RUN`, `OUTPUT`, and `ATTACH` for each. These commands
are also saved in `~/vjets-1jet-launches/launch.*/`.

After the integration of each sample has finished, confirm
`result_exit=0` in its OUTPUT/timing.txt and that the archive exists.
Then perform the independent **no-recompile full-PMG EVNT smoke**
on a suitable worker:

```bash
bash scripts/validate_vjets_1jet_smoke.sh 910101 /absolute/path/to/Zee.GRID.tar.gz 20 911101
bash scripts/validate_vjets_1jet_smoke.sh 910102 /absolute/path/to/Wenu.GRID.tar.gz 20 911102
```

These are **technical tests only**: `req_acc=0.5` is not sufficient
for cross sections, systematic comparisons or physics distributions.
No local Condor integration has been launched by this GitHub commit.
