# Zee FxFx

The unified standard111 Zee JobOption is in
`standard111/100000/` with its `dummy_fct.f` HT2 bias,
`montecarlocounter_MINE.f` and FxFx exclusive-kT patch.

The single JO uses `GRIDPACK_MODE = not is_gen_from_gridpack()`.
Condor gridpack creation uses central PDF only; event generation from
the same gridpack uses PDF/scale reweighting and Pythia8 FxFx.

**Status:** scaffold adapted from the user's older two JOs and source
files. The combined modes, patched Condor backend, upstream FxFx cut
fix, Grid reweighting and real shower still need end-to-end testing.
Further configurations: delta111, delta221 and delta441.
