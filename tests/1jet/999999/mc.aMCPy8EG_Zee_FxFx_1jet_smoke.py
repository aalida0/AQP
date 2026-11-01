import os
import subprocess

import MadGraphControl.MadGraphUtils as MG
import MadGraphControl.MGC as MGC
from MadGraphControl.MadGraphUtils import *
from MadGraphControl.MGC import MGControl

# AthGeneration/23.6.63 gridpack finalization workaround.
if not hasattr(MGControl, "_original_add_runArgs"):
    MGControl._original_add_runArgs = MGControl.add_runArgs

    def _safe_add_runArgs(self, runArgs=None):
        if runArgs is not None:
            return MGControl._original_add_runArgs(self, runArgs)

    MGControl.add_runArgs = _safe_add_runArgs

USE_DELTA = False
FOLDING = "1, 1, 1"
REQUIRED_ACCURACY = 0.1
GRIDPACK_MODE = not is_gen_from_gridpack()

# Optional controlled recompile of the *extracted copy* of an NLO gridpack.
# MadGraphControl otherwise invokes generate_events with --nocompile.
# This has no effect on gridpack creation/integration.
recompile_setting = os.environ.get("GRIDPACK_RECOMPILE", "0")
if recompile_setting not in ("0", "1"):
    raise RuntimeError("GRIDPACK_RECOMPILE must be 0 or 1")
RECOMPILE_GRIDPACK = (recompile_setting == "1") and not GRIDPACK_MODE

# PMG-approved Zee FxFx scale/PDF weight recipe.
# Set in the legacy MadGraphUtils/MGC modules before constructing MGControl.
# AthGeneration/23.6.63 does NOT support MGControl(pdf_setting=...).
# The 1-jet smoke gridpack retains its original process and nominal PDF.
MG.MADGRAPH_PDFSETTING = {
    "central_pdf": 325100,
    "pdf_variations": [325100, 93300],
    "alternative_pdfs": [
        304400, 13000, 25300, 14000, 14100, 14200, 61200, 42560,
        303200, 27400, 331500,
    ],
    "scale_variations": [0.5, 1, 2],
}
MGC.MADGRAPH_PDFSETTING = MG.MADGRAPH_PDFSETTING

evgenConfig.description = "Zee+0,1j NLO FxFx Condor gridpack smoke"
evgenConfig.contact = ["francesco.giuli@cern.ch"]
evgenConfig.keywords += ["Z", "jets"]
evgenConfig.generators += ["aMcAtNlo", "Pythia8"]
evgenConfig.nEventsPerJob = 5000

# The production integration settings must stay identical to the archived
# gridpack. Generation only reads those grids: no new integration or patch.
if GRIDPACK_MODE:
    process = """
import model loop_sm-no_b_mass
define p = u u~ d d~ s s~ c c~ b b~ g
define j = u u~ d d~ s s~ c c~ b b~ g
generate p p > e+ e- [QCD] @0
add process p p > e+ e- j [QCD] @1
output -f
"""
    process_dir = str(new_process(process))

    patch_name = "fxfx_exclusive_kt.patch"
    subprocess.check_call(["get_files", "-data", patch_name])
    patch = os.path.abspath(patch_name)
    command = ["patch", "--batch", "--forward", "-p1", "-d", process_dir, "-i", patch]
    subprocess.check_call(command + ["--dry-run"])
    subprocess.check_call(command)
else:
    process_dir = str(MADGRAPH_GRIDPACK_LOCATION)
    # On this AthGeneration release the gridpack config must be reloaded
    # before modify_run_card and generate from an existing NLO gridpack.
    mgc = MGControl()
    mgc.get_config_cardloc()
    mgc.getConfigFromPath(mgc.config_path)
    mgc.getRunCardDict()
    MG.my_MGC_instance = mgc

nevents = (
    max(20, 2 * int(runArgs.maxEvents))
    if GRIDPACK_MODE else 5 * int(runArgs.maxEvents if runArgs.maxEvents > 0
                                  else evgenConfig.nEventsPerJob)
)

modify_run_card(process_dir=process_dir, runArgs=runArgs, settings={
    "ebeam1": float(runArgs.ecmEnergy) / 2,
    "ebeam2": float(runArgs.ecmEnergy) / 2,
    "nevents": nevents,
    "req_acc": REQUIRED_ACCURACY,
    "maxjetflavor": 5,
    "parton_shower": "PYTHIA8",
    "ickkw": 3,
    "jetradius": 1.0,
    "ptj": 8,
    "etaj": 10,
    "mll": 40,
    "mll_sf": 40,
    "mcatnlo_delta": USE_DELTA,
    "folding": FOLDING,
    # NLO PDF/scale variations require #aMCatNLO reweight metadata
    # in each generated LHE event. This is controlled at event
    # generation, not by changing the completed integration grids.
    # Keep the archived gridpack integration smoke configuration intact.
    "store_rwgt_info": not GRIDPACK_MODE,
})

config_settings = (
    {"run_mode": 1, "cluster_type": "condor", "cluster_nb_retry": 0}
    if GRIDPACK_MODE else {"run_mode": 0, "nb_core": 1}
)
modify_config_card(process_dir=process_dir, settings=config_settings)

generate(process_dir=process_dir, runArgs=runArgs,
         required_accuracy=REQUIRED_ACCURACY, grid_pack=GRIDPACK_MODE,
         gridpack_compile=RECOMPILE_GRIDPACK)

if not GRIDPACK_MODE:
    arrange_output(process_dir=process_dir, runArgs=runArgs,
                   lhe_version=3, saveProcDir=False)
    include("Pythia8_i/Pythia8_A14_NNPDF23LO_EvtGen_Common.py")
    include("Pythia8_i/Pythia8_aMcAtNlo.py")
    PYTHIA8_nJetMax = 1
    PYTHIA8_qCut = 20.0
    include("Pythia8_i/Pythia8_FxFx_A14mod.py")
