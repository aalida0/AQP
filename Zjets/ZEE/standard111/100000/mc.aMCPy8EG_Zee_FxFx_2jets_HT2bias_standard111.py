# Historical Zee standard111 gridpack JO, adapted as a source-patch scaffold.
# Requires the exact missing HT2 Fortran files listed in REQUIRED_FILES.md.
import os
import shutil
import subprocess

import MadGraphControl.MadGraphUtils
from MadGraphControl.MadGraphUtils import *
from MadGraphControl.MGC import MGControl

# AthGeneration/23.6.63 gridpack finalization workaround.
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
evgenConfig.nEventsPerJob = 2000

nevents = int(5 * (runArgs.maxEvents if runArgs.maxEvents > 0
                    else evgenConfig.nEventsPerJob))
beam_energy = float(runArgs.ecmEnergy) / 2.0


def install_file(filename, destination):
    subprocess.check_call(["get_files", "-data", filename])
    if not os.path.isfile(filename):
        raise RuntimeError("Required source file not found: " + filename)
    shutil.copy2(filename, destination)


def install_patch(filename, process_dir):
    subprocess.check_call(["get_files", "-data", filename])
    if not os.path.isfile(filename):
        raise RuntimeError("Required patch not found: " + filename)
    source = os.path.abspath(filename)
    subprocess.check_call(["patch", "--batch", "--forward", "--dry-run",
                           "-p1", "-d", process_dir, "-i", source])
    subprocess.check_call(["patch", "--batch", "--forward",
                           "-p1", "-d", process_dir, "-i", source])


if is_gen_from_gridpack():
    raise RuntimeError("Use the matching grid event-generation JO")

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

MadGraphControl.MadGraphUtils.MADGRAPH_PDFSETTING = {
    "central_pdf": 325100,
    "pdf_variations": [],
    "alternative_pdfs": [],
    "scale_variations": [],
}

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

config_settings = {
    "run_mode": 1,
    "nb_core": 1,
    "cluster_type": "condor",
    "cluster_size": 100,
}

if USE_DELTA:
    pythia8_path = os.getenv("PY8PATH")
    if not pythia8_path:
        raise RuntimeError("PY8PATH is required for MC@NLO-Delta")
    config_settings["pythia8_path"] = pythia8_path

modify_config_card(process_dir=process_dir, settings=config_settings)

generate(required_accuracy=REQUIRED_ACCURACY, process_dir=process_dir,
         runArgs=runArgs, grid_pack=True)

# In gridpack mode, MadGraphControl finalizes/exits before event showering.
