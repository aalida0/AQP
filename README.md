# AQP — FxFx NLO sample production

One complete **process/configuration/DSID JobOption**, plus its own
Fortran sources and patches, is used for **both gridpack production
and Grid event generation**. The execution mode is selected by the
presence of an input MadGraph gridpack (via `is_gen_from_gridpack()`).

```text
JOs/
  V+jets/
    Z+jets/Z(ee)/
      standard111/100000/
        mc.aMCPy8EG_Zee_FxFx_2jets_HT2bias_standard111.py
        dummy_fct.f
        montecarlocounter_MINE.f
        fxfx_exclusive_kt.patch
      delta111/
      delta221/
      delta441/
    W+jets/W(ev)/
      standard111/
      delta441/200003/
  VV+jets/{WW,WZ,ZZ}/
  ttbar+jets/
grid/
  event_generation/
  submit/
  download/
runtime/{parsers,reports}/
rivet/{analyses,plots}/
scripts/check_sample.py
```

**Gridpack build:** No input gridpack; use Condor and central PDF
only, no scale/PDF variations. Patches and Fortran overrides are
installed in the new MadGraph process before compilation.
The Condor backend patch requires a source-pinned **pre-import**
launcher on AF (maintained on the experimental Condor branch);
merely having `cluster_type=condor` does not install it.

**Grid event production:** Supply the matching gridpack to the SAME
JO on PanDA. `run_mode=0` and `nb_core=1` with the
PDF/scale variations configured in the JO, followed by
`arrange_output()` and Pythia8 FxFx. The example's reweighting
mode is **not yet verified in a live Grid task**; validate the
LHE weight names, expected PDF sets, and shower events before PMG use.

The sample numbers `100000` and `200003` are illustrative, not
approved DSIDs. The Zee source files are exactly the user-provided
`dummy_fct(4).f` and `montecarlocounter_MINE(1).f`,
committed under the correct production basenames.
The active `H_T^2` bias function is in `dummy_fct.f`;
`montecarlocounter_MINE.f` contains a numerical Sudakov tolerance
check (`eps=100*epsilon(1d0)`). The FxFx
exclusive-kT patch is sourced from MG5_aMC PR #426.
The **combination has not yet been runtime validated** and the patch
must pass a dry run on the generated source.

The `grid/`, `runtime/`, and `rivet/` directories describe
automation stages, but are not yet end-to-end working pipelines.

```bash
python3 scripts/check_sample.py 'JOs/V+jets/Z+jets/Z(ee)/standard111/100000'
```
