import os
import shutil
import subprocess

import MadGraphControl.MadGraphUtils
from MadGraphControl.MadGraphUtils import *
from MadGraphControl.MGC import MGControl

# AthGeneration 23.6.63 gridpack-finalization workaround.
if not hasattr(MGControl, "_original_add_runArgs"):
    MGControl._original_add_runArgs = MGControl.add_runArgs

    def _safe_add_runArgs(self, runArgs=None):
        if runArgs is None:
            return
        return MGControl._original_add_runArgs(self, runArgs)

    MGControl.add_runArgs = _safe_add_runArgs


USE_DELTA = False
FOLDING = "1, 1, 1"
REQUIRED_ACCURACY = 1e-4
GRIDPACK_MODE = not is_gen_from_gridpack()

evgenConfig.description = "aMcAtNlo Zee+0,1,2j NLO FxFx HT2-biased Py8"
evgenConfig.contact = ["lenart.jerala@cern.ch"]
evgenConfig.keywords += ["Z", "jets"]
evgenConfig.generators += ["aMcAtNlo", "Pythia8"]
evgenConfig.nEventsPerJob = 2000 if GRIDPACK_MODE else 5000

beam_energy = float(runArgs.ecmEnergy) / 2.0
nevents = 5 * (runArgs.maxEvents if runArgs.maxEvents > 0
               else evgenConfig.nEventsPerJob)


# Apply central PDF only to gridpack integration; reweight on Grid jobs.
MadGraphControl.MadGraphUtils.MADGRAPH_PDFSETTING = {
    "central_pdf": 325100,
    "pdf_variations": [] if GRIDPACK_MODE else [325100],
    "alternative_pdfs": [] if GRIDPACK_MODE else [304400],
    "scale_variations": [] if GRIDPACK_MODE else [0.5, 1.0, 2.0],
}

def install_file(filename, destination):
    subprocess.check_call(["get_files", "-data", filename])
    if not os.path.isfile(filename):
        raise RuntimeError("Missing required source: " + filename)
    shutil.copy2(filename, destination)


def install_patch(filename, process_dir):
    subprocess.check_call(["get_files", "-data", filename])
    if not os.path.isfile(filename):
        raise RuntimeError("Missing required patch: " + filename)
    source = os.path.abspath(filename)
    subprocess.check_call(["patch", "--batch", "--forward", "--dry-run",
                           "-p1", "-d", process_dir, "-i", source])
    subprocess.check_call(["patch", "--batch", "--forward",
                           "-p1", "-d", process_dir, "-i", source])


if GRIDPACK_MODE:
    process = """
    import model loop_sm-no_b_mass
    define p = u u~ d d~ s s~ c c~ b b~ g
    define j = u u~ d d~ s s~ c c~ b b~ g
    generate p p > e+ e- [QCD] @0
    add process p p > e+ e- j [QCD] @1
    add process p p > e+ e- j j [QCD] @2
    output -f
    """
    process_dir = str(new_process(process))
    install_file("dummy_fct.f",
                 os.path.join(process_dir, "SubProcesses", "dummy_fct.f"))
    install_file("montecarlocounter_MINE.f",
                 os.path.join(process_dir, "SubProcesses", "montecarlocounter.f"))
    install_patch("fxfx_exclusive_kt.patch", process_dir)
else:
    process_dir = str(MADGRAPH_GRIDPACK_LOCATION)
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
        "nevents": int(nevents),
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

config_settings = (
    {"run_mode": 1, "nb_core": 1, "cluster_type": "condor",
     "cluster_size": 100, "cluster_nb_retry": 0}
    if GRIDPACK_MODE else {"run_mode": 0, "nb_core": 1}
)
if USE_DELTA:
    pythia8_path = os.getenv("PY8PATH")
    if not pythia8_path:
        raise RuntimeError("PY8PATH is required for MC@NLO-Delta")
    config_settings["pythia8_path"] = pythia8_path

modify_config_card(process_dir=process_dir, settings=config_settings)

generate(required_accuracy=REQUIRED_ACCURACY, process_dir=process_dir,
         runArgs=runArgs, grid_pack=GRIDPACK_MODE)

if not GRIDPACK_MODE:
    arrange_output(process_dir=process_dir, runArgs=runArgs,
                   lhe_version=3, saveProcDir=False)
    include("Pythia8_i/Pythia8_A14_NNPDF23LO_EvtGen_Common.py")
    include("Pythia8_i/Pythia8_aMcAtNlo.py")
    PYTHIA8_nJetMax = 2
    PYTHIA8_qCut = 20.0
    include("Pythia8_i/Pythia8_FxFx_A14mod.py")
