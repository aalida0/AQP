# FxFx production

One complete `mc.*.py` per configuration/DSID, with `.f` and
`.patch` files adjacent in `JOs/`. The same JO builds a gridpack on
Condor and consumes it for event generation on the ATLAS Grid.

## Gridpack (UChicago AF; experimental pinned Condor backend)

```bash
setupATLAS
asetup 23.6.63,AthGeneration
bash scripts/gridpack.sh 'JOs/V+jets/Z+jets/Z(ee)/standard111/100000'
```

Optional positional arguments: `ecm_GeV` (13000), `maxEvents` (2000),
`seed` (12345). The launcher uses a **separate tmux socket**,
stages the entire DSID JO directory under shared
`~/gridpack-work/`, then runs `Gen_tf.py`. On success it verifies
exactly one `mc_*GRID.tar.gz` archive, checks the tar, and **moves**
it to `/data/$USER/gridpacks/` alongside `generation.log`,
`timing.txt` and `controller_cpu.txt`. On failure the whole
workspace remains in `/home` for diagnosis.

Preflight requires the pinned v3 Condor patch/bootstrap already tested
at `~/AQP/aqp-condor-minimal/` and exact matching MadGraph
`cluster.py`; no untested patch is silently applied. The launcher
only records **overall elapsed wall time** and controller-process CPU
time, *not* Condor worker core-hours. Per-worker integration timing,
Grid generation, and Rivet are subsequent stages.

**Status:** launcher is syntactically reviewed, not AF-run.
The unified Zee JO's new FxFx source patch and the PDF/scale variations
still require end-to-end validation; these example DSIDs are not
approved production IDs.
