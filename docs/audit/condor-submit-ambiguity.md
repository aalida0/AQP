# MadGraph internal Condor submission: ambiguous acknowledgement (diagnostic)

The user's isolated source-pinned fix for condor_q status handling passed the mocked failure checks:
- `control_one_job FAIL_CLOSED` with rc=42 and no output-check calls.
- `control FAIL_CLOSED` with rc=42 and no output-check calls.
- Candidate checksum: `bbddb6eedd5c68be6070d3cbc8d3efff20d49851f7eb328932e81d3a8cddb6f9`.

**These results do not yet constitute an end-to-end integration acceptance test.**

## Separate risk: condor_submit

In MG5 3.5.11, `CondorCluster.submit()` and `submit2()` are decorated with `@multiple_try()`. They issue `condor_submit`, parse the printed cluster number, and throw if that number is missing. A generic retry may submit a *new* job even if the scheduler accepted the first submission but its acknowledgment was lost. A successfully parsed acknowledgment is also accepted without checking the subprocess return code.

This is a source-backed **potential** for duplicate/orphaned submissions, not proof that it produced the 26 historical MINT1 bad-real logs.

Run the source-pinned mock:

```bash
cd ~/AQP/aqp-production-audit
git pull --ff-only
MG=/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt
python3 scripts/aqp_condor_submit_mock.py --mg-root "$MG"
```

The script extracts only the two installed submission methods and installed retry decorator by Python AST, supplies entirely simulated subprocess responses, and skips all sleeping. It verifies the two scenarios:

1. Normal acknowledgment: one accepted mock submission and one tracked ID.
2. Lost first acknowledgment despite simulated scheduler acceptance: two mock submissions but only the second ID tracked.
3. Contradictory nonzero command exit plus parseable acknowledgment: source tracks ID without checking exit status.

**No live Condor calls, no MG integration, no production file writes.**

## Criteria for a future candidate fix

Treat submission and status queries differently:
- Transient **query** failures can be retried, but job disappearance can only be acted upon after a *successful, complete* scheduler query.
- An ambiguous **submission** result must not be automatically repeated without reconciliation with the scheduler, e.g. by a unique submission token, durable per-attempt state and a query that can find the previously accepted request.
- Recording a unique request identity and retrieving history should be designed together; disabling retries alone may prevent duplicates but can leave orphaned jobs.
- Any resubmission must guarantee that the previous worker cannot continue writing to the same stage/GF directory.
- Test all the above in an isolated mock before a single controlled pilot.

**Do not modify CVMFS, gridpacks or active process directories.** Keep HT² and the Sudakov patch accepted and FxFx mismatch deferred.
