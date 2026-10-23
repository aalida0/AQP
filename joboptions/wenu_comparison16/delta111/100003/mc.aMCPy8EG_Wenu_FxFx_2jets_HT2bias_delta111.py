"""ATLAS Wenu+0,1,2j FxFx NLO delta111 from a pre-existing gridpack.

This is a sixteen-core comparison JO derived from the validated Wenu event-generation JO
at generation/100000. It must NEVER create a new MG process or reintegrate
its MINT0/MINT1 grids. The input tarball is unpacked as ./madevent/ in the
worker-local scratch directory before Gen_tf starts.
"""

import os
import MadGraphControl.MadGraphUtils
from MadGraphControl.MadGraphUtils import *
from MadGraphControl.MGC import MGControl
import re

# --------------------------------------------------------------------
# Event-generation configuration
# --------------------------------------------------------------------
GRIDPACK_ECM_ENERGY = 13000.0
USE_DELTA = True
FOLDING = "1, 1, 1"
REQUIRED_ACCURACY = 1.0e-4
LHE_OVERSAMPLING_FACTOR = 5
DELTA441_NB_CORES = 16

# --------------------------------------------------------------------
# EVGEN metadata
# --------------------------------------------------------------------
evgenConfig.description = (
    "aMcAtNlo Wenu+0,1,2j NLO FxFx HT2-biased Py8, "
    "MC@NLO-Delta=True matching with folding 111"
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
        "AQP_WENU_ABORT_NO_EXISTING_GRIDPACK: "
        "extract the Delta441 archive as ./madevent/ before running Gen_tf"
    )
if abs(float(runArgs.ecmEnergy) - GRIDPACK_ECM_ENERGY) > 1.0e-6:
    raise RuntimeError("AQP_WENU_ABORT_WRONG_ECM: use --ecmEnergy=13000")

# Do not rewrite an integration gridpack into a different physics setup.
# MG RunCardNLO reads keys case-insensitively; the final entry wins.
_original_card = os.path.join(str(MADGRAPH_GRIDPACK_LOCATION), "Cards", "run_card.dat")
_original = {}
with open(_original_card, encoding="utf-8") as _cardfile:
    for _line in _cardfile:
        _line = _line.split("#", 1)[0].split("!", 1)[0]
        if "=" not in _line:
            continue
        _value, _key = _line.rsplit("=", 1)
        _original[_key.strip().lower()] = _value.strip().lower()
def _bool(x):
    return x in ("true", ".true.", "t", "1")
_want_fold = tuple(int(x) for x in FOLDING.split(","))
try:
    _actual_fold = tuple(int(x) for x in re.split(r"[,\\s]+", _original["folding"]) if x)
except (KeyError, ValueError):
    raise RuntimeError("AQP_WENU_ABORT_BAD_OR_MISSING_ARCHIVE_FOLDING")
if _actual_fold != _want_fold or _bool(_original.get("mcatnlo_delta", "false")) != USE_DELTA:
    raise RuntimeError("AQP_WENU_ABORT_ARCHIVE_PHYSICS_MISMATCH: folding=%s delta=%s" %
                       (_actual_fold, _original.get("mcatnlo_delta")))
if _original.get("ickkw") != "3":
    raise RuntimeError("AQP_WENU_ABORT_ARCHIVE_NOT_FXFX")
if _original.get("event_norm") != "bias":
    raise RuntimeError("AQP_WENU_ABORT_ARCHIVE_WRONG_EVENT_NORM")
try:
    if (float(_original["ebeam1"].replace("d", "e")) != 6500.0 or
            float(_original["ebeam2"].replace("d", "e")) != 6500.0):
        raise RuntimeError("AQP_WENU_ABORT_ARCHIVE_WRONG_BEAM")
except (KeyError, ValueError):
    raise RuntimeError("AQP_WENU_ABORT_ARCHIVE_INVALID_BEAM")
if _original.get("lhaid") != "325100":
    raise RuntimeError("AQP_WENU_ABORT_ARCHIVE_PDF_MISMATCH")
print("AQP_WENU_ARCHIVE_PHYSICS_VERIFIED")
print("AQP_WENU_CONFIG=delta111")

process_dir = str(MADGRAPH_GRIDPACK_LOCATION)
if not os.path.isfile(os.path.join(process_dir, "SubProcesses", "job_status.pkl")):
    raise RuntimeError("AQP_WENU_ABORT_MISSING_RECOVERED_CHECKPOINT")

requested_events = (
    int(runArgs.maxEvents)
    if runArgs.maxEvents > 0
    else int(evgenConfig.nEventsPerJob)
)
nevents = LHE_OVERSAMPLING_FACTOR * requested_events
beam_energy = GRIDPACK_ECM_ENERGY / 2.0

print("AQP_WENU_EXISTING_GRIDPACK_ONLY")
print("AQP_WENU_LHE_EVENTS_REQUESTED=%d" % nevents)

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

print("AQP_WENU_MGCONTROL_CARDS_LOADED")

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
# Execute local multicore workers inside ONE HTCondor allocation.
# MadGraph run_mode=2 is local multicore; mode=1 is cluster submission.
# A separate outer HTCondor batch job requests exactly 8 CPUs.
# --------------------------------------------------------------------
pythia8_path = os.getenv("PY8PATH")
if not pythia8_path:
    raise RuntimeError("AQP_WENU_ABORT_PY8PATH_NOT_SET")

modify_config_card(
    process_dir=process_dir,
    settings={
        "run_mode": 2,
        "nb_core": DELTA441_NB_CORES,
        "pythia8_path": pythia8_path,
    },
)

# Verify the actual MadGraph config card before expensive event generation.
# The last assignment wins in MG configurations, so parse all assignments.
_config_file = os.path.join(process_dir, "Cards", "amcatnlo_configuration.txt")
_config_values = {}
with open(_config_file, encoding="utf-8") as _cfg:
    for _line in _cfg:
        _body = _line.split("#", 1)[0].strip()
        if "=" not in _body:
            continue
        _key, _value = [x.strip() for x in _body.split("=", 1)]
        if _key in ("run_mode", "nb_core"):
            _config_values[_key] = _value
try:
    _mode = int(_config_values["run_mode"])
    _cores = int(_config_values["nb_core"])
except (KeyError, ValueError) as _err:
    raise RuntimeError("AQP_WENU_ABORT_UNREADABLE_PARALLEL_CONFIG") from _err
if (_mode, _cores) != (2, DELTA441_NB_CORES):
    raise RuntimeError(
        "AQP_WENU_ABORT_WRONG_PARALLEL_CONFIG: "
        "run_mode=%s nb_core=%s" % (_mode, _cores)
    )
print("AQP_WENU_PARALLEL_CONFIG_VERIFIED_MODE=2_NB_CORE=%d" % _cores)
print("AQP_WENU_PARALLEL_MODE=2_NB_CORE=%d" % DELTA441_NB_CORES)

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
# Pythia8 depends on transform mode.
# TXT-only transforms need one NONPHYSICAL Pythia8 dummy event; FxFx
# matching must not be attached to that minimum-bias event. The real
# LHE events are already generated by MadGraphControl above.
# EVNT transforms instead shower the real LHE with full FxFx matching.
# --------------------------------------------------------------------
include("Pythia8_i/Pythia8_A14_NNPDF23LO_EvtGen_Common.py")
if getattr(runArgs, "outputTXTFile", None):
    # The GENtoTXT skeleton supplies its own dummy process configuration.
    # Crucially omit both the aMC@NLO LHE interface and JetMatchingMadgraph
    # from the dummy; neither affects the saved LHE/TXT physical events.
    print("AQP_WENU_TXT_MODE_DUMMY_WITHOUT_LHE_OR_FXFX_HOOK")
    print("AQP_WENU_TXT_MODE_LHE_PHYSICS_PRESERVED")
else:
    include("Pythia8_i/Pythia8_aMcAtNlo.py")
    PYTHIA8_nJetMax = 2
    PYTHIA8_qCut = 20.0
    include("Pythia8_i/Pythia8_FxFx_A14mod.py")
    genSeq.Pythia8.Commands += ["SoftQCD:inelastic = off"]
    print("AQP_WENU_EVNT_MODE_REAL_FXFX_SHOWER_CONFIGURED")
