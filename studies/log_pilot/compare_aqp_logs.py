#!/usr/bin/env python3
"""Compare a balanced pilot of Zee and Wenu FxFx Athena log.generate files.

Only measurements explicitly present in the logs are reported. All 8
configurations are printed, including configurations with missing files.
"""
import argparse
import csv
import gzip
import math
import re
import tarfile
from pathlib import Path

FLOAT = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
PLAN = [(p, c, 'v3' if c == 'delta441' else 'v2',
         50 if c == 'delta441' else 10,
         1000 if c == 'delta441' else 5000)
        for p in ('Zee', 'Wenu')
        for c in ('standard111', 'delta111', 'delta221', 'delta441')]


def last_number(text, keys):
    """Return most recent numerical metric matching any named key."""
    matches = []
    for key in keys:
        rx = re.compile(r'(?<![\w])' + key + r'\s*(?:[:=]|\|)\s*(' + FLOAT + r')', re.I)
        matches.extend((m.start(), m.group(1)) for m in rx.finditer(text))
    if not matches:
        return None
    return float(max(matches)[1].replace('D', 'E').replace('d', 'e'))


def pythia_counts(text):
    """Find last Pythia8 'All included processes' row or named counters."""
    rows = []
    for line in text.splitlines():
        if 'All included processes' not in line and 'All included subprocesses' not in line:
            continue
        m = re.search(r'All included (?:sub)?processes\s*\|?\s*(\d+)\s*\|?\s*(\d+)\s*\|?\s*(\d+)\b', line, re.I)
        if m:
            rows.append(tuple(map(int, m.groups())))
    if rows:
        return rows[-1]
    keys = [('nTried', 'events[ _-]*tried', 'Pythia[ _-]*events[ _-]*tried'),
            ('nSelected', 'events[ _-]*selected'),
            ('nAccepted', 'events[ _-]*accepted')]
    counts = [last_number(text, key) for key in keys]
    return tuple(int(round(v)) if v is not None else None for v in counts)


def explicit_seconds(text):
    """Use only explicitly identified transform/generation wall times."""
    patterns = [
        r'\b(?:total[ _-]+)?generation[ _-]+(?:wall[ _-]+)?(?:time|elapsed(?:[ _-]+time)?)[ _-]*(?:\(s\))?\s*[:=]\s*(' + FLOAT + r')\s*(?:s|sec|seconds)\b',
        r'\bgenerate[ _-]+executor[ _-]+(?:wall[ _-]+)?(?:time|elapsed)\s*[:=]\s*(' + FLOAT + r')\s*(?:s|sec|seconds)\b',
        r'\b(?:total[ _-]+)?(?:transform|job)[ _-]+(?:wall[ _-]+)?elapsed[ _-]+time\s*[:=]\s*(' + FLOAT + r')\s*(?:s|sec|seconds)\b',
    ]
    found = [(m.start(), float(m.group(1).replace('D', 'E')))
             for pattern in patterns for m in re.finditer(pattern, text, re.I)]
    return max(found)[1] if found else None


def timestamp_span(text):
    """Fallback wall-time proxy from generate HH:MM:SS lines (<24h only)."""
    times = re.findall(r'^generate\s+(\d{2}):(\d{2}):(\d{2})\b', text, re.M)
    if len(times) < 2:
        return None
    def secs(t):
        return int(t[0])*3600 + int(t[1])*60 + int(t[2])
    start, end = secs(times[0]), secs(times[-1])
    span = (end-start) % 86400
    return float(span) if span > 0 else None


def load_log(path):
    """Load actual Athena generator log; PanDA .log.generate is often tar.gz.

    Inspect the file bytes rather than guessing the format from the filename.
    A single matching generator stdout is used to avoid double-counting.
    """
    with path.open("rb") as fh:
        magic = fh.read(512)
    tar_like = magic.startswith(b"\x1f\x8b") or magic[257:262] == b"ustar" or path.name.endswith((".tgz", ".tar.gz"))
    if tar_like and tarfile.is_tarfile(path):
        with tarfile.open(path, "r:*") as archive:
            members = [m for m in archive.getmembers() if m.isfile()]
            def rank(member):
                name = Path(member.name).name
                if name == "log.generate":
                    return (0, member.name)
                if name == "payload.stdout":
                    return (1, member.name)
                if name in ("generate.log", "log.generate.txt"):
                    return (2, member.name)
                if "generate" in name and name.endswith((".log", ".txt")):
                    return (3, member.name)
                return (10, member.name)
            for member in sorted(members, key=rank):
                if rank(member)[0] >= 10:
                    continue
                stream = archive.extractfile(member)
                if stream:
                    payload = stream.read()
                    if payload.startswith(b"\x1f\x8b"):
                        payload = gzip.decompress(payload)
                    return payload.decode("utf-8", "replace")
        raise ValueError("Archive contains no recognized generator log; inspect tar -tf <file>")
    if magic.startswith(b"\x1f\x8b"):
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    return path.read_text(encoding="utf-8", errors="replace")


def parse_one(path, process, cfg, version, events):
    row = dict(process=process, config=cfg, version=version,
               filename=str(path), expected_events=events)
    try:
        text = load_log(path)
        row['parse_error'] = ''
    except (OSError, ValueError, tarfile.TarError) as exc:
        row['parse_error'] = str(exc)
        return row
    tried, selected, accepted = pythia_counts(text)
    if tried is not None and accepted is not None and (tried < accepted or tried <= 0):
        tried = accepted = selected = None
        row['parse_error'] = 'Inconsistent Pythia counts'
    pos = last_number(text, ('sumOfPosWeights', 'sum[ _-]*of[ _-]*positive[ _-]*weights', 'sumPosWeights'))
    neg = last_number(text, ('sumOfNegWeights', 'sum[ _-]*of[ _-]*negative[ _-]*weights', 'sumNegWeights'))
    npos = last_number(text, ('nPosWeights', 'nPositiveWeights', 'nPosEvents'))
    nneg = last_number(text, ('nNegWeights', 'nNegativeWeights', 'nNegEvents'))
    row.update(tried=tried, selected=selected, accepted=accepted,
               sum_pos=pos if pos is not None and pos >= 0 else None,
               abs_sum_neg=abs(neg) if neg is not None else None,
               n_pos=npos if npos is not None and npos >= 0 else None,
               n_neg=nneg if nneg is not None and nneg >= 0 else None,
               generation_wall_s=explicit_seconds(text), log_span_s=timestamp_span(text),
               close_to_expected=(accepted is not None and abs(accepted-events) <= max(5, 0.05*events)))
    return row


def ratio(a, b):
    return a/b if b and a is not None else None


def weighted_fraction(rows, positive, negative):
    good = [r for r in rows if r.get(positive) is not None and r.get(negative) is not None]
    a = sum(r[positive] for r in good)
    b = sum(r[negative] for r in good)
    return ratio(b, a+b), len(good)


def time_per_event(rows, key):
    good = [r for r in rows if r.get(key) is not None and r.get('accepted') and r.get('close_to_expected')]
    return ratio(sum(r[key] for r in good), sum(r['accepted'] for r in good)), len(good)


def as_csv(path, rows, fields):
    with path.open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def fmt(x, decimals=2, pct=False):
    if x is None or not math.isfinite(x):
        return 'NA'
    return f'{x*100 if pct else x:.{decimals}f}'


def all_log_paths(folder):
    items = []
    for p in folder.rglob('*') if folder.exists() else ():
        if p.is_file() and (p.name.endswith(('.log.generate', '.log.generate.gz', '.log.generate.txt', '.log.generate.txt.gz', '.log.tgz', '.log.tar.gz'))):
            items.append(p)
    return sorted(set(items))


def summarize(root):
    individual, summary = [], []
    for process, cfg, version, target_jobs, events in PLAN:
        path = root/process/cfg/version
        logs = [parse_one(f, process, cfg, version, events) for f in all_log_paths(path)]
        individual.extend(logs)
        good = [r for r in logs if not r.get('parse_error')]
        valid = [r for r in good if r.get('close_to_expected')]
        wf, nw = weighted_fraction(valid, 'sum_pos', 'abs_sum_neg')
        nf, nn = weighted_fraction(valid, 'n_pos', 'n_neg')
        fxs = [r for r in valid if r.get('tried') and r.get('accepted') is not None]
        fx = ratio(sum(r['accepted'] for r in fxs), sum(r['tried'] for r in fxs))
        tm, nt = time_per_event(valid, 'generation_wall_s')
        span, ns = time_per_event(valid, 'log_span_s')
        dil = 1/(1-2*wf)**2 if wf is not None and wf < 0.5 else None
        summary.append(dict(process=process, config=cfg, version=version,
                            target_logs=target_jobs, downloaded_logs=len(logs),
                            valid_accepted_logs=len(valid),
                            accepted_events=sum(r['accepted'] for r in valid if r.get('accepted') is not None),
                            tried_events=sum(r['tried'] for r in fxs),
                            weighted_nwf=wf, unweighted_nwf=nf, fxfx_efficiency=fx,
                            dilution_approx=dil,
                            gen_wall_s_per_event=tm, log_span_s_per_event=span,
                            cost_wall_s_per_neff_approx=tm*dil if tm is not None and dil is not None else None,
                            jobs_weighted_nwf=nw, jobs_unweighted_nwf=nn, jobs_fxfx=len(fxs),
                            jobs_gen_wall=nt, jobs_log_span=ns,
                            parse_errors=sum(bool(r.get('parse_error')) for r in logs)))
    return individual, summary


def report_table(summary):
    lines = []
    lines.append('AQP FxFx pilot: 50,000 requested accepted events per configuration')
    lines.append('Aborted delta441 v2 tasks excluded; delta441 v3 = 1000/job, others v2 = 5000/job')
    lines.append('')
    hdr = (f"{'Sample':19} {'logs':>7} {'valid':>5} {'accepted':>9} "
           f"{'wNWF%':>7} {'uNWF%':>7} {'FxFx%':>7} {'dilut.':>8} "
           f"{'gen s/ev':>9} {'span s/ev':>10} {'cost s/N_eff':>12}")
    lines.append(hdr)
    lines.append('-'*len(hdr))
    for r in summary:
        sample = f"{r['process']}/{r['config']}"
        lines.append(f"{sample:19} {r['downloaded_logs']:>3}/{r['target_logs']:<3} "
                     f"{r['valid_accepted_logs']:>5} {r['accepted_events']:>9,} "
                     f"{fmt(r['weighted_nwf'],pct=True):>7} {fmt(r['unweighted_nwf'],pct=True):>7} "
                     f"{fmt(r['fxfx_efficiency'],pct=True):>7} {fmt(r['dilution_approx']):>8} "
                     f"{fmt(r['gen_wall_s_per_event'],3):>9} {fmt(r['log_span_s_per_event'],3):>10} "
                     f"{fmt(r['cost_wall_s_per_neff_approx'],3):>12}")
    lines.extend(['', 'METRIC COVERAGE (jobs with the necessary measured values):'])
    hdr2 = f"{'Sample':19} {'wNWF':>6} {'uNWF':>6} {'FxFx':>6} {'gen wall':>9} {'log span':>9} {'errors':>7}"
    lines.extend([hdr2, '-'*len(hdr2)])
    for r in summary:
        sample = f"{r['process']}/{r['config']}"
        lines.append(f"{sample:19} {r['jobs_weighted_nwf']:>6} {r['jobs_unweighted_nwf']:>6} "
                     f"{r['jobs_fxfx']:>6} {r['jobs_gen_wall']:>9} {r['jobs_log_span']:>9} {r['parse_errors']:>7}")
    lines.extend(['', 'INTERPRETATION:'])
    lines.append('  * wNWF uses absolute positive/negative WEIGHT sums (prefer for biased samples).')
    lines.append('  * uNWF uses counts of positive/negative weights (when present).')
    lines.append('  * FxFx = sum(nAccepted) / sum(nTried), not a mean of per-job percentages.')
    lines.append('  * gen s/ev requires explicitly identified generation wall time; NA = not found.')
    lines.append('  * span s/ev is a timestamp-span proxy, NOT certified CPU or generation time;')
    lines.append('    it is ambiguous for logs running 24h or longer.')
    lines.append('  * dilution and cost are approximations for equal-|weight| events; for biased')
    lines.append('    events exact N_eff requires sum(w^2) and complete event weights.')
    lines.append('  * Compare v2 vs v3 runtimes only after checking identical generation/shower scope')
    lines.append('    and CPU allocations. Missing metrics are NA, never inferred.')
    return '\n'.join(lines) + '\n'


def diagnose_zero_coverage(root, summary):
    """Show representative raw lines when counters cannot be parsed."""
    failed = [row for row in summary
              if row['downloaded_logs'] and not row['valid_accepted_logs']]
    if not failed:
        return
    print("\nPARSER DIAGNOSTICS (first downloaded log from each unparsed configuration)")
    print("-" * 78)
    pattern = re.compile(
        r"All included|nTried|nAccepted|nSelected|sumOf|negative.weights|"
        r"positive.weights|[Ee]vents (?:tried|selected|accepted)|"
        r"FxFx.*(?:eff|match)|Pythia8.*(?:statistic|accepted)", re.I)
    for row in failed:
        location = root / row['process'] / row['config'] / row['version']
        files = all_log_paths(location)
        if not files:
            continue
        first = files[0]
        print(f"\n{row['process']}/{row['config']}/{row['version']} : {first.name}")
        try:
            with first.open('rb') as handle:
                header = handle.read(512)
            print(f"  source gzip={header.startswith(bytes.fromhex('1f8b'))}  tar={tarfile.is_tarfile(first)}")
            if tarfile.is_tarfile(first):
                with tarfile.open(first, 'r:*') as archive:
                    members = [m.name for m in archive.getmembers() if m.isfile()]
                    print("  archive members: " + ", ".join(members[:8]))
            sample = load_log(first)
            print(f"  decoded length: {len(sample):,} chars")
            tried, selected, accepted = pythia_counts(sample)
            print(f"  parsed Pythia counters: tried={tried}, selected={selected}, accepted={accepted}")
            matches = [line.strip() for line in sample.splitlines() if pattern.search(line)]
            print(f"  relevant lines: {len(matches)}")
            for line in matches[-8:]:
                print("   ", line[:220])
            if not matches:
                for line in sample.splitlines()[:3]:
                    print("   RAW:", line[:220])
        except (OSError, ValueError, tarfile.TarError) as exc:
            print("  diagnostic failed:", exc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path, help='Path containing Zee/ and Wenu/ downloaded logs')
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    rows, summary = summarize(root)
    perlog_fields = ['process','config','version','filename','expected_events','parse_error',
                     'tried','selected','accepted','close_to_expected','sum_pos','abs_sum_neg',
                     'n_pos','n_neg','generation_wall_s','log_span_s']
    as_csv(root/'aqp_per_log.csv', rows, perlog_fields)
    as_csv(root/'aqp_summary.csv', summary, list(summary[0]))
    report = report_table(summary)
    (root/'aqp_results.txt').write_text(report, encoding='utf-8')
    print('\n' + report)
    diagnose_zero_coverage(root, summary)
    print(f"Saved: {root/'aqp_per_log.csv'}, {root/'aqp_summary.csv'}, {root/'aqp_results.txt'}")
    if not rows:
        print('WARNING: No logs found. Results are empty; check the Rucio DIDs and downloads.')


if __name__ == '__main__':
    main()
