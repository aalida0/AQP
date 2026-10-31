"""Read ATLAS EVNT.pool.root into Rivet_i without regenerating events.

Required environment: AQP_PR426_EVNT, AQP_PR426_PLUGIN_DIR, AQP_PR426_YODA.
Optional: AQP_PR426_MAX_EVENTS (200 by default, -1 for all).
"""
import os
from AthenaCommon.AlgSequence import AlgSequence
from AthenaCommon.AppMgr import ServiceMgr as svcMgr
import AthenaPoolCnvSvc.ReadAthenaPool

input_file = os.environ["AQP_PR426_EVNT"]
if not os.path.isfile(input_file):
    raise RuntimeError("Missing EVNT: " + input_file)
svcMgr.EventSelector.InputCollections = [input_file]
theApp.EvtMax = int(os.environ.get("AQP_PR426_MAX_EVENTS", "200"))

job = AlgSequence()
from xAODEventInfoCnv.xAODEventInfoCnvConf import xAODMaker__EventInfoCnvAlg
job += xAODMaker__EventInfoCnvAlg()

from Rivet_i.Rivet_iConf import Rivet_i
rivet = Rivet_i("AQP_PR426_Rivet")
rivet.AnalysisPath = os.environ["AQP_PR426_PLUGIN_DIR"]
rivet.Analyses = ["AQP_PR426_JETS"]
rivet.McEventKey = "GEN_EVENT"
rivet.SkipWeights = True
rivet.NominalWeightName = "Default"
# Deliberately arbitrary; this validation compares only unit-area shapes.
rivet.CrossSection = 1.0
rivet.HistoFile = os.environ["AQP_PR426_YODA"]
job += rivet
print("AQP_PR426_RIVET_INPUT=%s MAX_EVENTS=%d" % (input_file, theApp.EvtMax))
