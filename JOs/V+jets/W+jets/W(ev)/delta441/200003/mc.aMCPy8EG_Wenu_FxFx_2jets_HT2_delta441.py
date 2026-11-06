import os
import shutil
import subprocess

import MadGraphControl.MadGraphUtils as MG
from MadGraphControl.MadGraphUtils import *
import MadGraphControl.MGC as MGC
from MadGraphControl.MGC import MGControl

# Required by MadGraphControl in AthGeneration/23.6.63.
if not hasattr(MGControl, "_original_add_runArgs"):
    MGControl._original_add_runArgs = MGControl.add_runArgs

    def _safe_add_runArgs(self, runArgs=None):
        if runArgs is not None:
            return MGControl._original_add_runArgs(self, runArgs)

    MGControl.add_runArgs = _safe_add_runArgs

USE_DELTA = True
FOLDING = "4, 4, 1"
REQUIRED_ACCURACY = 1e-3  # Requested 2-jet integration target; physics validation pending
GRIDPACK_MODE = not is_gen_from_gridpack()

evgenConfig.description = "aMcAtNlo Wenu+0,1,2j HT2 NLO FxFx PR426 delta441"
evgenConfig.contact = ["francesco.giuli@cern.ch"]
evgenConfig.keywords += ["W", "jets"]
evgenConfig.generators += ["aMcAtNlo", "Pythia8"]
evgenConfig.nEventsPerJob = 2000 if GRIDPACK_MODE else 5000

# PMG full PDF/scale weights in event mode; central PDF only for gridpack integration.
MG.MADGRAPH_PDFSETTING = {
    "central_pdf": 325100,
    "pdf_variations": [] if GRIDPACK_MODE else [325100, 93300],
    "alternative_pdfs": [] if GRIDPACK_MODE else [
        304400, 13000, 25300, 14000, 14100, 14200, 61200, 42560,
        303200, 27400, 331500,
    ],
    "scale_variations": [] if GRIDPACK_MODE else [0.5, 1, 2],
}
MGC.MADGRAPH_PDFSETTING = MG.MADGRAPH_PDFSETTING

if GRIDPACK_MODE:
    process = """
    import model loop_sm-no_b_mass
    define p = u u~ d d~ s s~ c c~ b b~ g
    define j = u u~ d d~ s s~ c c~ b b~ g
    generate p p > e+ ve [QCD] @0
    add process p p > e+ ve j [QCD] @1
    add process p p > e+ ve j j [QCD] @2
    output -f
    """
    process_dir = str(new_process(process))
    for source, target in (
        ("dummy_fct.f", "dummy_fct.f"),
        ("montecarlocounter_MINE.f", "montecarlocounter.f"),
    ):
        subprocess.check_call(["get_files", "-data", source])
        shutil.copy2(source, os.path.join(process_dir, "SubProcesses", target))
    patch_name = "fxfx_exclusive_kt.patch"
    subprocess.check_call(["get_files", "-data", patch_name])
    patch = os.path.abspath(patch_name)
    command = ["patch", "--batch", "--forward", "-p1", "-d", process_dir, "-i", patch]
    subprocess.check_call(command + ["--dry-run"])
    subprocess.check_call(command)
else:
    process_dir = str(MADGRAPH_GRIDPACK_LOCATION)
    mgc = MGControl()
    mgc.get_config_cardloc()
    mgc.getConfigFromPath(mgc.config_path)
    mgc.getRunCardDict()
    MG.my_MGC_instance = mgc

beam_energy = float(runArgs.ecmEnergy) / 2.0
nevents = (5 if GRIDPACK_MODE else 10) * (
    runArgs.maxEvents if runArgs.maxEvents > 0 else evgenConfig.nEventsPerJob
)
modify_run_card(process_dir=process_dir, runArgs=runArgs, settings={
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
    "mcatnlo_delta": USE_DELTA,
    "folding": FOLDING,
    "store_rwgt_info": True,  # Must also be True when building the gridpack
})

config_settings = (
    {"run_mode": 1, "nb_core": 1, "cluster_type": "condor",
     "cluster_size": 100, "cluster_nb_retry": 0}
    if GRIDPACK_MODE else {"run_mode": 0, "nb_core": 1}
)
if USE_DELTA:
    pythia8_path = os.getenv("PY8PATH")
    if not pythia8_path:
        raise RuntimeError("PY8PATH is required for MC@NLO-Delta")
    pythia8_path = os.path.realpath(pythia8_path)
    if not os.path.isfile(os.path.join(pythia8_path, "lib", "libpythia8.a")):
        raise RuntimeError("MC@NLO-Delta Pythia8 static library unavailable")
    config_settings["pythia8_path"] = pythia8_path
modify_config_card(process_dir=process_dir, settings=config_settings)

generate(required_accuracy=REQUIRED_ACCURACY, process_dir=process_dir,
         runArgs=runArgs, grid_pack=GRIDPACK_MODE, gridpack_compile=False)

if not GRIDPACK_MODE:
    arrange_output(process_dir=process_dir, runArgs=runArgs,
                   lhe_version=3, saveProcDir=False)
    include("Pythia8_i/Pythia8_A14_NNPDF23LO_EvtGen_Common.py")
    include("Pythia8_i/Pythia8_aMcAtNlo.py")
    PYTHIA8_nJetMax = 2
    PYTHIA8_qCut = 20.0
    include("Pythia8_i/Pythia8_FxFx_A14mod.py")
