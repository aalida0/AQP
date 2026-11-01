# Historical Zee event-generation JO (grid submission reference).
# NOTE: this baseline disables PDF/scale reweighting. Not PMG-final.
import os

import MadGraphControl.MadGraphUtils
from MadGraphControl.MadGraphUtils import *
from MadGraphControl.MGC import MGControl

# AthGeneration/23.6.63 gridpack-related workaround.
if not hasattr(MGControl, "_original_add_runArgs"):
    MGControl._original_add_runArgs = MGControl.add_runArgs

    def _safe_add_runArgs(self, runArgs=None):
        if runArgs is None:
            return
        return MGControl._original_add_runArgs(self, runArgs)

    MGControl.add_runArgs = _safe_add_runArgs

USE_DELTA = False
FOLDING = "1, 1, 1"
REQUIRED_ACCURACY = 0.0001

evgenConfig.description = "aMcAtNlo Zee+0,1,2j NLO FxFx HT2-biased Py8"
evgenConfig.contact = ["lenart.jerala@cern.ch"]
evgenConfig.keywords += ["Z", "jets"]
evgenConfig.generators += ["aMcAtNlo", "Pythia8"]
evgenConfig.nEventsPerJob = 5000

if not is_gen_from_gridpack():
    raise RuntimeError("This JO requires the matching Zee gridpack")

process_dir = str(MADGRAPH_GRIDPACK_LOCATION)
nevents = int(5 * (runArgs.maxEvents if runArgs.maxEvents > 0
                    else evgenConfig.nEventsPerJob))
beam_energy = float(runArgs.ecmEnergy) / 2.0

# The user's historical grid-generation configuration. Full PDF/scale
# reweighting remains to be validated separately before PMG submission.
MadGraphControl.MadGraphUtils.MADGRAPH_PDFSETTING = None

mgc = MGControl()
mgc.get_config_cardloc()
mgc.getConfigFromPath(mgc.config_path)
mgc.getRunCardDict()
MadGraphControl.MadGraphUtils.my_MGC_instance = mgc

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
        "etaj": 10,
        "mll": 40,
        "mll_sf": 40,
        "mcatnlo_delta": USE_DELTA,
        "folding": FOLDING,
    },
)

config_settings = {"run_mode": 0, "nb_core": 1}
if USE_DELTA:
    pythia8_path = os.getenv("PY8PATH")
    if not pythia8_path:
        raise RuntimeError("PY8PATH is required for MC@NLO-Delta")
    config_settings["pythia8_path"] = pythia8_path

modify_config_card(process_dir=process_dir, settings=config_settings)

generate(required_accuracy=REQUIRED_ACCURACY, process_dir=process_dir,
         runArgs=runArgs, grid_pack=False)

arrange_output(process_dir=process_dir, runArgs=runArgs,
               lhe_version=3, saveProcDir=False)

include("Pythia8_i/Pythia8_A14_NNPDF23LO_EvtGen_Common.py")
include("Pythia8_i/Pythia8_aMcAtNlo.py")

PYTHIA8_nJetMax = 2
PYTHIA8_qCut = 20.0
include("Pythia8_i/Pythia8_FxFx_A14mod.py")
