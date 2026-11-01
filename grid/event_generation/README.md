# Event generation on the ATLAS Grid

Do **not** copy or maintain another `mc.*.py` here. Each job must
use the same process/configuration/DSID JO from `JOs/` that was
used to build its corresponding gridpack.

The JO determines the mode with `is_gen_from_gridpack()`:
when an input gridpack is present, it sets `grid_pack=False`,
configures `run_mode=0`, enables the selected central-PDF,
PDF-set and scale variations, arranges the LHE and configures the
Pythia8 FxFx shower. Without an input gridpack, it creates
a Condor gridpack (on the AF only) without extra PDF/scale weights.

Prior to a PMG/Grid submission, check the gridpack ID and path,
matching process/Delta/folding/HT2 settings, `get_files` lookup
of auxiliary sources, expected weight labels in the LHE output,
successful showering, FxFx efficiency, and provenance.

No grid task submission tooling is implemented here yet.
