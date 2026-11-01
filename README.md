# FxFx production

One PMG-reviewable JobOption per configuration/DSID under `JOs/`, with its
Fortran sources and patches alongside it. The same JO builds a Condor
gridpack or consumes a gridpack for ATLAS Grid event generation.

## Gridpack smoke test (0,1 jets; accuracy 0.1)

Run on the UChicago Analysis Facility, from a fresh home checkout
(`~/NWR` is supported; the GitHub repository is still `aalida0/AQP`):

```bash
cd ~/NWR
setupATLAS
asetup 23.6.63,AthGeneration
python3 scripts/check_sample.py tests/1jet/999999
bash -n scripts/gridpack.sh
bash scripts/gridpack.sh tests/1jet/999999 13000 10 34123
```

The launcher checks a source-pinned Condor bootstrap at
`<checkout>/.condor/cluster.py` and
`<checkout>/.condor/bootstrap_v3/sitecustomize.py` before starting
anything. These are **local, ignored test assets**, not production
dependencies: copy the exact validated files from the old AF test
checkout, without changing them. You may override the folder using
`GP_PATCH_ROOT=/absolute/path`.

The tmux-launched run uses a unique shared `~/gridpack-work/` directory.
On success, the gridpack, logs, and elapsed/controller timing are saved to
`/data/$USER/gridpacks/`. It does not count remote Condor CPU-hours yet.
The test uses standard matching/folding 111 with no HT2 bias and applies
the FxFx exclusive-kT source patch before compilation. It is a **smoke
test only**, not a validated physics sample.

Production JOs, Grid submission automation and Rivet validation remain
separate stages. Do not move a live Condor work directory during a job.
