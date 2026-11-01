# AQP — FxFx NLO sample production

PMG-reviewable JobOptions are grouped by physics process under `JOs/`.
Each configuration keeps **its own complete JO and its required Fortran
sources/patches in the same DSID directory**, matching the historical Zee
production layout.

```text
JOs/
  V+jets/
    Z+jets/Z(ee)/
      standard111/100000/
        mc.aMCPy8EG_Zee_FxFx_2jets_HT2bias_standard111.py
        fxfx_exclusive_kt.patch
        REQUIRED_FILES.md
      delta111/
      delta221/
      delta441/
      event_generation/grid_submit_standard111/100000/
        mc.aMCPy8EG_Zee_FxFx_2jets_HT2bias_standard111.py
    W+jets/W(ev)/
      standard111/
      delta441/200003/
        mc.aMCPy8EG_Wenu_FxFx_2jets_D441.py.template
        fxfx_exclusive_kt.patch
      event_generation/
  VV+jets/{WW,WZ,ZZ}/
  ttbar+jets/
grid/{submit,download}/
runtime/{parsers,reports}/
rivet/{analyses,plots}/
scripts/check_sample.py
```

The illustrative DSIDs `100000` and `200003` are **not confirmed
ATLAS production assignments**. The Zee reference JOs were adapted from
previous tests and are not revalidated against the new patch stack.
The original Zee HT2 Fortran files `dummy_fct.f` and
`montecarlocounter_MINE.f` remain absent; see `REQUIRED_FILES.md`.
Never replace them with unrelated source files.

**Gridpack stage:** build using HTCondor on the Analysis Facility; use
the central PDF without scale/PDF variations. Apply per-sample Fortran
patches to fresh MadGraph process sources before compilation. The tested
Condor patch is kept on a separate development branch and requires
source-pinned bootstrap **before** MadGraph imports.

**Event-generation stage:** use the corresponding gridpack on the
ATLAS Grid. The historical Zee example keeps
`MADGRAPH_PDFSETTING=None`; enabled PDF/scale reweighting still
requires implementation and validation. The separate Pythia8 dummy
event segfault from the Condor smoke also remains unresolved.

The `grid/`, `runtime/`, and `rivet/` directories are preparation
scaffolds, not operational submission, accounting, or analysis tools.
Record exact versions, configuration, patch hashes and run logs for PMG.

Static checks (missing auxiliary files correctly cause a nonzero result):

```bash
python3 scripts/check_sample.py 'JOs/V+jets/Z+jets/Z(ee)/standard111/100000'
python3 scripts/check_sample.py 'JOs/V+jets/W+jets/W(ev)/delta441/200003'
```
