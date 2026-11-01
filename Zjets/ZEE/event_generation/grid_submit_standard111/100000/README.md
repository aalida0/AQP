# Historical Zee Grid event-generation JO

This is the user's formerly executed baseline with `grid_pack=False`,
`run_mode=0`, `nb_core=1`, central-only
`MADGRAPH_PDFSETTING=None`, and Pythia8 FxFx. It assumes the matching
Zee standard111 HT2 gridpack was already produced.

The ultimate workflow requires **PDF/scale variations during grid event
generation**. That feature is not yet implemented here and must be
tested for expected LHE weight names, nonzero weights, and grid runtime.
The 2026-11-01 smoke had an unrelated downstream Pythia dummy-event crash.
