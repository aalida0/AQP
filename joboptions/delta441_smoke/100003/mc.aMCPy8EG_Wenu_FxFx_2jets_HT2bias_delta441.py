"""ATLAS Wenu+0,1,2j FxFx NLO Delta441 production from an EXISTING gridpack.

This is a smoke-test JO derived from the established Wenu event-generation JO
at generation/100000. It must NEVER create a new MG process or reintegrate
its MINT0/MINT1 grids. The input tarball is unpacked as ./madevent/ in the
worker-local scratch directory before Gen_tf starts.
"""

import os
import MadGraphControl.MadGraphUtils
from MadGraphControl.MadGraphUtils import *
from MadGraphControl.MGC import MGControl

# --------------------------------------------------------------------
# Event-generation configuration
# --------------------------------------------------------------------
GRIDPACK_ECM_ENERGY = 13000.0
USE_DELTA = True
FOLDING = "4, 4, 1"
REQUIRED_ACCURACY = 1.0e-4
LHE_OVERSAMPLING_FACTOR = 5

# --------------------------------------------------------------------
# EVGEN metadata
# --------------------------------------------------------------------
evgenConfig.description = (
    "aMcAtNlo Wenu+0,1,2j NLO FxFx HT2-biased Py8, "
    "MC@NLO-Delta matching with folding 441"
)
evgenConfig.contact = ["lenart.jerala@cern.ch"]
evgenConfig.keywords += ["W", "jets"]
evgenConfig.generators += ["aMcAtNlo", "Pythia8"]
evgenConfig.nEventsPerJob = 5000

# --------------------------------------------------------------------
# Fail closed: this JO is strictly for generation from existing gridpack
# --------------------------------------------------------------------
if not is_gen_from_gridpack():
    raise RuntimeError(
        "AQP_DELTA441_ABORT_NO_EXISTING_GRIDPACK: "
        "extract the Delta441 archive as ./madevent/ before running Gen_tf"
    )
if abs(float(runArgs.ecmEnergy) - GRIDPACK_ECM_ENERGY) > 1.0e-6:
    raise RuntimeError("AQP_DELTA441_ABORT_WRONG_ECM: use --ecmEnergy=13000")

process_dir = str(MADGRAPH_GRIDPACK_LOCATION)
if not os.path.isfile(os.path.join(process_dir, "SubProcesses", "job_status.pkl")):
    raise RuntimeError("AQP_DELTA441_ABORT_MISSING_RECOVERED_CHECKPOINT")

requested_events = (
    int(runArgs.maxEvents)
    if runArgs.maxEvents > 0
    else int(evgenConfig.nEventsPerJob)
)
nevents = LHE_OVERSAMPLING_FACTOR * requested_events
beam_energy = GRIDPACK_ECM_ENERGY / 2.0

print("AQP_DELTA441_EXISTING_GRIDPACK_ONLY")
print("AQP_DELTA441_LHE_EVENTS_REQUESTED=%d" % nevents)

# --------------------------------------------------------------------
# Legacy AthGeneration/23.6.63 MadGraphControl gridpack initialization
# This exact card-loading sequence follows generation/100000.
# --------------------------------------------------------------------
MadGraphControl.MadGraphUtils.MADGRAPH_PDFSETTING = None

_mgc = MGControl()
_mgc.get_config_cardloc()
_mgc.getConfigFromPath(_mgc.config_path)
_mgc.getRunCardDict()
MadGraphControl.MadGraphUtils.my_MGC_instance = _mgc

print("AQP_DELTA441_MGCONTROL_CARDS_LOADED")

# --------------------------------------------------------------------
# Run card: match the existing Delta441 FxFx integration settings
# --------------------------------------------------------------------
modify_run_card(
    process_dir=process_dir,
    runArgs=runArgs,
    settings={
        "ebeam1": beam_energy,
        "ebeam2": beam_energy,
        "event_norm": "bias",
        "maxjetflavor": 5,
        "parton_shower": "PYTHIA8",
        "nevents": nevents,
        "req_acc": REQUIRED_ACCURACY,
        "ickkw": 3,
        "jetradius": 1.0,
        "ptj": 8,
        "etaj": -1.0,
        "mcatnlo_delta": USE_DELTA,
        "folding": FOLDING,
    },
)

# --------------------------------------------------------------------
# Execute locally on the HTCondor worker (do not submit nested jobs)
# --------------------------------------------------------------------
pythia8_path = os.getenv("PY8PATH")
if not pythia8_path:
    raise RuntimeError("AQP_DELTA441_ABORT_PY8PATH_NOT_SET")

modify_config_card(
    process_dir=process_dir,
    settings={
        "run_mode": 0,
        "nb_core": 1,
        "pythia8_path": pythia8_path,
    },
)

# In an already-extracted gridpack, the source files and integration grids
# already exist. This is the known working event-generation pattern.
generate(
    required_accuracy=REQUIRED_ACCURACY,
    process_dir=process_dir,
    runArgs=runArgs,
    grid_pack=False,
)

arrange_output(
    process_dir=process_dir,
    runArgs=runArgs,
    lhe_version=3,
    saveProcDir=False,
)

# --------------------------------------------------------------------
# Pythia8 FxFx shower (matching the existing generation/100000 JO)
# --------------------------------------------------------------------
include("Pythia8_i/Pythia8_A14_NNPDF23LO_EvtGen_Common.py")
include("Pythia8_i/Pythia8_aMcAtNlo.py")

PYTHIA8_nJetMax = 2
PYTHIA8_qCut = 20.0

include("Pythia8_i/Pythia8_FxFx_A14mod.py")
