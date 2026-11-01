# Zee + 0,1,2 jets NLO FxFx — corrected exclusive-kT ME cut

This test JobOption rebuilds the **integration grids and upper envelopes**
with the exact Template/NLO/SubProcesses/cuts.f change from
[MG5_aMC PR #426](https://github.com/mg5amcnlo/mg5amcnlo/pull/426)
(merged into the upstream 3.5.17 branch on 2026-09-28).

The old ME-side FxFx cut used *inclusive* kT clustering with R=1,
artificially rejecting close parton pairs for DeltaRjj<1. Pythia8
applies an *exclusive* kT merging veto. The corrected check uses the
exclusive FastJet merging scale, agreeing with the shower resolution.

## Physics configuration (not yet production-approved)

- MG5_aMC 3.5.11.atlas13 from AthGeneration/23.6.63, 13 TeV.
- p p > e+ e- + 0,1,2 jets at NLO QCD FxFx (@0, @1, @2).
- Standard MC@NLO matching; folding 111; not MC@NLO-Delta.
- FxFx merging: ickkw=3, ptj=8 GeV, jetradius=1.0,
  Pythia8 nJetMax=2, qCut=20 GeV.
- PMG scale/PDF recipe retained from the validated 1-jet smoke JO.
- req_acc=1e-4 for the integration (potentially expensive).
- No HT2 bias; preserve this baseline definition in comparisons.

## 1. Build a completely new gridpack

This is a **new grid/envelope integration**. Recompiling event executables
for an old gridpack cannot implement a changed ME-side generation cut.

On UChicago AF, using the existing source-pinned Condor bootstrap
required by scripts/gridpack.sh:

    cd ~/NWR
    git fetch origin
    git switch test/fxfx-pr426-zee2jets
    git pull --ff-only
    setupATLAS
    asetup 23.6.63,AthGeneration
    python3 -m unittest discover -s tests -p 'test_zee2jet_pr426.py' -v
    python3 scripts/check_sample.py tests/2jet/999998
    bash -n scripts/gridpack.sh
    bash scripts/gridpack.sh tests/2jet/999998 13000 10 34131

The launcher prints RUN, OUTPUT and ATTACH. It launches generation in
tmux; submit only once, monitor its Condor jobs, and verify
result_exit=0 in timing.txt inside OUTPUT. Do not modify its workdir
while jobs are running. Verify that FXFX_PR426_EXCLUSIVE_KT_VERIFIED
appears in log.generate and patching exits 0 before MINT integration.

The gridpack, logs and timing go to
/data/$USER/NWR/gridpacks/tests-2jet-999998/<run>/.

## 2. Smoke-test events and shower

Pass the exact archived GRID.tar.gz path from the OUTPUT directory:

    bash scripts/validate_zee2jet_pr426_gridpack.sh \
      /data/aalida/NWR/gridpacks/tests-2jet-999998/<run>/<actual-GRID.tar.gz> \
      20 34132 --recompile

The wrapper stages a fresh gridpack copy under
~/gridpack-validation/zee2jet.*, recompiles only event binaries,
reuses the new corrected integration, and checks the ATLAS EVNT
CollectionTree event count. If this passes, extend to 1000 EVNT.
This does not yet constitute physics validation.

## 3. Physics comparison

Compare against a documented legacy unpatched **2-jet** gridpack with
identical nominal PDFs, matching, scales and kinematic cuts. Measure
DeltaR(j1,j2) in bins of pT(Z), particularly 0<DeltaR<1, and DeltaR(bb)
from g->bb when applicable. Preserve the old and new cross-section
normalization and integration provenance. The 1-jet smoke gridpack
cannot demonstrate the two-parton defect.

All work here remains on a test branch, not main.
