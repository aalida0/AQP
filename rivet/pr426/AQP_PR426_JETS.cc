// W->e nu + jets: before/after MG5_aMC PR426 FxFx generation-cut test.
// Shapes only: not an absolute cross-section measurement.
#include <algorithm>
#include <cstddef>
#include "Rivet/Analysis.hh"
#include "Rivet/Projections/FinalState.hh"
#include "Rivet/Projections/VetoedFinalState.hh"
#include "Rivet/Projections/PromptFinalState.hh"
#include "Rivet/Projections/FastJets.hh"

namespace Rivet {
class AQP_PR426_JETS : public Analysis {
public:
  RIVET_DEFAULT_ANALYSIS_CTOR(AQP_PR426_JETS);
  void init() {
    const PromptFinalState electrons(Cuts::abspid == PID::ELECTRON);
    declare(electrons, "Electrons");
    const PromptFinalState nus(Cuts::abspid == PID::NU_E);
    declare(nus, "NuE");
    VetoedFinalState jetFS(FinalState(Cuts::abseta < 5.0));
    jetFS.vetoNeutrinos();
    jetFS.addVetoOnThisFinalState(electrons);
    declare(FastJets(jetFS, JetAlg::ANTIKT, 0.4), "Jets");

    book(_h_njets, "njets", 9, -0.5, 8.5);
    book(_h_ptj1, "ptj1", 50, 0., 500.);
    book(_h_ptj2, "ptj2", 50, 0., 500.);
    book(_h_ptw, "ptw", 50, 0., 500.);
    // 0.05 bins probe 0.4 < DeltaR(j1,j2) < 1.0.
    book(_h_drjj, "drjj", 60, 0., 3.);
    book(_h_drjj_ptw_lt100, "drjj_ptw_lt100", 60, 0., 3.);
    book(_h_drjj_ptw_100_200, "drjj_ptw_100_200", 60, 0., 3.);
    book(_h_drjj_ptw_ge200, "drjj_ptw_ge200", 60, 0., 3.);
  }

  void analyze(const Event& event) {
    // Rivet 4 fills nominal weights (including negative weights).
    const Jets jets = apply<FastJets>(event, "Jets")
      .jetsByPt(Cuts::pT > 30*GeV && Cuts::abseta < 4.4);
    _h_njets->fill(std::min(jets.size(), size_t(8)));
    if (!jets.empty()) _h_ptj1->fill(jets[0].pT()/GeV);
    if (jets.size() < 2) return;
    _h_ptj2->fill(jets[1].pT()/GeV);
    const double dr = deltaR(jets[0].momentum(), jets[1].momentum());
    _h_drjj->fill(dr);

    const Particles els = apply<PromptFinalState>(event, "Electrons").particlesByPt();
    const Particles nus = apply<PromptFinalState>(event, "NuE").particlesByPt();
    if (els.empty() || nus.empty()) return;
    // Leading prompt e and electron-neutrino: diagnostic pT(W) proxy.
    const double ptw = (els[0].momentum()+nus[0].momentum()).pT()/GeV;
    _h_ptw->fill(ptw);
    if (ptw < 100.) _h_drjj_ptw_lt100->fill(dr);
    else if (ptw < 200.) _h_drjj_ptw_100_200->fill(dr);
    else _h_drjj_ptw_ge200->fill(dr);
  }

  void finalize() {} // Keep raw signed shapes; normalize in plotting.
private:
  Histo1DPtr _h_njets, _h_ptj1, _h_ptj2, _h_ptw, _h_drjj;
  Histo1DPtr _h_drjj_ptw_lt100, _h_drjj_ptw_100_200, _h_drjj_ptw_ge200;
};
RIVET_DECLARE_PLUGIN(AQP_PR426_JETS);
}
