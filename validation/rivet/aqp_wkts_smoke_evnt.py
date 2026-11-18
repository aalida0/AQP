# Athena JobOptions: isolated W+jets splitting-scale probe on ONE EVNT file.
# This does not edit or overwrite the existing AQP Rivet campaign outputs.
import os

evnt_input = os.environ["AQP_RIVET_INPUT"]
yoda_output = os.environ["AQP_RIVET_OUTPUT"]
plugin_dir = os.environ["AQP_RIVET_PLUGIN_DIR"]

if not os.path.isfile(evnt_input):
    raise RuntimeError("EVNT file missing: " + evnt_input)
if not os.path.isdir(plugin_dir):
    raise RuntimeError("Compiled Rivet plugin directory missing: " + plugin_dir)
if os.path.exists(yoda_output):
    raise RuntimeError("Refusing to overwrite a smoke-test result: " + yoda_output)

theApp.EvtMax = -1
import AthenaPoolCnvSvc.ReadAthenaPool
from AthenaCommon.AppMgr import ServiceMgr as svcMgr
svcMgr.EventSelector.InputCollections = [evnt_input]
from AthenaCommon.AlgSequence import AlgSequence
job = AlgSequence()
from xAODEventInfoCnv.xAODEventInfoCnvConf import xAODMaker__EventInfoCnvAlg
job += xAODMaker__EventInfoCnvAlg()
from Rivet_i.Rivet_iConf import Rivet_i
rivet = Rivet_i("AQPWKTSmoke")
rivet.McEventKey = "GEN_EVENT"
rivet.Analyses = ["AQP_WKTSPLITTINGS:LMODE=EL"]
rivet.AnalysisPath = plugin_dir
rivet.RunName = ""
rivet.HistoFile = yoda_output
rivet.SkipWeights = True
rivet.CrossSection = 0.0
job += rivet

print("AQP_WKTS_INPUT=" + evnt_input)
print("AQP_WKTS_PLUGIN_DIR=" + plugin_dir)
print("AQP_WKTS_OUTPUT=" + yoda_output)
