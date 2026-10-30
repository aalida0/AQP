# Upstream HTCondor status-query regression: latest release check (2026-10-30)

## Finding

**Not fixed in latest tagged release.** The official `mg5amcnlo/mg5amcnlo` tag `v3.8.1` has `VERSION`: `version = 3.8.1`, `date = 2026-10-09`. The latest development branch `3.x` reports the same version and has the same `madgraph/various/cluster.py` blob SHA (`0d2225a1438c98ee7ef26e6de1cbcad247fcabba`). No claimed newer release was found in this check.

The relevant `CondorCluster` methods continue reading `status.stderr.read()` and branching on `status.returncode` **without calling `wait()`, `poll()`, or `communicate()` first**. Python's `subprocess.Popen.returncode` can remain `None` after a process exits until one of those methods has collected its exit status.

| Version/ref | VERSION date | Status-query defect | Submission generic retry |
| --- | --- | --- | --- |
| ATLAS 3.5.11.atlas13-dbd05 | installed | confirmed by user mock against installed source | present |
| upstream v3.6.7 | 2026-01-05 | present | present |
| upstream v3.7.1 | 2026-04-29 | present | present |
| upstream **v3.8.1** | **2026-10-09** | **present** | **present** |
| upstream `3.x` (checked 2026-10-30) | 2026-10-09 | present; source identical to v3.8.1 | present |

In v3.8.1:
- [`control_one_job`, lines 1272–1286](https://github.com/mg5amcnlo/mg5amcnlo/blob/v3.8.1/madgraph/various/cluster.py#L1272-L1286): error handling checks uncollected `returncode`.
- [`control`, lines 1291–1337](https://github.com/mg5amcnlo/mg5amcnlo/blob/v3.8.1/madgraph/various/cluster.py#L1291-L1337): same, followed by missing-ID checks and possible `check_termination`.
- [`submit`, `submit2`, around lines 976 and 1102](https://github.com/mg5amcnlo/mg5amcnlo/blob/v3.8.1/madgraph/various/cluster.py): retry decorators still present.

## Evidence from UChicago

User's isolated failure mock against **the ATLAS-installed** 3.5.11 source (no live Condor calls):

```
control_one_job BUG_REPRODUCED_SUPPRESSED_QUERY_FAILURE mock_rc=42 result='' output_checks=0 warning=True
control BUG_REPRODUCED_FALSE_JOB_DISAPPEARANCE mock_rc=42 result=(0, 1, 0, 0) output_checks=1 warning=True
```

This demonstrates a genuine source-level failure mode, **not proof of the historical cause** of Wenu MINT1 duplicate jobs.

## Decision / scope

**Do not upgrade all generator software to address this bug; the newest release still contains it.** Prepare a narrowly scoped, reversible **isolated** 3.5.11 compatibility fix and regression suite; ensure a nonzero `condor_q` result fails closed before interpreting missing queue IDs. Also separately test status output completeness and ambiguous `condor_submit` acknowledgments, since an output-status fix alone does not make submission idempotent. Do not patch CVMFS, source process trees or production JOs until tested and explicitly approved.

PMG-approved HT2 bias, previously working Sudakov tolerance patch and deferred FxFx mismatch are out of scope.
