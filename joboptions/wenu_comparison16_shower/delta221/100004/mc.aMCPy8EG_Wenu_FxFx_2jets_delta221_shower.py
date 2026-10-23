"""Shower-only FxFx validation of the delta221 Wenu LHE file.

This JO MUST NOT run MadGraph: it consumes --inputGeneratorFile and writes EVNT.
The input LHE is supplied by the preceding generation stage.
No MINT0/MINT1/MINT2, gridpack extraction or modifications are performed.
"""

if not hasattr(runArgs, "inputGeneratorFile") or not runArgs.inputGeneratorFile:
    raise RuntimeError("AQP_FXFX_SHOWER_ABORT_MISSING_INPUT_LHE")
if not hasattr(runArgs, "outputEVNTFile"):
    raise RuntimeError("AQP_FXFX_SHOWER_ABORT_NOT_EVNT_OUTPUT")
if abs(float(runArgs.ecmEnergy) - 13000.0) > 1.0e-6:
    raise RuntimeError("AQP_FXFX_SHOWER_ABORT_WRONG_ECM")

evgenConfig.description = (
    "Shower-only validation: Wenu+0,1,2j NLO FxFx HT2-biased "
    "MC@NLO-Delta folding 441, seed-237 LHE"
)
evgenConfig.contact = ["lenart.jerala@cern.ch"]
evgenConfig.keywords += ["W", "jets"]
evgenConfig.generators += ["aMcAtNlo", "Pythia8"]
evgenConfig.nEventsPerJob = 5000

print("AQP_FXFX_SHOWER_ONLY_USING_INPUT_GENERATOR_FILE")
print("AQP_FXFX_SHOWER_INPUT=%s" % runArgs.inputGeneratorFile)
print("AQP_FXFX_SHOWER_MADGRAPH_NOT_INVOKED")
print("AQP_WENU_SHOWER_CONFIG=delta221")

# Use the same ATLAS Pythia8 tune, aMC@NLO interface, and FxFx settings
# as the production JO, but deliberately do not import MadGraphControl.
include("Pythia8_i/Pythia8_A14_NNPDF23LO_EvtGen_Common.py")
include("Pythia8_i/Pythia8_aMcAtNlo.py")

PYTHIA8_nJetMax = 2
PYTHIA8_qCut = 20.0
include("Pythia8_i/Pythia8_FxFx_A14mod.py")

# For an external hard-process LHE sample, SoftQCD process generation
# must not be enabled alongside JetMatchingMadgraph. The TXT-only
# transform enables dummy SoftQCD event generation, but this is an
# actual EVNT shower of the supplied LHE and does not need a dummy.
genSeq.Pythia8.Commands += ["SoftQCD:inelastic = off"]
print("AQP_FXFX_SHOWER_CONFIGURATION=FxFx_2jets_qCut20_SoftQCDoff")
