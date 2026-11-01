# JOs/V+jets/W+jets/W(ev)/delta441/200003 — example layout, not a registered DSID

Illustrative Wenu FxFx 0,1,2-jet configuration: MC@NLO-Delta with folding 441 and no HT2 bias. **Do not submit**. The source file is named `.py.template` until the configuration and its patches have been validated.

All source patches and any process-specific Fortran `.f` files go **directly in this same DSID directory** beside the JO. The JO fetches required basenames using ATLAS `get_files -data`. The FxFx patch is included; the tested Delta tolerance patch has not yet been included. The source-pinned Condor patch needs a pre-import AF launcher; it cannot safely be hot-patched after MadGraph is loaded.

Before releasing a real `mc.*.py`: confirm DSID and PMG process settings; include and validate all mandatory sources; test both central-only gridpack and full Grid reweighting; verify a real Pythia8 shower; record exact patch hashes, timings, NWF, FxFx efficiency and Rivet histograms.
