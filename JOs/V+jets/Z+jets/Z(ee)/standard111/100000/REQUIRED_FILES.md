# Files needed before running this sample

This JO calls `get_files -data` for these **process-local original files**:

- `dummy_fct.f` — the validated **Zee HT2-bias** Fortran implementation.
- `montecarlocounter_MINE.f` — the user's version-pinned source
  replacement installed as `SubProcesses/montecarlocounter.f`.
- `fxfx_exclusive_kt.patch` — included in this directory; upstream
  MadGraph5_aMC PR #426. Patch needs `patch --dry-run` and
  appropriate release validation.

The original two `.f` files are not available in this conversation's
mounted sources, and therefore **are intentionally NOT replaced** with
generic or unrelated files. In particular, the currently mounted
`dummy_fct.f` contains diphoton logic and an inactive HT2 example;
it is NOT an established Zee HT2 source.

Gridpack JO requires the pre-import Condor backend source patch
and safe, isolated guard directory. It must be tested with the matching
AthGeneration/MG5 versions. The new FxFx PR #426 patch deliberately
changes the generated jet acceptance relative to historical results:
perform an explicit before/after validation before physics use.
