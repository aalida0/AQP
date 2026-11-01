# PMG JobOptions

Each physics channel contains per-configuration and per-DSID directories.
Keep exactly **one full `mc.*.py`** plus its required `.f`, `.patch`
and process metadata in that DSID directory.

The same JO selects between Condor gridpack building and ATLAS Grid
event generation via `is_gen_from_gridpack()`. Do not maintain a
second JO under an `event_generation/` directory.

Grid submission instructions and datasets belong under top-level
`grid/event_generation/`.
