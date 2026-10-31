"""AQP Wenu Standard111 direct-LHE FxFx PR426 A/B with MG internal Condor.

Fresh MG5_aMC process and integration for BOTH A and B.
Uses original Wenu custom dummy_fct.f and montecarlocounter_MINE.f unchanged.
This JO does NOT create or reuse a gridpack and does NOT test the Condor
backend patch. Uses original MG internal Condor backend (run_mode=1), called
from a persistent terminal on an approved interactive/submission host.
"""

import hashlib
import importlib.util
import os
from pathlib import Path
import shutil

import MadGraphControl.MadGraphUtils
from MadGraphControl.MadGraphUtils import *
from MadGraphControl.MGC import MGControl

FXFX_APPLY_PR426 = False
FXFX_CASE = "before"
USE_DELTA = False
FOLDING = "1, 1, 1"
REQUIRED_ACCURACY = 0.1
LHE_OVERSAMPLING_FACTOR = 5

evgenConfig.description = (
    "Wenu+0,1,2 jets NLO FxFx Standard111, legacy bias settings; "
    "AQP PR426 " + FXFX_CASE + " technical test"
)
evgenConfig.contact = ["amine.alida@cern.ch"]
evgenConfig.keywords += ["W", "jets"]
evgenConfig.generators += ["aMcAtNlo", "Pythia8"]
evgenConfig.nEventsPerJob = 2000

if is_gen_from_gridpack():
    raise RuntimeError("AQP_FXFX_AB_REJECT_GRIDPACK_REUSE")
if abs(float(runArgs.ecmEnergy) - 13000.) > 1.0e-6:
    raise RuntimeError("AQP_FXFX_AB_WRONG_ENERGY")

if int(runArgs.maxEvents) <= 0:
    raise RuntimeError("AQP_FXFX_AB_EXPLICIT_MAXEVENTS_REQUIRED")
nevents = LHE_OVERSAMPLING_FACTOR * int(runArgs.maxEvents)
if nevents not in (200, 50000):
    raise RuntimeError("AQP_FXFX_AB_UNSUPPORTED_LHE_COUNT_%d" % nevents)

if not getattr(runArgs, "outputTXTFile", None):
    raise RuntimeError("AQP_FXFX_AB_REQUIRE_TXT_ONLY_NO_SHOWER_IN_GENERATION")

# MG internal Condor child processes must see the generated process tree
# through a shared filesystem. Never integrate in /data (Ceph).
if os.path.realpath(os.getcwd()).startswith("/data/"):
    raise RuntimeError("AQP_FXFX_AB_REFUSE_CEPH_WORKDIR")

process = """
import model loop_sm-no_b_mass
define p = u u~ d d~ s s~ c c~ b b~ g
define j = u u~ d d~ s s~ c c~ b b~ g
define e = e+ e-
define nu = ve ve~
generate p p > e nu [QCD] @0
add process p p > e nu j [QCD] @1
add process p p > e nu j j [QCD] @2
output -f
"""

process_dir = str(new_process(process))
source_dir = Path(os.environ.get("AQP_FXFX_AB_INPUT_DIR", ""))
if (not os.environ.get("AQP_FXFX_AB_INPUT_DIR")
        or not source_dir.is_dir()):
    raise RuntimeError("AQP_FXFX_AB_INPUT_DIR_MISSING")
for src_name, dst_name in (
    ("dummy_fct.f", "dummy_fct.f"),
    ("montecarlocounter_MINE.f", "montecarlocounter.f"),
):
    source = source_dir / src_name
    if not source.is_file() or source.stat().st_size <= 0:
        raise RuntimeError("AQP_FXFX_AB_MISSING_HT2_SOURCE_%s" % src_name)
    shutil.copy2(str(source), os.path.join(process_dir, "SubProcesses", dst_name))
    print("AQP_FXFX_AB_CUSTOM_SOURCE=%s SHA256=%s" %
          (src_name, hashlib.sha256(source.read_bytes()).hexdigest()))

cuts_path = Path(process_dir) / "SubProcesses" / "cuts.f"
if not cuts_path.is_file():
    raise RuntimeError("AQP_FXFX_AB_MISSING_GENERATED_CUTS")
before = cuts_path.read_text(encoding="utf-8")

script = source_dir / "aqp_prepare_fxfx_exclusive_kt_patch.py"
if not script.is_file():
    raise RuntimeError("AQP_FXFX_AB_MISSING_PR426_PATCHER")
spec = importlib.util.spec_from_file_location("aqp_fxfx_pr426", str(script))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Both variants must start with EXACTLY the same old FxFx implementation;
# the patcher refuses unknown ATLAS versions or partially patched files.
after = mod.patched_text(before)
if FXFX_APPLY_PR426:
    cuts_path.write_text(after, encoding="utf-8")
    selected = after
else:
    selected = before

actual = cuts_path.read_text(encoding="utf-8")
if actual != selected:
    raise RuntimeError("AQP_FXFX_AB_CUTS_READBACK_FAILED")
if ("amcatnlo_fastjetdmergemax(nQCD-2).lt.ptj**2" in actual) != FXFX_APPLY_PR426:
    raise RuntimeError("AQP_FXFX_AB_WRONG_CUTS_VARIANT")
print("AQP_FXFX_AB_CASE=%s" % FXFX_CASE)
print("AQP_FXFX_AB_BASELINE_CUTS_SHA256=%s" %
      hashlib.sha256(before.encode()).hexdigest())
print("AQP_FXFX_AB_ACTIVE_CUTS_SHA256=%s" %
      hashlib.sha256(actual.encode()).hexdigest())
print("AQP_FXFX_AB_PR426_ENABLED=%s" % FXFX_APPLY_PR426)
print("AQP_FXFX_AB_CUSTOM_SOURCES_IDENTICAL_TO_LEGACY")

# Disable the ATLAS automatic PDF/scale variation machinery.
# With a non-None dictionary, arrange_output() demands the nominal
# systematic weight MUR1.0_MUF1.0_PDF325100 even when no variation lists
# are requested. The 200-event baseline completed MG generation but failed
# at precisely this post-generation check. Keep the central PDF via lhaid
# below; retain only the native nominal LHE event weight.
MadGraphControl.MadGraphUtils.MADGRAPH_PDFSETTING = None
if MadGraphControl.MadGraphUtils.my_MGC_instance is not None:
    MadGraphControl.MadGraphUtils.my_MGC_instance.pdf_setting = None
print("AQP_FXFX_AB_SYSTEMATICS_DISABLED_PDF325100_NOMINAL_ONLY")

modify_run_card(
    process_dir=process_dir,
    runArgs=runArgs,
    settings={
        "ebeam1": 6500.0,
        "ebeam2": 6500.0,
        "event_norm": "bias",
        "lhaid": 325100,
        "systematics_program": "none",
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

# In MG5_aMC 3.5.11, nb_core also controls local parallel
# compilation of P* directories, independently of run_mode=1.
# The caller must reserve/own the matching CPUs on a compute node.
compile_cores = int(os.environ.get("AQP_FXFX_AB_COMPILE_CORES", "4"))
if compile_cores not in (4, 16, 24, 32):
    raise RuntimeError("AQP_FXFX_AB_COMPILE_CORES_MUST_BE_4_16_24_OR_32")
# Compile workers run locally even with run_mode=1. Respect the
# Analysis Facility login limit of four cores; a 24-core value is only
# permitted from an appropriately allocated, scheduler-capable host.
if os.uname().nodename.split(".")[0].startswith(("login", "head")) and compile_cores > 4:
    raise RuntimeError("AQP_FXFX_AB_LOGIN_COMPILE_CORES_EXCEED_4")
print("AQP_FXFX_AB_COMPILE_CORES=%d" % compile_cores)

pythia8_path = os.environ.get("PY8PATH")
if not pythia8_path:
    raise RuntimeError("AQP_FXFX_AB_PY8PATH_MISSING")
modify_config_card(
    process_dir=process_dir,
    settings={
        "run_mode": 1,
        "nb_core": compile_cores,
        "cluster_type": "condor",
        "cluster_size": 100,
        "pythia8_path": pythia8_path,
    },
)
print("AQP_FXFX_AB_INTERNAL_CONDOR_MODE=1_CLUSTER_SIZE=100")
print("AQP_FXFX_AB_CONDOR_BACKEND_UNPATCHED")
print("AQP_FXFX_AB_REQUESTED_LHE=%d_REQ_ACC=%g" %
      (nevents, REQUIRED_ACCURACY))

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

# In Gen_tf TXT mode this creates only the skeleton's nonphysical dummy
# event, NOT a real FxFx shower. Physical showering is an independent step.
include("Pythia8_i/Pythia8_A14_NNPDF23LO_EvtGen_Common.py")
print("AQP_FXFX_AB_TXT_ONLY_SHOWER_DEFERRED")
