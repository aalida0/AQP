#!/usr/bin/env python3
"""Read-only survey of cross-section evidence in AQP PanDA log.generate files.

Scan existing sampled generator logs; print RAW lines referring to cross
sections/sigmaGen and their provenance. No inferred cross-section is assigned.
Log lines from MG integration, unweighted event production, Pythia and Athena
may describe DIFFERENT normalizations: do not adopt a number from this survey
without independent cross-check.

Directory convention from the existing AQP pilot:
 ROOT/{Zee,Wenu}/{standard111,delta111,delta221,delta441}/{v2,v1,v3}
No network calls or Rucio downloads. Handles tar archives/gzip by signature.
"""
import argparse
import gzip
import re
import tarfile
from pathlib import Path

PLAN = tuple(
    (proc, cfg, ("v1" if (proc, cfg) == ("Wenu", "standard111") else
                 "v3" if cfg == "delta441" else "v2"))
    for proc in ("Zee", "Wenu")
    for cfg in ("standard111", "delta111", "delta221", "delta441")
)
LOG_SUFFIXES = (".log.generate", ".log.generate.gz", ".log.generate.txt",
                ".log.generate.txt.gz", ".log.tar.gz", ".log.tgz")
SIGNAL = re.compile(
    r"(?:cross[\s_\-]*section|\bxsec\b|sigmagen|sigma(?:total|matched|nlo)?\s*[:=(])",
    re.IGNORECASE,
)
POTENTIAL_FALSE_POSITIVE = re.compile(
    r"(?i)(?:https?://|cross.section.*uncertainty|"
    r"plot.*cross.section|generation.*cross.section.*configuration)"
)


def log_paths(folder):
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.rglob("*")
                  if p.is_file() and p.name.endswith(LOG_SUFFIXES))


def decode_log(path):
    with path.open("rb") as stream:
        head = stream.read(512)
    if tarfile.is_tarfile(path):
        with tarfile.open(path, "r:*") as tf:
            candidates = [m for m in tf.getmembers() if m.isfile()]
            def rank(member):
                name = Path(member.name).name
                if name == "log.generate":
                    return (0, member.name)
                if name == "payload.stdout":
                    return (1, member.name)
                if name in ("log.generate.txt", "generate.log"):
                    return (2, member.name)
                if "generate" in name and name.endswith((".txt", ".log")):
                    return (3, member.name)
                return (10, member.name)
            for member in sorted(candidates, key=rank):
                if rank(member)[0] > 3:
                    continue
                file = tf.extractfile(member)
                if file is None:
                    continue
                raw = file.read()
                if raw.startswith(b"\x1f\x8b"):
                    raw = gzip.decompress(raw)
                return raw.decode("utf-8", "replace")
        raise ValueError("archive has no recognizable generator stdout")
    if head.startswith(b"\x1f\x8b"):
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as file:
            return file.read()
    return path.read_text(encoding="utf-8", errors="replace")


def candidates_from_text(content, max_lines=10):
    candidates = []
    for n, line in enumerate(content.splitlines(), 1):
        if not SIGNAL.search(line) or POTENTIAL_FALSE_POSITIVE.search(line):
            continue
        line = line.strip()
        if len(line) > 350:
            line = line[:347] + "..."
        if line:
            candidates.append((n, line))
    # Keep first and last evidence if the log contains many repeated lines.
    if len(candidates) > max_lines:
        half = max_lines // 2
        candidates = candidates[:half] + candidates[-(max_lines-half):]
    return candidates


def build_report(root, max_logs=10, max_lines=5):
    lines = [
        "AQP generator log cross-section evidence (RAW text, unvalidated)",
        f"Log directory: {root}",
        "CAUTION: a matching sigma/xsec line is not yet a certified physical FxFx rate.",
        "Do not derive full-sample XS by averaging unrelated stages of a log.",
        "",
    ]
    for process, cfg, version in PLAN:
        folder = root / process / cfg / version
        files = log_paths(folder)
        sampled = files[:max_logs] if max_logs else files
        lines.append(f"=== {process}/{cfg}/{version} : "
                     f"{len(sampled)}/{len(files)} scanned ===")
        if not sampled:
            lines.append(f"  NO LOGS FOUND at {folder}")
            continue
        shown_any = False
        for path in sampled:
            try:
                content = decode_log(path)
                matches = candidates_from_text(content, max_lines)
            except (OSError, ValueError, EOFError, tarfile.TarError) as exc:
                lines.append(f"  ERROR {path.name}: {type(exc).__name__}: {exc}")
                continue
            if not matches:
                continue
            shown_any = True
            lines.append(f"  FILE {path.name}")
            for line_no, text in matches:
                lines.append(f"    L{line_no}: {text}")
        if not shown_any:
            lines.append("  NO XS/SIGMA TEXT FOUND IN THESE GENERATOR LOGS")
        lines.append("")
    lines.extend([
        "RESULT: RAW_XSEC_EVIDENCE_ONLY",
        "Required next checks: generator provenance, bias/event_norm convention,",
        "post-FxFx matching, per-job spread, and EVNT/HepMC xsec agreement.",
    ])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path("/data/aalida/AQP/aqp_log_comparison"))
    parser.add_argument("--max-logs", type=int, default=10,
                        help="Per sample; 0 means all")
    parser.add_argument("--max-lines", type=int, default=6,
                        help="Max candidate text lines per log")
    parser.add_argument("--output", type=Path, default=None,
                        help="Optional saved report (under /home recommended)")
    args = parser.parse_args()
    if args.max_logs < 0 or args.max_lines < 1:
        parser.error("--max-logs must be >=0 and --max-lines >=1")
    report = build_report(args.root.expanduser(), args.max_logs, args.max_lines)
    if args.output:
        args.output.expanduser().parent.mkdir(parents=True, exist_ok=True)
        args.output.expanduser().write_text(report, encoding="utf-8")
        print(f"REPORT_PATH={args.output}")
    print(report)


if __name__ == "__main__":
    main()
