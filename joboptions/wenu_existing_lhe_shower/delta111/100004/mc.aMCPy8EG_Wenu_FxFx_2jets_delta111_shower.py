"""AQP Wenu delta111: shower existing 1000-event LHE using FxFx.

Source: preserved Events/run_01/events.lhe.gz from the August Wenu run.
This JO does not call MadGraph, build grids, or perform event generation.
It is a diagnostic of the existing LHE, not an ATLAS production-approved JO.
"""
if not getattr(runArgs, "inputGeneratorFile", None):
    raise RuntimeError("AQP_FXFX_SHOWER_ABORT_MISSING_INPUT_LHE")
if not getattr(runArgs, "outputEVNTFile", None):
    raise RuntimeError("AQP_FXFX_SHOWER_ABORT_MISSING_OUTPUT_EVNT")
if abs(float(runArgs.ecmEnergy) - 13000.0) > 1e-6:
    raise RuntimeError("AQP_FXFX_SHOWER_ABORT_WRONG_ECM")

evgenConfig.description = (
    "Wenu+0,1,2j FxFx Pythia8 shower-only of 1000 preserved LHE events; "
    "MC@NLO-Delta folding 111; HT2 generation bias"
)
evgenConfig.contact = ["lenart.jerala@cern.ch"]
evgenConfig.keywords += ["W", "jets"]
evgenConfig.generators += ["aMcAtNlo", "Pythia8"]
evgenConfig.nEventsPerJob = 200

print("AQP_FXFX_SHOWER_ONLY_USING_INPUT_GENERATOR_FILE")
print("AQP_FXFX_SHOWER_INPUT=%s" % runArgs.inputGeneratorFile)
print("AQP_FXFX_SHOWER_MADGRAPH_NOT_INVOKED")
print("AQP_WENU_SHOWER_CONFIG=delta111")
print("AQP_WENU_RECOVERED_LHE_SMOKE=1000")

include("Pythia8_i/Pythia8_A14_NNPDF23LO_EvtGen_Common.py")
include("Pythia8_i/Pythia8_aMcAtNlo.py")
PYTHIA8_nJetMax = 2
PYTHIA8_qCut = 20.0
include("Pythia8_i/Pythia8_FxFx_A14mod.py")
genSeq.Pythia8.Commands += ["SoftQCD:inelastic = off"]
print("AQP_FXFX_SHOWER_CONFIGURATION=FxFx_2jets_qCut20_SoftQCDoff")
