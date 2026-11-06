# FxFx process configurations (AthGeneration/23.6.63)

Complete production-layout JobOptions are organized by process, matching
configuration, and DSID. All code here is **pending process-by-process
runtime and physics validation**; a static review alone is insufficient.

- Zee: standard111, delta111, delta221, delta441; HT2-biased with
  `event_norm=bias`, `ptj=8`, `qCut=20`, `mll=40`.
- Wenu: W+ -> e+ nu_e only (not inclusive W+/-); same HT2 bias, with
  lepton-specific cuts inherited from the one-jet reference where applicable.
- VV: opposite-sign WW -> l nu l nu, WZ -> 3l nu, ZZ -> 4l or 2l2nu.
  MadSpin decays originate from the supplied vv-jets-production archive;
  these have `ptj=10`, `qCut=25`; OS WW uses maxjetflavor=4,
  WZ/ZZ use 5. WW/WZ/ZZ require fresh validation.
- Same-sign WW has a 2-jet Born process in the supplied source and
  is deliberately NOT treated as a 0,1,2j FxFx sample here.

All setups use the user-supplied central PDF 325100 with the full
PMG uncertainty lists during *event generation*; additional PDF error
sets are disabled during gridpack integration. In particular, the WZ
source archive used a **different** central PDF (303000). The common
325100 policy is an explicit study choice, not a claim of identity to
the archived WZ sample. Cross sections must be independently checked.

**Critical:** `store_rwgt_info=True` in both gridpack construction and
event generation. Each JO loads the full PDF recipe into both MadGraph
control modules; `gridpack_compile=False` when consuming the gridpack.
Custom source patches and Fortran code must be installed before gridpack
integration. The Condor backend remains external; use the existing
`scripts/gridpack.sh` launcher with its source-pinned bootstrap.

**Validation gate:** before EVNT production, verify process generation,
PR426 applicability, MadSpin syntax/decays, gridpack integration, direct
no-recompile event generation, complete PMG weight names, negative-weight
and FxFx bookkeeping. Do not equate a 20-event smoke with physics approval.

## Zee/Wenu 0,1,2j integration benchmark (2026-11)

All eight full-multiplicity Zee and Wenu JOs explicitly request
`REQUIRED_ACCURACY=1e-3`. The existing 1j tests use `0.5` and do NOT
establish physics validity of the 2j gridpacks. The source SHA of the
`dummy_fct.f`, `montecarlocounter_MINE.f`, and
`fxfx_exclusive_kt.patch` is identical across all eight DSIDs.

Timings: the supported `scripts/gridpack.sh` launcher records exact
start/end epochs and overall Gen_tf wall time in `timing.txt`, Bash's
controller CPU in `controller_cpu.txt`, and MadGraph stage times plus
per-job HTCondor CPU in `timing_summary.json` and `.csv`.
The stage wall times are extracted from timestamped logs (lower
resolution than the overall epochs). The per-worker CPU total is
reported as definitive ONLY when `worker_accounting_complete=true`.
For restarts, HTCondor cumulative CPU is preferred and missing
history is recorded as incomplete, NOT counted as zero.

Do not infer a runtime or CPU-hour prediction from the number of
completed integration channels. Very expensive subprocesses may be last.
Pilot validations must verify that scale/PDF weights are present in
both the LHE and EVNT metadata and that the packed gridpack can be
consumed without recompiling.
