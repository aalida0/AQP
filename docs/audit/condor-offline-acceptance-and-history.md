# Wenu Condor reliability: offline patch complete, historical event-log gate

## Confirmed 2026-10-30 results (UChicago)

- Seven bundled-backend patch tests passed (7/7).
- Pinned checks verified all four original Wenu `bin/internal/cluster.py` files have only timing instrumentation changes versus central ATLAS MG5 3.5.11.
- Four isolated combined (status + submission) candidates generated in a **temporary directory only**:

| Config | Candidate SHA256 |
| --- | --- |
| standard111 | `682075381f79c6ad027244a4a2157f6c21b1202ea561fbc40a8fc0d0383a4a2e` |
| delta111 | `b2879ef87fa4f1a4f70a79699b2db6c1025c0770c3828d704a6c19acb5d2d17a` |
| delta221 | `f17032fc4f814bcbff1b878d1f9192832a266f6f453b82827afe4140dc4c8263` |
| delta441_backup | `a1d0916e8c9a03b2825a87a781077cc85e4f7119cd2a310bc1b9532cefa791c2` |

- Source-extracted mocks on the **standard111 candidate** passed for both Condor status methods and both submission methods. In the mock, invalid scheduler query exits no longer trigger output checks; ambiguous submit acknowledgments no longer trigger automatic re-submission; nonzero submit exits are rejected.
- The actual `standard111` interface import resolved to `internal.cluster` and `internal.misc` from its bundled process.
- Three timing directories existed and were writable; the `delta441_backup` backend points to an older `delta441/aqp_condor_timing` directory and that path was missing or unwritable.
- **Original production processes, gridpacks and CVMFS were not modified.**

## Next read-only historical evidence check

The original timing instrumentation selects Condor event-log filenames of the form
`P2_...__GF7.0__step1.log` (one per subprocess channel and integration stage).
An HTCondor job's user log can distinguish:

- `000` SUBMIT, identifying **a newly submitted job ID**.
- `001` EXECUTE, which can recur for the **same job ID** after an eviction or restart.
- `004` EVICTED, `005` TERMINATED; there are also HOLD/ABORT events.

Thus **two distinct submission IDs in a single GF/stage log** support a duplicate-submission explanation, whereas multiple EXECUTE events for one ID alone do not. Missing logs or submit records are ambiguous and must not be interpreted as proof that only one submission occurred.

See the official HTCondor manual: https://htcondor.readthedocs.io/en/main/codes-other-values/job-event-log-codes.html and https://htcondor.readthedocs.io/en/main/man-pages/condor_history.html . `condor_history` generally preserves only the final state of a job; optional `-epochs` adds per-run records where enabled.

The new `scripts/aqp_audit_wenu_condor_eventlogs.py` is **read-only and offline**: it reads the per-GF timing log files and historical `GF*/log_MINT1.txt`, prints a summary of distinct submission IDs, repeat EXECUTE events, evictions, nonzero known exits and correlation with MINT1 bad-real markers. It does **not** run `condor_q`, `condor_history`, or any generator, and never changes existing files. Its results are not a grid-integrity certificate.

Run:

```bash
cd ~/AQP/aqp-production-audit
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_aqp_audit_wenu_condor_eventlogs.py' -v
python3 scripts/aqp_audit_wenu_condor_eventlogs.py \
   --base "$HOME/AQP/Wjets/WENU"
```

The test uses synthetic logs; report findings require inspection of the actual local files. For machine-readable output, add `--json`. **Do not blindly retry any historical GF channel.**

## Required release gates beyond the first fix

1. Reconcile missing/ambiguous submission IDs against live `condor_q`, terminal `condor_history` and per-GF durable outputs. A missing job from the active queue alone is insufficient evidence it is gone.
2. Prevent any two workers from writing to one (process, stage, GF) output directory; a submission attempt must have a durable unique identity and a safe reconciliation decision. A generic retry is unsafe.
3. Confirm the actual patched backend is importable from a **fresh disposable process**, and check timeout/error behavior without touching the original integrations.
4. Only after that, run a small **non-physics** live Condor pilot. Historic Wenu grids are not suitable as pilot input.
5. Keep the audit branch development/test utilities separate from the final minimal production code and JOs. Physics matching, PMG-approved HT2 and Sudakov tolerance are out of scope.

Current conclusion: **offline targeted bugfixes validated; not yet end-to-end operationally safe**.
