# Physics and generator configuration

Evidence IDs resolve through [the index](evidence.md); line numbers refer to originals.

**Confirmed configuration.** The original Delta441 JO requests electron-family charged-current final states with 0/1/2 jets at NLO QCD, a massless-b loop model, and b in both beam/jet definitions ([E01](evidence.md#e01):53–60). The recovered card records 13 TeV proton beams, LHAPDF 325100, five jet flavors, biased event normalization, dynamical scales, and Pythia8 ([E04](evidence.md#e04):6,13–28,64); bottom mass is zero ([E06](evidence.md#e06):16). No flavor mismatch was demonstrated in these inspected settings.

| ID / priority | Finding and consequence | Required closure |
|---|---|---|
| P01 / high | **Validation gap:** `event_norm=bias` activates the supplied kinematic HT² bias ([E08](evidence.md#e08):86–91). Installed NLO runtime explicitly marks its biased integration-summary rate unsuitable as a physical cross section ([MG02](evidence.md#mg02):3191–3192). The LHE auditor disclaims physical normalization ([E21](evidence.md#e21):4–6,97–100). | Trace bias compensation through collected LHE and shower weights; demonstrate signed normalized yield/spectrum closure with a suitable reference. |
| P02 / high | **Confirmed:** scale/PDF reweight switches are false and `systematics_program=None`, despite scale-factor lists being present ([E04](evidence.md#e04):31–34,66–68). | Inspect actual weight definitions and records; document a nominal-only scope or a separately validated uncertainty procedure. Configured lists do not prove weights exist. |
| P03 / medium | **Confirmed choice requiring rationale:** PDF 325100 resolves to `NNPDF31_nnlo_as_0118_luxqed`, with five flavors and αs(MZ)=0.118 ([PDF02](evidence.md#pdf02):1219; [PDF01](evidence.md#pdf01):1,10,12,25). | Document why an NNLO PDF is used with NLO hard matrix elements. This choice alone is not a demonstrated error. |
| P04 / medium | **Confirmed scope:** `ptl=0`, `etal=-1`; custom cuts return acceptance ([E04](evidence.md#e04):43–44; [E08](evidence.md#e08):37). | Define the analysis fiducial selection explicitly before comparing yields; these inputs do not establish electron acceptance. |
| P05 / high | **Validation gap:** `req_acc=0.0001` is requested, while recovery supplies existing stage-1 results ([E04](evidence.md#e04):3; [E11](evidence.md#e11):129–149). | Report achieved integration uncertainty and channel diagnostics separately from requested accuracy and event count. |

**Weight diagnostics.** The current auditor reports sign fractions and `signed_weight_dilution` ([E21](evidence.md#e21):69–100), but omits the weight-square sum. For recorded weights define S=Σw, A=Σ|w|, Q=Σw². Its dilution D=A²/S² measures sign cancellation; N_eff=S²/Q also includes magnitude dispersion. Record N, S, A, Q and N_eff in analysis bins, with explicit zero-denominator handling. These are weight diagnostics, not a replacement for normalization or correlation accounting.

**Proposed, unperformed physics comparisons:** charge-separated lepton spectra, boson recoil, jet multiplicities, leading-jet spectra and hard tails, with consistent normalization and independent-seed uncertainties. Standard/Delta differences must be assessed at the claimed perturbative accuracy; lower negative-weight fractions alone cannot establish improved physics precision.
