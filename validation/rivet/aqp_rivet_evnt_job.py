# Athena jobOptions: offline Rivet on an existing ATLAS EVNT POOL ROOT file.
# Usage: AQP_RIVET_INPUT=/abs/file.root AQP_RIVET_OUTPUT=/abs/out.yoda.gz
#        AQP_RIVET_ANALYSES=MC_ZJETS,MC_ZINC athena.py aqp_rivet_evnt_job.py
# Run in a fully configured Athena/AthGeneration environment.

import os

inp = os.environ.get("AQP_RIVET_INPUT", "")
out = os.environ.get("AQP_RIVET_OUTPUT", "AQP_Rivet.yoda.gz")
analyses = [x.strip() for x in os.environ.get("AQP_RIVET_ANALYSES", "MC_ZJETS,MC_ZINC").split(",") if x.strip()]
if not inp or not os.path.isfile(inp):
    raise RuntimeError("AQP_RIVET_INPUT must point to an existing EVNT POOL ROOT file")
if not analyses:
    raise RuntimeError("AQP_RIVET_ANALYSES is empty")

theApp.EvtMax = -1  # All events in each downloaded EVNT file; no 2M cap.
import AthenaPoolCnvSvc.ReadAthenaPool
from AthenaCommon.AppMgr import ServiceMgr as svcMgr
svcMgr.EventSelector.InputCollections = [inp]

from AthenaCommon.AlgSequence import AlgSequence
job = AlgSequence()

# Follow the ATLAS offline EVNT->Rivet_i example.
from xAODEventInfoCnv.xAODEventInfoCnvConf import xAODMaker__EventInfoCnvAlg
job += xAODMaker__EventInfoCnvAlg()

from Rivet_i.Rivet_iConf import Rivet_i
rivet = Rivet_i("AQPRivet")
rivet.McEventKey = "GEN_EVENT"
rivet.Analyses = analyses
rivet.RunName = ""
rivet.HistoFile = out
rivet.AnalysisPath = os.getcwd()
rivet.SkipWeights = True  # Nominal weights only, for first physics-shape comparison.
rivet.CrossSection = 1.0  # SHAPE VALIDATION ONLY; NOT a physical cross section.
job += rivet
