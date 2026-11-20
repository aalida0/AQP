#!/usr/bin/env python3
"""Compare exactly 10 valid Zee/Wenu FxFx generator logs per configuration.

Correct Wenu S111 v1 only. Never mix old wrong-seed Wenu S111 v2.
These are preliminary 10-job statistics, not full-2M event estimates.
"""
import argparse
import csv
import gzip
import math
import re
import tarfile
from pathlib import Path

FLOAT = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
# Exactly 10 logs per configuration. The corrected Wenu S111 is v1.
# Do not use Wenu standard111 v2: that is the wrong-seed sample.
PLAN = [(p, c,
         ('v1' if (p, c) == ('Wenu', 'standard111') else
          ('v3' if c == 'delta441' else 'v2')),
         10, 1000 if c == 'delta441' else 5000)
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


def pythia_reported_efficiency(text):
    """Pythia8's reported efficiency in percent, converted to [0,1]."""
    matches = re.findall(
        r'Pythia8 efficiency\s*\(\s*nAccepted\s*/\s*nTried\s*%\s*\)\s*=\s*('
        + FLOAT + r')', text, re.I)
    if not matches:
        return None
    value = float(matches[-1].replace('D', 'E').replace('d', 'e')) / 100
    return value if 0 < value <= 1 else None


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
        row['parse_error'] = 'Inconsistent Pythia counts'
    pos = last_number(text, ('sumOfPosWeights', 'sum[ _-]*of[ _-]*positive[ _-]*weights', 'sumPosWeights'))
    neg = last_number(text, ('sumOfNegWeights', 'sum[ _-]*of[ _-]*negative[ _-]*weights', 'sumNegWeights'))
    sqr = last_number(text, ('sumOfSqrWeights', 'sum[ _-]*of[ _-]*squared[ _-]*weights', 'sumWeightsSquared'))
    npos = last_number(text, ('nPosWeights', 'nPositiveWeights', 'nPosEvents'))
    nneg = last_number(text, ('nNegWeights', 'nNegativeWeights', 'nNegEvents'))
    eff = pythia_reported_efficiency(text)
    # Explicit counts supersede the printed rounded Pythia8 efficiency.
    if tried is not None and tried > 0 and accepted is not None:
        eff = accepted / tried
    row.update(tried=tried, selected=selected, accepted=accepted,
               sum_pos=pos if pos is not None and pos >= 0 else None,
               abs_sum_neg=abs(neg) if neg is not None else None,
               sum_sqr=sqr if sqr is not None and sqr > 0 else None,
               n_pos=npos if npos is not None and npos >= 0 else None,
               n_neg=nneg if nneg is not None and nneg >= 0 else None,
               fxfx_efficiency_reported=eff,
               generation_wall_s=explicit_seconds(text), log_span_s=timestamp_span(text),
               close_to_expected=(accepted is None or abs(accepted-events) <= max(5, 0.05*events)))
    return row


def ratio(a, b):
    return a/b if b and a is not None else None


def weighted_fraction(rows, positive, negative):
    good = [r for r in rows if r.get(positive) is not None and r.get(negative) is not None]
    a = sum(r[positive] for r in good)
    b = sum(r[negative] for r in good)
    return ratio(b, a+b), len(good)


def time_per_event(rows, key):
    """Use verified accepted counts only, not target events."""
    good = [r for r in rows if r.get(key) is not None and r.get('accepted') and r.get('close_to_expected')]
    return ratio(sum(r[key] for r in good), sum(r['accepted'] for r in good)), len(good)


def summarize_efficiency(rows):
    """Pool exact counters; otherwise estimate from rounded job-level efficiencies.

    For equal accepted counts per job, pooled accepted/tried is the HARMONIC
    mean of each job's accepted/tried. This fallback is marked an estimate,
    because the log does not confirm the accepted count.
    """
    with_eff = [r for r in rows if r.get('fxfx_efficiency_reported')]
    if not with_eff:
        return None, 'unavailable', 0
    all_explicit = all(r.get('tried') and r.get('accepted') is not None for r in with_eff)
    if all_explicit:
        return (ratio(sum(r['accepted'] for r in with_eff),
                      sum(r['tried'] for r in with_eff)),
                'pooled_counts', len(with_eff))
    if all(r.get('accepted') is None or r.get('accepted') == r['expected_events']
           for r in with_eff):
        # Equal-accepted-target approximation, not measured event counts.
        return (len(with_eff) / sum(1.0/r['fxfx_efficiency_reported'] for r in with_eff),
                'harmonic_mean_assumes_equal_accepted_counts', len(with_eff))
    # Mixed explicit accepted counts: cannot pool with only percentages.
    return (sum(r['fxfx_efficiency_reported'] for r in with_eff)/len(with_eff),
            'arithmetic_job_mean_not_pooled', len(with_eff))


def effective_events(rows):
    """Signed-weight N_eff using log metadata moments.

    Valid as a combined sample only if event weights from different jobs
    share a consistent normalization and cover the same accepted event set.
    """
    good = [r for r in rows if r.get('sum_pos') is not None
            and r.get('abs_sum_neg') is not None and r.get('sum_sqr')]
    if not good:
        return None, 0
    signed = sum(r['sum_pos'] - r['abs_sum_neg'] for r in good)
    sumsq = sum(r['sum_sqr'] for r in good)
    return ratio(signed*signed, sumsq), len(good)


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
        # Parse the available logs, select exactly 10 completed usable jobs.
        # Keep deterministic ordering for reproducibility. No v2 Wenu-S111 fallback.
        all_paths = all_log_paths(path)
        parsed = [parse_one(f, process, cfg, version, events) for f in all_paths]
        good = [r for r in parsed
                if not r.get('parse_error') and r.get('close_to_expected')
                and r.get('sum_pos') is not None and r.get('abs_sum_neg') is not None]
        logs = good[:target_jobs]
        individual.extend(logs)
        good = logs
        wf, nw = weighted_fraction(good, 'sum_pos', 'abs_sum_neg')
        nf, nn = weighted_fraction(good, 'n_pos', 'n_neg')
        fx, fxmethod, nfx = summarize_efficiency(good)
        neff, nneff = effective_events(good)
        tm, nt = time_per_event(good, 'generation_wall_s')
        span, ns = time_per_event(good, 'log_span_s')
        dil = 1/(1-2*wf)**2 if wf is not None and wf < 0.5 else None
        with_counts = [r for r in good if r.get('accepted') is not None]
        summary.append(dict(
            process=process, config=cfg, version=version,
            target_logs=target_jobs, downloaded_logs=len(logs),
            usable_logs=len(good),
            # Do not misrepresent requested accepted events as measured counts.
            accepted_events_measured=sum(r['accepted'] for r in with_counts),
            jobs_with_accepted_counts=len(with_counts),
            accepted_events_target=target_jobs * events,
            weighted_nwf=wf, unweighted_nwf=nf,
            fxfx_efficiency=fx, fxfx_method=fxmethod,
            neff_weight_moments=neff,
            dilution_approx=dil,
            gen_wall_s_per_event=tm, log_span_s_per_event=span,
            cost_wall_s_per_neff_approx=tm*dil if tm is not None and dil is not None else None,
            jobs_weighted_nwf=nw, jobs_unweighted_nwf=nn, jobs_fxfx=nfx,
            jobs_neff=nneff, jobs_gen_wall=nt, jobs_log_span=ns,
            parse_errors=sum(bool(r.get('parse_error')) for r in logs)))
    return individual, summary


def report_table(summary):
    lines = [
        'AQP FxFx 10-log pilot (10 generator logs per configuration; accepted-event totals differ for v2/v3)',
        'Wenu S111 corrected v1 only (wrong-seed v2 excluded); D441 v3: 1000/job; others: 5000/job',
        ''
    ]
    hdr = (f"{'Sample':19} {'logs':>7} {'usable':>6} {'wNWF%':>7} {'uNWF%':>7} "
           f"{'FxFx%':>8} {'D~':>8} {'N_eff(w)':>10} {'gen s/ev':>9}")
    lines.extend([hdr, '-'*len(hdr)])
    for r in summary:
        sample = f"{r['process']}/{r['config']}"
        eff_text = fmt(r['fxfx_efficiency'], pct=True)
        if r['fxfx_method'] == 'harmonic_mean_assumes_equal_accepted_counts':
            eff_text = '~' + eff_text
        elif r['fxfx_method'] == 'arithmetic_job_mean_not_pooled':
            eff_text = '*' + eff_text
        lines.append(
            f"{sample:19} {r['downloaded_logs']:>3}/{r['target_logs']:<3} "
            f"{r['usable_logs']:>6} "
            f"{fmt(r['weighted_nwf'],pct=True):>7} {fmt(r['unweighted_nwf'],pct=True):>7} "
            f"{eff_text:>8} {fmt(r['dilution_approx']):>8} "
            f"{fmt(r['neff_weight_moments'],1):>10} "
            f"{fmt(r['gen_wall_s_per_event'],3):>9}"
        )
    lines.extend(['', 'METRIC COVERAGE (jobs with the necessary measured values):'])
    hdr2 = (f"{'Sample':19} {'wNWF':>6} {'uNWF':>6} {'FxFx':>6} "
            f"{'N_eff':>6} {'counts':>7} {'gen wall':>9} {'errors':>7}")
    lines.extend([hdr2, '-'*len(hdr2)])
    for r in summary:
        sample = f"{r['process']}/{r['config']}"
        lines.append(f"{sample:19} {r['jobs_weighted_nwf']:>6} {r['jobs_unweighted_nwf']:>6} "
                     f"{r['jobs_fxfx']:>6} {r['jobs_neff']:>6} "
                     f"{r['jobs_with_accepted_counts']:>7} {r['jobs_gen_wall']:>9} "
                     f"{r['parse_errors']:>7}")
    lines.extend(['', 'INTERPRETATION:'])
    lines.append('  * wNWF = sum(abs(negative weights)) / sum(abs(all weights)), from MetaData.')
    lines.append('  * uNWF = number of negative events / total; NA if event-sign counts absent.')
    lines.append('  * FxFx%: pooled accepted/tried only if exact counts are logged.')
    lines.append('  * ~FxFx%: HARMONIC mean of reported job efficiencies, assuming all jobs')
    lines.append('    accepted the same target events. This is an estimate, NOT an exact count ratio.')
    lines.append('  * *FxFx%: arithmetic job mean if accepted counts differ; NOT pooled efficiency.')
    lines.append('  * N_eff(w) = [sum(pos)-sum(abs(neg))]^2 / sum(w^2) from MetaData.')
    lines.append('    Combining jobs assumes consistent weight normalization across jobs.')
    lines.append('  * D~ = 1/(1-2*wNWF)^2; equal-|weight| approximation,')
    lines.append('    NOT exact statistical dilution for biased samples.')
    lines.append('  * Accepted event targets are from the sampling plan, not verified counters.')
    lines.append('  * gen s/ev requires explicit generation time AND accepted counts; otherwise NA.')
    lines.append('  * v2 versus v3 timing is not comparable until ME/shower workload is aligned.')
    return '\n'.join(lines) + '\n'


def diagnose_zero_coverage(root, summary):
    """Show representative raw lines when counters cannot be parsed."""
    failed = [row for row in summary
              if row['downloaded_logs'] and not row['jobs_weighted_nwf']]
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
                     'sum_sqr','n_pos','n_neg','fxfx_efficiency_reported',
                     'generation_wall_s','log_span_s']
    as_csv(root/'aqp_per_log.csv', rows, perlog_fields)
    as_csv(root/'aqp_summary.csv', summary, list(summary[0]))
    report = report_table(summary)
    (root/'aqp_results.txt').write_text(report, encoding='utf-8')
    print('\n' + report)
    diagnose_zero_coverage(root, summary)
    print(f"Saved: {root/'aqp_per_log.csv'}, {root/'aqp_summary.csv'}, {root/'aqp_results.txt'}")
    for row in summary:
        if row['usable_logs'] < 10:
            print(f"WARNING: {row['process']}/{row['config']}/{row['version']} "
                  f"has only {row['usable_logs']}/10 valid logs; this is NOT a final 10-log result.")
    if not rows:
        print('WARNING: No logs found. Results are empty; check the Rucio DIDs and downloads.')


if __name__ == '__main__':
    main()
