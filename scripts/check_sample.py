#!/usr/bin/env python3
"""Static review of one process/configuration/DSID directory (no Athena)."""
import argparse
import ast
from pathlib import Path

def main(path: Path):
    path = path.resolve(strict=True)
    if not path.is_dir() or not path.name.isdigit():
        raise SystemExit("Expected a process/configuration/<DSID> directory")
    jo_files = sorted(path.glob("mc.*.py")) + sorted(path.glob("mc.*.py.template"))
    if len(jo_files) != 1:
        raise SystemExit("Expected one complete JO or one illustrative JO template")
    jo = jo_files[0]
    src = jo.read_text()
    ast.parse(src, filename=str(jo))
    print("JO_SYNTAX_PASS", jo)
    if "AQP" in src:
        raise SystemExit("JO must not reference the project name")
    if jo.suffix == ".template":
        print("SCAFFOLD_ONLY: template cannot be submitted")
    references = []
    import re
    for f in re.findall(r'get_files",\s*"-data",\s*(["\x27])([^"\x27]+)\1', src):
        references.append(f[1])
    missing = [name for name in references if not (path / name).is_file()]
    if missing:
        print("MISSING_LOCAL_AUXILIARIES:", ", ".join(sorted(set(missing))))
        print("NOT_READY_FOR_SUBMISSION")
        return 2
    print("STATIC_LOCAL_AUXILIARIES_PASS", len(references))
    print("NOTE: syntax/auxiliary checks do NOT verify physics or Grid readiness")
    return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("sample", type=Path)
    raise SystemExit(main(p.parse_args().sample))
