# Offline EVNT-to-Rivet, fresh nominal-weight campaign. XS in pb from matched generator log.
import math
import os

inp = os.environ["AQP_RIVET_INPUT"]
out = os.environ["AQP_RIVET_OUTPUT"]
analyses = os.environ["AQP_RIVET_ANALYSES"].split(",")
xs_pb = float(os.environ["AQP_RIVET_XSEC_PB"])
if not os.path.isfile(inp) or os.path.exists(out):
    raise RuntimeError("Missing EVNT input or existing YODA output")
if not math.isfinite(xs_pb) or xs_pb <= 0:
    raise RuntimeError("Positive validated generator cross section required")

theApp.EvtMax = -1
import AthenaPoolCnvSvc.ReadAthenaPool
from AthenaCommon.AppMgr import ServiceMgr as svcMgr
svcMgr.EventSelector.InputCollections = [inp]
from AthenaCommon.AlgSequence import AlgSequence
job = AlgSequence()
from xAODEventInfoCnv.xAODEventInfoCnvConf import xAODMaker__EventInfoCnvAlg
job += xAODMaker__EventInfoCnvAlg()
from Rivet_i.Rivet_iConf import Rivet_i
rivet = Rivet_i("AQPFreshRivet")
rivet.McEventKey = "GEN_EVENT"
rivet.Analyses = analyses
rivet.RunName = ""
rivet.HistoFile = out
rivet.AnalysisPath = os.getcwd()
rivet.SkipWeights = True  # Keep signed nominal weights; skip systematic streams, not nominal weights.
rivet.CrossSection = xs_pb
job += rivet
print("AQP_FRESH_XSEC_PB=", xs_pb, "ANALYSES=", analyses)
