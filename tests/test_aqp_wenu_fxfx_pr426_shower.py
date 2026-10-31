#!/usr/bin/env python3
"""Static regression tests for Wenu PR426 before/after Pythia FxFx shower."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
JO=ROOT/"joboptions/wenu_fxfx_pr426_shower/100007/mc.aMCPy8EG_Wenu_FxFx_2jets_PR426_shower.py"
RUNNER=ROOT/"scripts/run_wenu_fxfx_pr426_shower.sh"
SUBMIT=ROOT/"condor/wenu_fxfx_pr426_before_18000_shower.submit"

class PR426Shower(unittest.TestCase):
    def test_jo_is_shower_only_with_standard_fxfx(self):
        s=JO.read_text()
        compile(s,str(JO),"exec")
        for expected in ("Pythia8_A14_NNPDF23LO_EvtGen_Common",
                         "Pythia8_aMcAtNlo", "Pythia8_FxFx_A14mod",
                         "PYTHIA8_nJetMax = 2", "PYTHIA8_qCut = 20.0",
                         "SoftQCD:inelastic = off",
                         "AQP_FXFX_PR426_SHOWER_MADGRAPH_NOT_INVOKED"):
            self.assertIn(expected,s)
        for forbidden in ("new_process(", "generate(", "arrange_output(", "MADGRAPH_PDFSETTING"):
            self.assertNotIn(forbidden,s)

    def test_n_events_per_job_conforms_to_atlas_large_job_rule(self):
        # Execute only the two assignment statements, without Athena.
        import ast
        from types import SimpleNamespace
        tree=ast.parse(JO.read_text())
        selected=[]
        for node in tree.body:
            if isinstance(node,ast.Assign):
                names=[ast.unparse(t) for t in node.targets]
                if "_requested_evnt" in names or "evgenConfig.nEventsPerJob" in names:
                    selected.append(node)
        self.assertEqual(len(selected),2)
        assignment=compile(ast.Module(body=selected,type_ignores=[]),
                           str(JO),"exec")
        for requested,expected in [(200,200),(10000,10000),
                                   (18000,20000),(20000,20000),
                                   (20001,30000)]:
            with self.subTest(requested=requested):
                config=SimpleNamespace()
                namespace={"runArgs":SimpleNamespace(maxEvents=requested),
                           "evgenConfig":config}
                exec(assignment,namespace)
                self.assertEqual(config.nEventsPerJob,expected)

    def test_runner_isolation(self):
        r=subprocess.run(["bash","-n",str(RUNNER)],
                         capture_output=True,text=True,timeout=5)
        self.assertEqual(r.returncode,0,r.stderr)
        s=RUNNER.read_text()
        for expected in ("gzip -cd", "input.events",
                         "--inputGeneratorFile=input.events",
                         "AQP_FXFX_PR426_CASE",
                         "JetMatchingMadgraph", "request"):
            if expected!="request":
                self.assertIn(expected,s)
        self.assertNotIn("condor_submit",s)
        self.assertNotIn("run_mode=1",s)
        self.assertIn("_CONDOR_SCRATCH_DIR",s)
        for stage in ("WORKDIR_CREATED", "VERIFYING_LHE_GZIP",
                      "DECOMPRESSING_50K_LHE", "LHE_STAGED",
                      "STARTING_ATLAS_SETUP", "ATLAS_SETUP_SUCCEEDED",
                      "LAUNCHING_GEN_TF"):
            self.assertIn("stage " + stage, s)
        self.assertIn("trap early_exit EXIT", s)
        self.assertIn("set +e\nset +u\nsource", s)
        self.assertIn("request",SUBMIT.read_text())

    def test_rescue_and_staging_syntax(self):
        resume=ROOT/"scripts/resume_wenu_fxfx_pr426_shower200.sh"
        for script in (RUNNER,resume):
            with self.subTest(script=script):
                p=subprocess.run(["bash","-n",str(script)],
                                 capture_output=True,text=True,timeout=5)
                self.assertEqual(p.returncode,0,p.stderr)
        original=RUNNER.read_text()
        rescue=resume.read_text()
        self.assertIn('gzip -cd "$INPUT" > "$OUT/input.events"',original)
        self.assertIn('ln -s "$OUT/input.events" "$WORK/input.events"',original)
        self.assertIn('cmp -s "$WORK/input.events" "$DATA_DIR/input.events"',rescue)
        self.assertIn('source_50k_lhe.gz',rescue)
        self.assertIn('source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh"',rescue)
        self.assertIn('Gen_tf.py --ecmEnergy=13000 --maxEvents=200',rescue)
        self.assertIn('AQP_PR426_SHOWER200_PASS',rescue)

    def test_batch_is_one_core_not_nested(self):
        s=SUBMIT.read_text()
        self.assertIn("request_cpus = 1",s)
        self.assertIn("before 18000",s)
        self.assertIn("should_transfer_files = YES",s)

if __name__=="__main__":
    unittest.main()
