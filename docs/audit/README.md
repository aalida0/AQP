# Wenu production audit

Initial read-only audit, 2026-10-30. **Operational pilot completion is documented; physics validation remains open.** No production files were changed, events generated, or jobs submitted. This commit contains reports and evidence metadata only.

The inspected original files are under `/home/aalida/AQP/Wjets/WENU/`. MadAgents reviewed the physics regime, NLO runtime, FKS/Fortran, matching, and shower interface. Review used the available MadGraph 3.5.11 package, rather than the harness's remembered 3.7.1. See [evidence and reproduction instructions](evidence.md).

| Report | Main finding |
|---|---|
| [Physics and generator](physics-generator.md) | Biased normalization needs closure; uncertainty weights are disabled; the selected PDF is NNLO while the hard process is NLO QCD. |
| [Fortran](fortran.md) | Two narrow modifications: HT² bias and a near-unity Sudakov tolerance/clamp. Build provenance and numerical tests remain necessary. |
| [FxFx and folding](fxfx-folding.md) | Requested multiplicities and thresholds agree across inspected paths; reconstructed checkpoint provenance and merging validation remain open. |
| [Condor reliability](condor-reliability.md) | Copy failures can escape the runner status; staging does not verify the pilot archive checksum; downloads use a mutable branch. |
| [Required tests](validation-plan.md) | Prioritized acceptance criteria for future scripts, fixtures, and separately authorized runtime validation. |

**Evidence standard:** “Confirmed” means direct source inspection or an existing recorded outcome. “Validation gap” means the inspected checks do not establish a required property. Proposed physics comparisons are explicitly unperformed; no claim of a demonstrated physics bias is made.

Before physics use, close normalization, checkpoint/source identity, effective shower configuration, and weighted merging checks. Before scaling production, close artifact-publication and retry/recovery checks. Existing successful scheduler exits do not close these requirements.

Scope limits: this audit did not rehash/unpack large gridpack archives, unpickle checkpoints, rebuild executables, inspect EVNT contents, or repeat integration/showering. Existing repository implementation and older reports are context; findings are tied to original-file evidence. Framework source and raw operational logs remain local.
