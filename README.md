# FxFx production

Full JOs and auxiliary patches are under `JOs/`. Build a gridpack on
UChicago AF using the source-pinned Condor backend, then move the archive
to `/data/$USER/gridpacks/`.

## Small integration smoke test

This test is **Z(ee)+0,1 jets**, standard111, `req_acc=0.1`,
no HT2 bias, no PDF/scale variations. It exercises the Condor
gridpack launcher and the FxFx exclusive-kT patch; it is
**not a physics/production sample**. The example ID 999999 is
not an approved DSID.

```bash
cd ~/AQP
git switch main
git pull --ff-only origin main
setupATLAS
asetup 23.6.63,AthGeneration
bash -n scripts/gridpack.sh
python3 scripts/check_sample.py tests/1jet/999999
bash scripts/gridpack.sh tests/1jet/999999 13000 10 34123
```

The launcher starts a dedicated `tmux` server, uses a fresh shared
`~/gridpack-work` directory, and records wall time, controller CPU,
logs, and JO SHA256. It verifies exactly one gridpack tar before
copying it to `/data/$USER/gridpacks`. It refuses a mismatched MadGraph
source or Condor patch, which must already be staged under
`~/AQP/aqp-condor-minimal` from the previously validated smoke setup.

The original production JOs remain untouched. Grid submissions, detailed
Condor worker core-hours, and Rivet follow after this smoke test passes.
