# ATLAS Grid event generation

Each `grid_submit_<configuration>/<DSID>/` contains the complete
corresponding `mc.*.py`. Gridpack production is separate and uses
Condor. Grid generation must request the intended PDF/scale weights,
validate the generated LHE weight block, and perform Pythia8 FxFx
showering. Use the exact matching gridpack.
