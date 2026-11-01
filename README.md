# AQP

Reproducible ATLAS FxFx production layout. Every process/configuration receives **its own complete JobOption** and colocated auxiliary Fortran sources and patches, suitable for independent PMG review.

## Layout

```text
Wenu/
  200003/                             # Example DSID; not registered/approved
    mc.aMCPy8EG_Wenu_FxFx_2jets_D441.py.template
    fxfx_exclusive_kt.patch           # MG5 PR #426 (source version must be verified)
    PATCHES.md                        # Delta / Condor integration requirements
    AUXILIARY.md                      # Optional per-process .f sources
    sample.json
    README.md
scripts/
  check_sample.py                     # Static check only, no jobs
```

The flat directory is intentional: files fetched by `get_files -data <filename>` are adjacent to their JO. The example carries a `.py.template` suffix to **prevent accidental grid submission** before validation and DSID approval.

## Same JO, separate execution stages

- **Build gridpack on the AF/Condor**: `is_gen_from_gridpack()` is false; generate the MG5 process, apply source patches in its new process directory *before compilation*, configure central PDF without PDF/scale reweighting, and call `generate(..., grid_pack=True)`. The source-pinned patched Condor backend is activated by the AF launcher **before Python imports MadGraph**, not installed as a late JO action.
- **Generate events on the ATLAS Grid**: `is_gen_from_gridpack()` is true; use the existing gridpack, enable PMG-approved PDF and scale variations, then shower with Pythia8 FxFx. Do not submit Condor jobs from grid workers.

A gridpack and its event-generation JO must agree on model/process, merging scale, Delta, folding and bias. Each exact patch/source/version/hash and all results must be recorded. HT2 is **opt-in per process**, never global. The 2026-11-01 Condor/LHE smoke passed; the dummy-event Pythia8 segmentation fault is an independent unresolved issue, so this scaffold is **not production validated**.

## Future workflow

Planned stages: render/validate JO → Condor gridpack → grid submission → parse integration/generation timing and weight/FxFx efficiency logs → Rivet/YODA → PMG tables. This commit implements the directory **skeleton only**, not job submission, runtime extraction, or Rivet execution.

Run static checks:

```bash
python3 scripts/check_sample.py Wenu/200003
```
