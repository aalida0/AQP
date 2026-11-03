import os
import shutil
import subprocess

import MadGraphControl.MadGraphUtils as MG
from MadGraphControl.MadGraphUtils import *
from MadGraphControl.MGC import MGControl
import MadGraphControl.MGC as MGC

if not hasattr(MGControl, "_original_add_runArgs"):
    MGControl._original_add_runArgs = MGControl.add_runArgs

    def _safe_add_runArgs(self, runArgs=None):
        if runArgs is not None:
            return MGControl._original_add_runArgs(self, runArgs)

    MGControl.add_runArgs = _safe_add_runArgs

# Integration test only; req_acc=0.5 is not suitable for physics comparisons.
USE_DELTA = True
FOLDING = "1, 1, 1"
REQUIRED_ACCURACY = 0.5
GRIDPACK_MODE = not is_gen_from_gridpack()

recompile_setting = os.environ.get("GRIDPACK_RECOMPILE", "0")
if recompile_setting not in ("0", "1"):
    raise RuntimeError("GRIDPACK_RECOMPILE must be 0 or 1")
RECOMPILE_GRIDPACK = (recompile_setting == "1") and not GRIDPACK_MODE

evgenConfig.description = "aMcAtNlo Zee+0,1j NLO FxFx HT2 PR426 delta111 rwgt"
evgenConfig.contact = ["lenart.jerala@cern.ch"]
evgenConfig.keywords += ["Z", "jets"]
evgenConfig.generators += ["aMcAtNlo", "Pythia8"]
evgenConfig.nEventsPerJob = 2000 if GRIDPACK_MODE else 5000

MG.MADGRAPH_PDFSETTING = {
    "central_pdf": 325100,
    "pdf_variations": [] if GRIDPACK_MODE else [325100],
    "alternative_pdfs": [] if GRIDPACK_MODE else [304400],
    "scale_variations": [] if GRIDPACK_MODE else [0.5, 1.0, 2.0],
}
MGC.MADGRAPH_PDFSETTING = MG.MADGRAPH_PDFSETTING

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
    for source, target in (
        ("dummy_fct.f", "dummy_fct.f"),
        ("montecarlocounter_MINE.f", "montecarlocounter.f"),
    ):
        subprocess.check_call(["get_files", "-data", source])
        if not os.path.isfile(source):
            raise RuntimeError("Missing authoritative main JO source: " + source)
        shutil.copy2(source, os.path.join(process_dir, "SubProcesses", target))

    with open(os.path.join(process_dir, "SubProcesses", "dummy_fct.f")) as handle:
        if "bias_wgt=H_T**2" not in handle.read():
            raise RuntimeError("Zee HT2 bias function is missing")
    with open(os.path.join(process_dir, "SubProcesses", "montecarlocounter.f")) as handle:
        src = handle.read()
        if ("eps = 100.d0 * epsilon(1.d0)" not in src
                or "if(probne.gt.1.d0+eps)then" not in src
                or "if(probne.gt.1.d0) probne=1.d0" not in src):
            raise RuntimeError("MC@NLO-Delta Sudakov tolerance correction missing")
    print("ZEE_HT2_BIAS_AND_DELTA_TOLERANCE_VERIFIED")

    patch_name = "fxfx_exclusive_kt.patch"
    subprocess.check_call(["get_files", "-data", patch_name])
    patch = os.path.abspath(patch_name)
    command = ["patch", "--batch", "--forward", "-p1", "-d", process_dir, "-i", patch]
    subprocess.check_call(command + ["--dry-run"])
    subprocess.check_call(command)
    with open(os.path.join(process_dir, "SubProcesses", "cuts.f")) as handle:
        if "amcatnlo_fastjetdmergemax(nQCD-2).lt.ptj**2" not in handle.read():
            raise RuntimeError("PR426 FxFx exclusive-kT cut not applied")
    print("FXFX_PR426_EXCLUSIVE_KT_VERIFIED")
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
    "mll": 40,
    "mll_sf": 40,
    "mcatnlo_delta": USE_DELTA,
    "folding": FOLDING,
    "store_rwgt_info": True,  # Required already when packing the gridpack.
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
         runArgs=runArgs, grid_pack=GRIDPACK_MODE,
         gridpack_compile=RECOMPILE_GRIDPACK)

if not GRIDPACK_MODE:
    arrange_output(process_dir=process_dir, runArgs=runArgs,
                   lhe_version=3, saveProcDir=False)
    include("Pythia8_i/Pythia8_A14_NNPDF23LO_EvtGen_Common.py")
    include("Pythia8_i/Pythia8_aMcAtNlo.py")
    PYTHIA8_nJetMax = 1
    PYTHIA8_qCut = 20.0
    include("Pythia8_i/Pythia8_FxFx_A14mod.py")
