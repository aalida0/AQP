import os
import subprocess

import MadGraphControl.MadGraphUtils as MG
from MadGraphControl.MadGraphUtils import *
from MadGraphControl.MGC import MGControl

# AthGeneration/23.6.63 gridpack finalization.
if not hasattr(MGControl, "_original_add_runArgs"):
    MGControl._original_add_runArgs = MGControl.add_runArgs

    def _safe_add_runArgs(self, runArgs=None):
        if runArgs is not None:
            return MGControl._original_add_runArgs(self, runArgs)

    MGControl.add_runArgs = _safe_add_runArgs

USE_DELTA = False
FOLDING = "1, 1, 1"
REQUIRED_ACCURACY = 0.1

evgenConfig.description = "Zee+0,1j NLO FxFx Condor gridpack smoke"
evgenConfig.contact = ["francesco.giuli@cern.ch"]
evgenConfig.keywords += ["Z", "jets"]
evgenConfig.generators += ["aMcAtNlo", "Pythia8"]
evgenConfig.nEventsPerJob = 5000

if is_gen_from_gridpack():
    raise RuntimeError("Gridpack-only integration smoke test")

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

MG.MADGRAPH_PDFSETTING = {
    "central_pdf": 325100,
    "pdf_variations": [],
    "alternative_pdfs": [],
    "scale_variations": [],
}
modify_run_card(process_dir=process_dir, runArgs=runArgs, settings={
    "ebeam1": float(runArgs.ecmEnergy) / 2,
    "ebeam2": float(runArgs.ecmEnergy) / 2,
    "nevents": max(20, 2 * int(runArgs.maxEvents)),
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
})
modify_config_card(process_dir=process_dir, settings={
    "run_mode": 1,
    "cluster_type": "condor",
    "cluster_nb_retry": 0,
})
generate(process_dir=process_dir, runArgs=runArgs,
         required_accuracy=REQUIRED_ACCURACY, grid_pack=True)
