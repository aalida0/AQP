// Diagnostic copy of Rivet MC_WKTSPLITTINGS:
// source: https://heprivet.org/analyses/MC_WKTSPLITTINGS/
// Only physics-irrelevant changes: analysis class/name and MET projection key.
// Unlike AQP_WKTSPLITTINGS, selection logic and projection declaration style
// are kept the same as the published implementation.
// This diagnoses whether the "MET" projection lookup key is the failure.
#include "Rivet/Analyses/MC_KTSPLITTINGS_BASE.hh"
#include "Rivet/Projections/FastJets.hh"
#include "Rivet/Projections/LeptonFinder.hh"
#include "Rivet/Projections/MissingMomentum.hh"
#include "Rivet/Projections/PromptFinalState.hh"
#include "Rivet/Projections/VetoedFinalState.hh"

namespace Rivet {

  class AQP_WKTSPLITTINGS_METKEY : public MC_KTSPLITTINGS_BASE {
  public:
    AQP_WKTSPLITTINGS_METKEY()
      : MC_KTSPLITTINGS_BASE("AQP_WKTSPLITTINGS_METKEY", 4, "Jets") {}

    void init() {
      _dR = (getOption("SCHEME") == "BARE") ? 0.0 : 0.2;
      _lepton = (getOption("LMODE") == "MU") ? PID::MUON : PID::ELECTRON;
      const double ETACUT = getOption<double>("ABSETALMAX", 3.5);
      const double PTCUT = getOption<double>("PTLMIN", 25.);
      const Cut cut = Cuts::abseta < ETACUT && Cuts::pT > PTCUT * GeV;

      LeptonFinder lf(_dR, cut && Cuts::abspid == _lepton);
      declare(lf, "Leptons");

      // Only changed projection: original key "MET" -> "AQP_W_MET".
      declare(MissingMomentum(), "AQP_W_MET");

      VetoedFinalState jetinput;
      jetinput.vetoFinalState(lf);
      const double R = getOption<double>("R", 0.6);
      FastJets fj(jetinput, JetAlg::KT, R);
      declare(fj, "Jets");

      MC_KTSPLITTINGS_BASE::init();
    }

    void analyze(const Event& event) {
      const P4& pmiss = apply<MissingMom>(event, "AQP_W_MET").missingMom();
      if (pmiss.pT() < 25 * GeV) vetoEvent;

      const Particles& ls = apply<LeptonFinder>(event, "Leptons").particles();
      const int ifound = closestMassIndex(ls, pmiss, 80.4 * GeV,
                                          60 * GeV, 100 * GeV);
      if (ifound < 0) vetoEvent;

      MC_KTSPLITTINGS_BASE::analyze(event);
    }

    void finalize() {
      MC_KTSPLITTINGS_BASE::finalize();
    }

  protected:
    double _dR;
    PdgId _lepton;
  };

  RIVET_DECLARE_PLUGIN(AQP_WKTSPLITTINGS_METKEY);
}
