# Zee standard111 source inventory

All three source files requested by the JO are now **colocated here**:

- `dummy_fct.f`: the **uploaded** 94-line file
  `dummy_fct(4).f`, SHA-256
  `76f47c8fdfacd7d2136f13e5261765ab27aae21752448cae0cb4d05120e9fc08`.
  Its active bias function returns `H_T**2`; with `event_norm=bias`,
  retain weights for analysis.
- `montecarlocounter_MINE.f`: the **uploaded** 5487-line file
  `montecarlocounter_MINE(1).f`, SHA-256
  `fee80cac03c15fc5e7b85c791dbb4f7b284fb004faec47b2e3c6a33c9a861f0a`.
  Contains a Sudakov tolerance check at 100 machine epsilons.
- `fxfx_exclusive_kt.patch`: upstream MG5_aMC PR #426; replaces the
  inclusive jet-counting FxFx criterion with an exclusive-kT criterion.
  It is applied to the generated `SubProcesses/cuts.f` with a
  strict dry run before compilation.

Gridpack mode needs the **separately bootstrapped, source-pinned
Condor backend**. That backend is not patched inside the JO after
MadGraph has been imported.

Physics/PMG release requires a live gridpack → Grid event generation
→ Pythia8 validation (including named PDF/scale weights, matching
efficiency, bias and normalization). The example DSID 100000
is illustrative.
