#!/usr/bin/env python3
"""Prepare combined MG5 3.5.11 Condor fixes for four *bundled* Wenu backends.

Never modifies originals. The local file must match its pinned SHA256 AND
differ from the central ATLAS source solely by the exact known timing-log
instrumentation, which is preserved verbatim. Uses pre-reviewed status and
submission fix functions in this directory.

Default: read-only verification and diff summary.
--write: create new candidate files in an existing empty output directory.

Does not import MadGraph, submit jobs, or access any integration grids.
"""
import argparse
import ast
import difflib
import hashlib
from pathlib import Path
import sys

from aqp_prepare_condor_status_patch import patch_text as patch_status
from aqp_prepare_condor_submit_patch import patch_text as patch_submit

CENTRAL_SHA = "feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe"
BUNDLES = {
    "standard111": ("624717e154fd9bbf0cb7398f310a93c7d7f48c8d7c1a88bce46cc76844c9e5fc", "standard111"),
    "delta111": ("10f51467078d72337a0293b09e62d07f68aa6231eae778ef3ec9326ad13d39c0", "delta111"),
    "delta221": ("f2e95e0143ab6a770679aa7f530d54490fe3f42afaddc6480db761326e8ead16", "delta221"),
    # This original process was renamed; its historical timing-log path still says delta441.
    "delta441_backup": ("6c6e193d217313d1b1d04cb28915bf05078109cc8f0da65d9c6f9f1a493adf8b", "delta441"),
}

OLD = "        if log is None:\n            log = '/dev/null'\n"


def sha(value):
    return hashlib.sha256(value).hexdigest()


def timing_replacement(config):
    label = BUNDLES[config][1]
    target = "/home/aalida/AQP/Wjets/WENU/%s/aqp_condor_timing" % label
    return (
        "        if log is None:\n"
        "            if os.path.basename(str(prog)) == 'ajob1' and argument:\n"
        "                step = str(argument[3]) if len(argument) > 3 else 'unknown'\n"
        "\n"
        "                if step in ('0', '1'):\n"
        "                    log = os.path.join(\n"
        "                        '%s',\n" % target +
        "                        '%s__GF%s__step%s.log' % (\n"
        "                            os.path.basename(os.path.normpath(cwd)),\n"
        "                            argument[0],\n"
        "                            step,\n"
        "                        ),\n"
        "                    )\n"
        "                else:\n"
        "                    log = '/dev/null'\n"
        "            else:\n"
        "                log = '/dev/null'\n"
    )


def method_bounds(source, names):
    tree = ast.parse(source)
    found = [x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == "CondorCluster"]
    if len(found) != 1:
        raise ValueError("CondorCluster class not found uniquely")
    positions = []
    for name in names:
        funcs = [x for x in found[0].body if isinstance(x, ast.FunctionDef) and x.name == name]
        if len(funcs) != 1:
            raise ValueError("Expected one CondorCluster." + name)
        f = funcs[0]
        positions.append((f.lineno - 1, f.end_lineno, name))
    return sorted(positions, reverse=True)


def add_known_timing(central, config):
    lines = central.splitlines(keepends=True)
    for start, end, name in method_bounds(central, ("submit", "submit2")):
        original = "".join(lines[start:end])
        if original.count(OLD) != 1:
            raise ValueError("Central %s has unexpected timing block" % name)
        lines[start:end] = original.replace(OLD, timing_replacement(config), 1).splitlines(keepends=True)
    return "".join(lines)


def build(central, local, config):
    expected = add_known_timing(central, config)
    if local != expected:
        diff = list(difflib.unified_diff(expected.splitlines(), local.splitlines(),
                                         fromfile="expected-timing-only",
                                         tofile="actual-local", n=2))
        raise ValueError("%s has modifications beyond approved timing instrumentation; first diff:\n%s" %
                         (config, "\n".join(diff[:18])))
    first = patch_status(local)
    candidate = patch_submit(first)
    compile(candidate, config + "/cluster.py", "exec")
    if candidate.count(timing_replacement(config)) != 2:
        raise ValueError("%s: timing instrumentation was not preserved exactly" % config)
    if candidate == local:
        raise ValueError("No changes made")
    return candidate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", required=True, type=Path,
                   help="Parent of standard111, delta111, delta221, delta441_backup")
    p.add_argument("--central", required=True, type=Path,
                   help="Exact ATLAS 3.5.11 madgraph/various/cluster.py")
    p.add_argument("--outdir", type=Path, help="Existing empty temporary directory")
    p.add_argument("--write", action="store_true", help="Create candidate copies (never overwrite)")
    p.add_argument("--show-diff", action="store_true", help="Show compact unified diffs")
    args = p.parse_args()
    if args.write and args.outdir is None:
        p.error("--write requires --outdir")
    try:
        central_file = args.central.expanduser().resolve(strict=True)
        central_raw = central_file.read_bytes()
        if sha(central_raw) != CENTRAL_SHA:
            raise ValueError("Unexpected central source fingerprint: " + sha(central_raw))
        central_text = central_raw.decode("utf-8")
        base = args.base.expanduser().resolve(strict=True)
        generated = {}
        for config, (expected_hash, _) in BUNDLES.items():
            local_file = base / config / "PROCNLO_loop_sm-no_b_mass_0/bin/internal/cluster.py"
            local_raw = local_file.read_bytes()
            if sha(local_raw) != expected_hash:
                raise ValueError("%s source fingerprint changed: %s" % (config, sha(local_raw)))
            local_text = local_raw.decode("utf-8")
            candidate = build(central_text, local_text, config)
            generated[config] = candidate
            print("VERIFIED", config, "bundle=" + expected_hash,
                  "candidate=" + sha(candidate.encode("utf-8")))
            if args.show_diff:
                print("".join(difflib.unified_diff(
                    local_text.splitlines(True), candidate.splitlines(True),
                    fromfile=config + " original", tofile=config + " candidate", n=2)))
        if not args.write:
            print("DRY_RUN_ONLY: no files changed")
            return
        dest_root = args.outdir.expanduser().resolve(strict=True)
        if not dest_root.is_dir() or list(dest_root.iterdir()):
            raise ValueError("Output directory must exist and be empty")
        if (str(dest_root).startswith("/cvmfs/") or
                "/AQP/Wjets/" in str(dest_root) or
                "/AQP/Zjets/" in str(dest_root)):
            raise ValueError("Refusing to write into CVMFS or AQP production")
        for config, candidate in generated.items():
            dest = dest_root / config
            dest.mkdir()
            with (dest / "cluster.py").open("x", encoding="utf-8") as f:
                f.write(candidate)
            print("CANDIDATE_CREATED", dest / "cluster.py")
        print("NO_EXISTING_SOURCE_MODIFIED; CANDIDATES_NOT_INSTALLED")
    except (OSError, UnicodeError, ValueError, SyntaxError) as exc:
        p.error(str(exc))


if __name__ == "__main__":
    main()
