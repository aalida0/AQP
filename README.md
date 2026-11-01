# AQP — FxFx NLO sample production

ATLAS/PMG reviewable JobOptions, source patches, and auxiliary Fortran files
are organized **by process, configuration, and DSID**, in the same style
as the original Zee production layout. JOs are normal, complete `mc.*.py`
files, not wrappers around a private runtime framework.

```text
Zjets/ZEE/standard111/100000/
  mc.aMCPy8EG_Zee_FxFx_2jets_HT2bias_standard111.py
  fxfx_exclusive_kt.patch
  REQUIRED_FILES.md                    # Missing original Zee HT2 files
Zjets/ZEE/event_generation/grid_submit_standard111/100000/
  mc.aMCPy8EG_Zee_FxFx_2jets_HT2bias_standard111.py
Wjets/Wenu/delta441/200003/
  mc.aMCPy8EG_Wenu_FxFx_2jets_D441.py.template  # Unvalidated scaffold
  fxfx_exclusive_kt.patch
VVjets/{WW,WZ,ZZ}/
ttbarjets/
grid/{submit,download}/
runtime/{parsers,reports}/
rivet/{analyses,plots}/
scripts/
```

The sample IDs 100000 and 200003 are **examples**; do not assume an
assigned ATLAS DSID. Zee files are adapted from user-provided historical
JOs and **have not been revalidated** against the current patch stack.
The sample's `REQUIRED_FILES.md` documents the two absent process-specific
Fortran sources. Do not copy a generic `dummy_fct.f` as an HT2 bias function.

**Gridpack stage:** Condor gridpack integration, central PDF, no PDF/scale
variations, process-local Fortran patches applied to a fresh MadGraph process
*before* compilation. Condor backend must be installed via a pinned,
pre-import AF launcher (not by editing CVMFS from inside the JO).

**Event generation stage:** separate, readable JO for each process/config,
ATLAS Grid using its gridpack; full PDF/scale reweighting is a **pending
implementation/validation**. The Zee event JO records the actual legacy
`MADGRAPH_PDFSETTING=None` configuration; this must change before claiming
systematic-weight production. Showering requires a validated Pythia8 FxFx
chain. The no-reweight Condor smoke completed the LHE workflow, but its
Athena dummy Pythia event segfault is still unresolved.

Proposed follow-on tooling lives in `grid/`, `runtime/`, and `rivet/`.
These directories are planning scaffolds, **not working production scripts**.
Each sample's exact software versions, patch checksums and run logs should
be archived for PMG review.

Run static inspection with:

```bash
python3 scripts/check_sample.py Zjets/ZEE/standard111/100000
python3 scripts/check_sample.py Wjets/Wenu/delta441/200003
```
