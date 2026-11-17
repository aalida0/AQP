#!/usr/bin/env python3
"""Build an isolated Wenu internal-Condor query fix from the pinned AF backend.

Do not modify .condor/cluster.py in place. Change only queue-status polling:
bounded query retries, at most 16 IDs per query. Never mark missing jobs done
without verifying their successful termination in Condor history.
"""
import argparse
import hashlib
from pathlib import Path

ORIGINAL_SHA256 = "ab60358a273531522835cd64c0f76acaca91faed1d426374ae8c04796ca4ef3c"

OLD_QUERY = """def _aqp_query(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ClusterManagmentError('Condor query failed: %s' % exc)
    if result.returncode != 0 or result.stderr.strip():
        raise ClusterManagmentError('Condor query error: %s %s' %
                                   (result.returncode, result.stderr.strip()))
    return [line.split() for line in result.stdout.splitlines() if line.strip()]
"""

NEW_QUERY = """def _aqp_query(args):
    # Retry transient scheduler/ClassAd errors; never infer completion.
    import time
    last_error = None
    for attempt in range(4):
        try:
            result = subprocess.run(args, capture_output=True, text=True,
                                    timeout=45)
        except (OSError, subprocess.TimeoutExpired) as exc:
            last_error = 'query failed: %s' % exc
        else:
            if result.returncode == 0 and not result.stderr.strip():
                return [line.split() for line in result.stdout.splitlines()
                        if line.strip()]
            last_error = 'query returned %s: %s' % (
                result.returncode, result.stderr.strip())
        if attempt < 3:
            time.sleep(2 ** attempt)
    raise ClusterManagmentError('Condor query failed after 4 attempts: %s' %
                               last_error)

_aqp_query._wenu_query_v2 = True
"""

OLD_AGGREGATE = """    result = parse(_aqp_query(['condor_q'] + ids +
                              ['-af', 'ClusterId', 'ProcId', 'JobStatus']), set(ids))
"""

NEW_AGGREGATE = """    # Query bounded batches instead of hundreds of tracked job IDs at once.
    result = {}
    for offset in range(0, len(ids), 16):
        batch = ids[offset:offset + 16]
        rows = _aqp_query(['condor_q'] + batch +
                          ['-af', 'ClusterId', 'ProcId', 'JobStatus'])
        subset = parse(rows, set(batch))
        if set(result).intersection(subset):
            raise ClusterManagmentError('Repeated Condor job across query batches')
        result.update(subset)
"""


def patched_source(source):
    for marker in (OLD_QUERY, OLD_AGGREGATE):
        if source.count(marker) != 1:
            raise ValueError("Expected exactly one pinned Condor query block")
    result = source.replace(OLD_QUERY, NEW_QUERY, 1)
    result = result.replace(OLD_AGGREGATE, NEW_AGGREGATE, 1)
    compile(result, "cluster.py", "exec")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    destination = args.destination.resolve(strict=False)
    if source == destination:
        parser.error("Refusing to modify pinned source in place")
    blob = source.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    if digest != ORIGINAL_SHA256:
        parser.error("Source-pinned Condor backend SHA256 mismatch: " + digest)
    modified = patched_source(blob.decode("utf-8"))
    if destination.exists():
        parser.error("Refusing to overwrite candidate: " + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(modified, encoding="utf-8")
    print("WENU_CONDOR_QUERY_V2_BUILT", destination)
    print("SOURCE_SHA256", digest)
    print("CANDIDATE_SHA256", hashlib.sha256(destination.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
