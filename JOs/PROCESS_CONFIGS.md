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
