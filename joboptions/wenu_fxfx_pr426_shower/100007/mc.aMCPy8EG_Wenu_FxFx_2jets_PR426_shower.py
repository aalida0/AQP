"""AQP Wenu Standard111 FxFx PR426 A/B: Pythia8 shower ONLY.

Reads an existing LHE using runArgs.inputGeneratorFile. Absolutely no
MadGraph integration, generation, patching, gridpack, or custom cuts.
Both PR426 variants use IDENTICAL Pythia8 settings; the case is
metadata only and is supplied as AQP_FXFX_PR426_CASE.
"""

import os

case = os.environ.get("AQP_FXFX_PR426_CASE", "")
if case not in ("before", "after"):
    raise RuntimeError("AQP_FXFX_PR426_SHOWER_CASE_REQUIRED")

if not getattr(runArgs, "inputGeneratorFile", None):
    raise RuntimeError("AQP_FXFX_PR426_SHOWER_MISSING_INPUT")
if not getattr(runArgs, "outputEVNTFile", None):
    raise RuntimeError("AQP_FXFX_PR426_SHOWER_MISSING_EVNT_OUTPUT")
if abs(float(runArgs.ecmEnergy) - 13000.) > 1e-6:
    raise RuntimeError("AQP_FXFX_PR426_SHOWER_WRONG_ECM")
if int(runArgs.maxEvents) <= 0:
    raise RuntimeError("AQP_FXFX_PR426_SHOWER_REQUIRE_POSITIVE_MAXEVENTS")

evgenConfig.description = (
    "Wenu+0,1,2 jets FxFx Standard111; Pythia8 A14 "
    "shower-only PR426 " + case + " diagnostic"
)
evgenConfig.contact = ["amine.alida@cern.ch"]
evgenConfig.keywords += ["W", "jets"]
evgenConfig.generators += ["aMcAtNlo", "Pythia8"]
# ATLAS EvgenJobTransforms requires nEventsPerJob > 10000 to be a
# multiple of 10000. It is metadata, not the events actually requested:
# Gen_tf.py --maxEvents controls the latter. For the 18k-event FxFx
# shower request, advertise 20k while keeping --maxEvents=18000.
_requested_evnt = int(runArgs.maxEvents)
evgenConfig.nEventsPerJob = (
    ((_requested_evnt + 9999) // 10000) * 10000
    if _requested_evnt > 10000 else _requested_evnt
)
print(
    "AQP_FXFX_PR426_SHOWER_REQUESTED_EVNT=%d_NEV_PER_JOB=%d"
    % (_requested_evnt, evgenConfig.nEventsPerJob)
)

print("AQP_FXFX_PR426_SHOWER_CASE=" + case)
print("AQP_FXFX_PR426_SHOWER_INPUT=" + str(runArgs.inputGeneratorFile))
print("AQP_FXFX_PR426_SHOWER_MADGRAPH_NOT_INVOKED")

include("Pythia8_i/Pythia8_A14_NNPDF23LO_EvtGen_Common.py")
include("Pythia8_i/Pythia8_aMcAtNlo.py")

# These are the SAME as in the original Wenu Standard111 JO.
PYTHIA8_nJetMax = 2
PYTHIA8_qCut = 20.0
include("Pythia8_i/Pythia8_FxFx_A14mod.py")
genSeq.Pythia8.Commands += ["SoftQCD:inelastic = off"]

print("AQP_FXFX_PR426_SHOWER_FXFX_NJETMAX=2_QCUT=20_A14")
