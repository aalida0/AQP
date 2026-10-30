#!/usr/bin/env python3
"""Offline unit tests for scripts/aqp_internal_condor_preflight.py.

Run from the repository root:
    python3 -m unittest discover -s tests -p 'test_aqp_internal_condor*.py' -v
No ATLAS environment, Condor service, gridpack or event generation required.
"""
import argparse
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "aqp_internal_condor_preflight.py"
spec = importlib.util.spec_from_file_location("aqp_internal_condor_preflight", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def options(process=None, jo=None, submit=None, logs=None, scan=False):
    return argparse.Namespace(process=process, joboption=jo, submit=submit,
                              log=logs or [], scan_gfs=scan, max_examples=2,
                              json=False)


class CardParsing(unittest.TestCase):
    def test_mg_run_card_value_equals_key_and_case_duplicate(self):
        values, duplicates = mod.assignments(
            "False = MCatNLO_DELTA #old\n"
            "True = mcatnlo_delta !new\n"
            "4, 4, 1 = folding\n"
            "3 = ickkw\n", "run"
        )
        self.assertEqual(values["mcatnlo_delta"], "True")
        self.assertEqual(values["folding"], "4, 4, 1")
        self.assertEqual(len(duplicates["mcatnlo_delta"]), 2)

    def test_config_card_key_equals_value(self):
        values, duplicates = mod.assignments(
            "run_mode = 1\ncluster_type = condor\ncluster_size = 100\n"
            "nb_core = 1\n", "config"
        )
        self.assertEqual(values["run_mode"], "1")
        self.assertEqual(values["cluster_type"], "condor")
        self.assertFalse(duplicates)

    def test_internal_condor_valid(self):
        issues = []
        mod.check_config(issues, {"run_mode": "1", "cluster_type": "condor",
                                  "cluster_size": "100", "nb_core": "1"}, "fixture")
        self.assertNotIn("ERROR", [i["level"] for i in issues])
        self.assertIn("INTERNAL_CONDOR", [i["code"] for i in issues])

    def test_internal_condor_missing_scheduler_configuration(self):
        issues = []
        mod.check_config(issues, {"run_mode": "1", "cluster_type": "pbs",
                                  "cluster_size": "0"}, "fixture")
        self.assertIn("CLUSTER_TYPE", [i["code"] for i in issues])
        self.assertIn("CLUSTER_SIZE", [i["code"] for i in issues])

    def test_local_multicore_is_not_internal_condor(self):
        issues = []
        mod.check_config(issues, {"run_mode": 2, "nb_core": 16}, "fixture")
        self.assertIn("LOCAL_MODE", [i["code"] for i in issues])
        self.assertNotIn("ERROR", [i["level"] for i in issues])


class JOParsing(unittest.TestCase):
    def test_jo_with_variable_core_count_and_dynamic_path(self):
        text = """
CORES = 16
pythia8_path = some_dynamic_value()
modify_config_card(process_dir=process_dir,
    settings={"run_mode": 2, "nb_core": CORES, "pythia8_path": pythia8_path})
"""
        configs = mod.jo_config(text)
        self.assertEqual(configs[0]["run_mode"], 2)
        self.assertEqual(configs[0]["nb_core"], 16)
        self.assertIsNone(configs[0]["pythia8_path"])

    def test_jo_with_named_dictionary(self):
        text = """
config_settings = {"run_mode": 1, "nb_core": 1, "cluster_type": "condor", "cluster_size": 100}
config_settings["pythia8_path"] = custom_function()
modify_config_card(process_dir=p, settings=config_settings)
"""
        cfg = mod.jo_config(text)
        self.assertEqual(cfg[0]["cluster_size"], 100)
        self.assertEqual(cfg[0]["run_mode"], 1)

    def test_no_code_execution(self):
        text = """
import os
os.system("false")
modify_config_card(settings={"run_mode": 2, "nb_core": 4})
"""
        self.assertEqual(mod.jo_config(text)[0]["nb_core"], 4)


class Diagnostics(unittest.TestCase):
    def test_signatures(self):
        self.assertIn("condor_auth", mod.classify_log(
            "Error during authentication: SECMAN:2007\n"))
        self.assertIn("condor_auth", mod.classify_log("SECMAN:2011"))
        self.assertIn("mint_format", mod.classify_log(
            "Fortran runtime error: Bad real number in item 15 of list input"))
        self.assertIn("runtime_failure", mod.classify_log(
            "Fortran runtime error: Bad real number in item 15 of list input"))
        self.assertIn("missing_artifact", mod.classify_log(
            "FileNotFoundError: No such file or directory: /x/GF4.0/log_MINT0.txt"))
        self.assertEqual(mod.classify_log("Normal finish; Time in seconds: 100"), [])

    def test_end_to_end_process_cards_logs_and_cpu_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc = root / "PROCNLO_loop_sm-no_b_mass_0"
            cards = proc / "Cards"
            cards.mkdir(parents=True)
            (cards / "run_card.dat").write_text(
                "False = MCatNLO_DELTA\nTrue = mcatnlo_delta\n4, 4, 1 = folding\n")
            (cards / "amcatnlo_configuration.txt").write_text(
                "run_mode = 1\ncluster_type = condor\ncluster_size = 100\nnb_core = 1\n")
            gf = proc / "SubProcesses" / "P1_test" / "GF1.0"
            gf.mkdir(parents=True)
            for name in ("mint_grids", "results.dat", "res_1.dat"):
                (gf / name).write_text("placeholder\n")
            (gf / "log_MINT1.txt").write_text(
                "Fortran runtime error: Bad real number in item 12\n")
            jo = root / "jo.py"
            jo.write_text('modify_config_card(settings={"run_mode":2,"nb_core":16})\n')
            submit = root / "outer.submit"
            submit.write_text("request_cpus = 8\nqueue\n")
            log = root / "condor.log"
            log.write_text("SECMAN:2007\n")
            result = mod.inspect(options(proc, jo, submit, [log], scan=True))
            codes = [x["code"] for x in result["issues"]]
            self.assertIn("DUPLICATE_RUN_KEY", codes)
            self.assertIn("CPU_OVERCOMMIT", codes)
            self.assertIn("LOG_FAILURE_SIGNATURE", codes)
            self.assertIn("DUPLICATE_MINT1_RISK", codes)
            self.assertEqual(result["gf_scan"]["gf_dirs"], 1)
            self.assertEqual(result["gf_scan"]["counts"]["mint_format"], 1)
            self.assertEqual(result["summary"]["ERROR"], 1)

    def test_missing_logs_are_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "absent.log"
            result = mod.inspect(options(logs=[path]))
            self.assertIn("LOG_MISSING", [i["code"] for i in result["issues"]])

    def test_no_log_failure_is_not_a_success_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "ok.log"
            log.write_text("Time in seconds: 5\n")
            result = mod.inspect(options(logs=[log]))
            self.assertEqual(result["logs"][0]["classifications"], [])
            self.assertEqual(result["summary"].get("ERROR", 0), 0)


if __name__ == "__main__":
    unittest.main()
