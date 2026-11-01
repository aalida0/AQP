#!/usr/bin/env python3
"""Static review of one process/configuration/DSID directory; never runs Athena."""
import argparse
import ast
from pathlib import Path


def main(path: Path):
    path = path.resolve(strict=True)
    if not path.is_dir() or not path.name.isdigit():
        raise SystemExit("Expected a process/configuration/<DSID> directory")

    joboptions = sorted(path.glob("mc.*.py")) + sorted(path.glob("mc.*.py.template"))
    if len(joboptions) != 1:
        raise SystemExit("Expected exactly one JO or illustrative JO template")
    jo = joboptions[0]
    source = jo.read_text()
    tree = ast.parse(source, filename=str(jo))
    if "AQP" in source:
        raise SystemExit("Do not put the project name in the JO")
    print("JO_SYNTAX_PASS", jo)

    # Check explicit process-local source requests, not their get_files wrapper
    # implementation: install_file("x.f", ...), install_patch("x.patch", ...).
    names = {"install_file", "install_patch", "apply_source_patch"}
    required = sorted({
        call.args[0].value
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id in names
        and call.args
        and isinstance(call.args[0], ast.Constant)
        and isinstance(call.args[0].value, str)
    })
    missing = [name for name in required if not (path / name).is_file()]
    print("PROCESS_LOCAL_FILES", ", ".join(required) if required else "(none)")
    if missing:
        print("MISSING_LOCAL_AUXILIARIES", ", ".join(missing))

    if jo.suffix == ".template" or missing:
        print("NOT_READY_FOR_SUBMISSION")
        return 2

    print("STATIC_CHECK_PASS")
    print("Not a production or physics validation; verify version pins and Grid weights.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample", type=Path)
    raise SystemExit(main(parser.parse_args().sample))
