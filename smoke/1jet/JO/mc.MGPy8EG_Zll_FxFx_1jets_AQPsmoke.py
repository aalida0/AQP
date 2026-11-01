import MadGraphControl.MadGraphUtils
from MadGraphControl.MadGraphUtils import *

# Based on mc.MGPy8EG_Zll_FxFx_1jets_valid.py.
# Isolated HTCondor backend smoke test ONLY; not a production JobOption.
evgenConfig.description = 'aMcAtNlo Zll+1Np FxFx (AQP Condor smoke)'
evgenConfig.contact = ["francesco.giuli@cern.ch","federico.sforza@cern.ch","hannes.mildner@cern.ch"]
evgenConfig.keywords += ['Z','jets']

evgenConfig.nEventsPerJob = 5000
nevents = runArgs.maxEvents*2.0 if runArgs.maxEvents > 0 else 2.0*evgenConfig.nEventsPerJob

maxjetflavor = 5
parton_shower = 'PYTHIA8'
nJetMax = 1
qCut = 20.
mllcut = 40
gridpack_mode = False

if not is_gen_from_gridpack():
    process = """
    import model loop_sm-no_b_mass
    define p = p b b~
    define j = p
    define l+ = mu+ e+
    define l- = mu- e-
    generate p p > l+ l- [QCD] @0
    add process p p > l+ l- j [QCD] @1
    output -f"""
    process_dir = str(new_process(process))
else:
    process_dir = str(MADGRAPH_GRIDPACK_LOCATION)

MadGraphControl.MadGraphUtils.MADGRAPH_PDFSETTING = {
    'central_pdf': 325100,
    'pdf_variations': [325100],
    'alternative_pdfs': [304400],
    'scale_variations': [0.5, 1, 2],
}

settings = {
    'maxjetflavor': int(maxjetflavor),
    'parton_shower': parton_shower,
    'nevents': int(nevents),
    'req_acc': 0.10,  # smoke test: deliberately loose integration accuracy
    'ickkw': 3,
    'jetradius': 1.0,
    'ptj': 8,
    'etaj': 10,
    'mll_sf': mllcut,
    'mll': mllcut,
}
modify_run_card(process_dir=process_dir, runArgs=runArgs, settings=settings)

# Ensure the generated process uses Condor and does not auto-resubmit failures.
modify_config_card(process_dir=process_dir, settings={
    'run_mode': 1,
    'cluster_type': 'condor',
    'cluster_queue': 'None',
    'cluster_nb_retry': 0,
    'cluster_retry_wait': 120,
})

generate(process_dir=process_dir, runArgs=runArgs, grid_pack=gridpack_mode)
arrange_output(process_dir=process_dir, runArgs=runArgs, lhe_version=3,
               saveProcDir=True)

include("Pythia8_i/Pythia8_A14_NNPDF23LO_EvtGen_Common.py")
include("Pythia8_i/Pythia8_aMcAtNlo.py")

PYTHIA8_nJetMax = nJetMax
PYTHIA8_qCut = qCut
include("Pythia8_i/Pythia8_FxFx_A14mod.py")
