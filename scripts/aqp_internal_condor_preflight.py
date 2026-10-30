#!/usr/bin/env python3
"""Read-only MG5_aMC@NLO/HTCondor preflight for AQP (Python >=3.9).

No imports from MadGraph, no shell commands, no pickle loading, no writes.
Card checks describe the *current* files, not historical submission settings.
A completed MINT log is not proof of valid integration grids.
"""
import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import re

SIGNATURES = (
    ("condor_auth", re.compile(r"SECMAN:20(?:07|11)|authentication failed|security negotiation", re.I)),
    ("condor_submit", re.compile(r"condor_submit.*(?:fail|error)|failed to submit|submission.*failed", re.I)),
    ("condor_transport", re.compile(r"(?:condor_q|condor_wait|condor_rm|schedd).*?(?:timed out|timeout|failed|error)", re.I)),
    ("missing_artifact", re.compile(r"(?:FileNotFoundError|No such file or directory).*?(?:MINT|GF|mint_grids|results\.dat)|(?:MINT|GF)[^\n]{0,100}(?:not found|missing)", re.I)),
    ("mint_format", re.compile(r"Bad real number in item|mint_module\.f90.*(?:error|runtime)", re.I)),
    ("runtime_failure", re.compile(r"Fortran runtime error|segmentation fault|SIGSEGV|SIGFPE|traceback \(most recent call last\)", re.I)),
)
KNOWN = ("standard111", "delta111", "delta221", "delta441_backup")


def assignments(text, kind):
    """Return effective values and duplicate entries (last assignment wins).

    MG run cards are VALUE = KEY; aMC configuration cards are KEY = VALUE.
    """
    found = {}
    for lineno, original in enumerate(text.splitlines(), 1):
        line = re.split(r"[#!]", original, maxsplit=1)[0].strip()
        if "=" not in line:
            continue
        left, right = (s.strip() for s in line.split("=", 1))
        if kind == "run":
            value, key = left, right
        else:
            key, value = left, right
        key = key.lower()
        if not re.fullmatch(r"[a-z][a-z_0-9]*", key):
            continue
        found.setdefault(key, []).append((lineno, value))
    return ({key: items[-1][1] for key, items in found.items()},
            {key: items for key, items in found.items() if len(items) > 1})


def literal(node, bindings):
    if isinstance(node, ast.Name):
        return bindings.get(node.id)
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return None


def jo_config(text):
    """Extract known literal settings, without executing the JobOption."""
    tree = ast.parse(text)
    bindings = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = literal(node.value, bindings)
                elif (isinstance(target, ast.Subscript)
                      and isinstance(target.value, ast.Name)
                      and isinstance(bindings.get(target.value.id), dict)):
                    key = literal(target.slice, bindings)
                    if isinstance(key, str):
                        bindings[target.value.id][key] = literal(node.value, bindings)
    candidates = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "modify_config_card":
            for keyword in node.keywords:
                if keyword.arg == "settings":
                    val = literal(keyword.value, bindings)
                    candidates.append(val if isinstance(val, dict) else {})
    return candidates


def add(issues, severity, code, message):
    issues.append({"level": severity, "code": code, "message": message})


def check_config(issues, effective, origin):
    if not effective:
        add(issues, "INFO", "CONFIG_MISSING", origin + ": no readable settings")
        return
    try:
        mode = int(str(effective["run_mode"]))
    except (KeyError, ValueError, TypeError):
        add(issues, "WARN", "MODE_UNKNOWN", origin + ": run_mode missing or nonliteral")
        return
    if mode == 1:
        if str(effective.get("cluster_type", "")).lower().strip("'\"") != "condor":
            add(issues, "ERROR", "CLUSTER_TYPE", origin + ": run_mode=1 needs cluster_type=condor for HTCondor")
        try:
            size = int(str(effective["cluster_size"]))
            if size < 1:
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            add(issues, "ERROR", "CLUSTER_SIZE", origin + ": run_mode=1 needs positive cluster_size")
        add(issues, "INFO", "INTERNAL_CONDOR", origin + ": MadGraph submits HTCondor jobs internally")
    elif mode == 2:
        add(issues, "INFO", "LOCAL_MODE", origin + ": local multicore, NOT MG internal Condor")
        try:
            if int(str(effective.get("nb_core", 0))) < 1:
                raise ValueError()
        except (ValueError, TypeError):
            add(issues, "ERROR", "LOCAL_CORES", origin + ": invalid nb_core")
    elif mode == 0:
        add(issues, "INFO", "SERIAL_MODE", origin + ": serial mode")
    else:
        add(issues, "WARN", "MODE_OTHER", origin + ": unexpected run_mode=" + str(mode))


def classify_log(text):
    return [label for label, pattern in SIGNATURES if pattern.search(text)]


def inspect_gfs(process, issues, max_examples):
    sub = process / "SubProcesses"
    if not sub.is_dir():
        add(issues, "ERROR", "MISSING_SUBPROCESSES", str(sub))
        return {"gf_dirs": 0}
    gfdirs = sorted(q for q in sub.glob("P*/GF*") if q.is_dir())
    counters = Counter()
    examples = {}
    for gf in gfdirs:
        log = gf / "log_MINT1.txt"
        if log.is_file():
            body = log.read_text(errors="replace")
            for label in classify_log(body):
                counters[label] += 1
                if len(examples.setdefault(label, [])) < max_examples:
                    examples[label].append(str(gf.relative_to(process)))
        elif (gf / "mint_grids").is_file():
            counters["mint1_log_absent_but_grids_present"] += 1
        for name in ("mint_grids", "results.dat", "res_1.dat"):
            path = gf / name
            if not path.is_file() or path.stat().st_size == 0:
                counters["missing_" + name.replace(".", "_")] += 1
                if len(examples.setdefault("missing_" + name, [])) < max_examples:
                    examples["missing_" + name].append(str(gf.relative_to(process)))
    if counters["condor_auth"] or counters["condor_transport"] or counters["condor_submit"]:
        add(issues, "WARN", "SCHEDULER_FAILURES", "Historical MINT1 logs contain HTCondor errors; verify schedd/auth and per-attempt status. Never resubmit blindly.")
    if counters["mint_format"]:
        add(issues, "WARN", "DUPLICATE_MINT1_RISK", "MINT1 bad-real errors may result from duplicate submissions rewriting shared mint_grids; log errors alone do not invalidate saved grids.")
    if not gfdirs:
        add(issues, "WARN", "NO_GF", str(sub) + ": no GF channel directories")
    return {"gf_dirs": len(gfdirs), "counts": dict(sorted(counters.items())), "examples": examples}


def inspect(args):
    issues = []
    report = {"process": str(args.process) if args.process else None,
              "joboption": str(args.joboption) if args.joboption else None,
              "submit": str(args.submit) if args.submit else None,
              "issues": issues}
    if args.process:
        p = args.process.expanduser().resolve()
        if not p.is_dir():
            add(issues, "ERROR", "PROCESS_MISSING", str(p))
        else:
            card = p / "Cards" / "run_card.dat"
            cfg = p / "Cards" / "amcatnlo_configuration.txt"
            if card.is_file():
                values, duplicates = assignments(card.read_text(errors="replace"), "run")
                report["run_card"] = {k: values.get(k) for k in
                                      ("mcatnlo_delta", "folding", "ickkw", "req_acc", "lhaid", "nevents")}
                for key, entries in duplicates.items():
                    unique = {v.casefold() for _, v in entries}
                    level = "WARN" if len(unique) > 1 else "INFO"
                    add(issues, level, "DUPLICATE_RUN_KEY", f"{key} at lines {[n for n, _ in entries]} (effective={entries[-1][1]!r})")
            else:
                add(issues, "WARN", "RUN_CARD_MISSING", str(card))
            if cfg.is_file():
                values, duplicates = assignments(cfg.read_text(errors="replace"), "config")
                report["mg_config"] = {k: values.get(k) for k in ("run_mode", "nb_core", "cluster_type", "cluster_size")}
                for key, entries in duplicates.items():
                    if len({v.casefold() for _, v in entries}) > 1:
                        add(issues, "WARN", "DUPLICATE_CONFIG_KEY", f"{key} at lines {[n for n, _ in entries]}")
                check_config(issues, values, str(cfg))
            else:
                add(issues, "WARN", "CONFIG_CARD_MISSING", str(cfg))
            if args.scan_gfs:
                report["gf_scan"] = inspect_gfs(p, issues, args.max_examples)
    jo_settings = []
    if args.joboption:
        path = args.joboption.expanduser()
        if path.is_file():
            try:
                jo_settings = jo_config(path.read_text(errors="replace"))
                if not jo_settings:
                    add(issues, "WARN", "JO_NO_CONFIG", "No statically inspectable modify_config_card() call")
                for settings in jo_settings:
                    check_config(issues, settings, str(path))
            except SyntaxError as exc:
                add(issues, "ERROR", "JO_SYNTAX", str(exc))
        else:
            add(issues, "ERROR", "JO_MISSING", str(path))
        report["jo_config"] = jo_settings
    if args.submit:
        path = args.submit.expanduser()
        if not path.is_file():
            add(issues, "ERROR", "SUBMIT_MISSING", str(path))
        else:
            match = re.search(r"(?im)^\s*request_cpus\s*=\s*(\d+)", path.read_text(errors="replace"))
            cpu = int(match.group(1)) if match else None
            report["request_cpus"] = cpu
            if cpu is None:
                add(issues, "WARN", "REQUEST_CPUS_UNKNOWN", str(path))
            for settings in jo_settings:
                if settings.get("run_mode") == 2 and isinstance(settings.get("nb_core"), int) and cpu is not None:
                    if settings["nb_core"] > cpu:
                        add(issues, "ERROR", "CPU_OVERCOMMIT",
                            f"JO nb_core={settings['nb_core']} exceeds submit request_cpus={cpu}")
    report["summary"] = dict(Counter(i["level"] for i in issues))
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--process", type=Path, help="An existing PROCNLO_* process directory")
    ap.add_argument("--joboption", type=Path, help="JO to inspect statically (never executed)")
    ap.add_argument("--submit", type=Path, help="Outer HTCondor submit file, if applicable")
    ap.add_argument("--scan-gfs", action="store_true", help="Read MINT1 logs and check GF artifacts (optional)")
    ap.add_argument("--max-examples", type=int, default=4)
    ap.add_argument("--json", action="store_true", help="Print machine-readable JSON to stdout")
    args = ap.parse_args()
    if not any((args.process, args.joboption, args.submit)):
        ap.error("Specify --process and/or --joboption, optionally --submit")
    if args.scan_gfs and not args.process:
        ap.error("--scan-gfs requires --process")
    if args.max_examples < 0:
        ap.error("--max-examples must be nonnegative")
    report = inspect(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("MG INTERNAL CONDOR PREFLIGHT (READ ONLY)")
        print("Process:", report["process"])
        for key in ("run_card", "mg_config", "jo_config", "request_cpus", "gf_scan"):
            if key in report:
                print(key + ":", json.dumps(report[key], sort_keys=True))
        for issue in report["issues"]:
            print(f"[{issue['level']}] {issue['code']}: {issue['message']}")
        print("SUMMARY:", report["summary"])
        print("NOTE: no MG jobs submitted; historical configuration and file presence do not prove runtime reliability.")
    return 2 if report["summary"].get("ERROR", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
