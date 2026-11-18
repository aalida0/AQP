// AQP W+jets kT-splitting smoke-test plugin.
//
// Adapted from the Rivet MC_WKTSPLITTINGS reference analysis
// (https://heprivet.org/analyses/MC_WKTSPLITTINGS/).
// Preserve its event selection and MC_KTSPLITTINGS_BASE histograms.
//
// This plugin uses a distinct analysis name and distinct MET/lepton projection
// keys to diagnose the Rivet 4.1.2 "No projection 'MET' found" failure.
// It does NOT replace the official Rivet analysis or modify the installation.

#include "Rivet/Analyses/MC_KTSPLITTINGS_BASE.hh"
#include "Rivet/Projections/FastJets.hh"
#include "Rivet/Projections/LeptonFinder.hh"
#include "Rivet/Projections/MissingMomentum.hh"
#include "Rivet/Projections/VetoedFinalState.hh"

namespace Rivet {

  class AQP_WKTSPLITTINGS : public MC_KTSPLITTINGS_BASE {
  public:
    AQP_WKTSPLITTINGS()
      : MC_KTSPLITTINGS_BASE("AQP_WKTSPLITTINGS", 4, "Jets") {}

    void init() {
      const double dressRadius = getOption("SCHEME") == "BARE" ? 0.0 : 0.2;
      const PdgId lepton = getOption("LMODE") == "MU" ? PID::MUON : PID::ELECTRON;
      const double etaCut = getOption<double>("ABSETALMAX", 3.5);
      const double ptCut = getOption<double>("PTLMIN", 25.0);

      const Cut leptonCut = Cuts::abseta < etaCut &&
                            Cuts::pT > ptCut * GeV &&
                            Cuts::abspid == lepton;
      LeptonFinder leptons(dressRadius, leptonCut);
      declare("AQP_W_LEPTONS", leptons);
      declare("AQP_W_MET", MissingMomentum());

      VetoedFinalState jetInput;
      jetInput.vetoFinalState(leptons);
      const double jetRadius = getOption<double>("R", 0.6);
      FastJets jets(jetInput, JetAlg::KT, jetRadius);
      declare("Jets", jets);

      MC_KTSPLITTINGS_BASE::init();
    }

    void analyze(const Event& event) {
      const P4& missing = apply<MissingMomentum>(event, "AQP_W_MET").missingMom();
      if (missing.pT() < 25 * GeV) vetoEvent;

      const Particles& leptons =
          apply<LeptonFinder>(event, "AQP_W_LEPTONS").particles();
      const int candidate = closestMassIndex(leptons, missing,
                                              80.4 * GeV, 60 * GeV, 100 * GeV);
      if (candidate < 0) vetoEvent;
      MC_KTSPLITTINGS_BASE::analyze(event);
    }

    void finalize() {
      MC_KTSPLITTINGS_BASE::finalize();
    }
  };

  RIVET_DECLARE_PLUGIN(AQP_WKTSPLITTINGS);
}
