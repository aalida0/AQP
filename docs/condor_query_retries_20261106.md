# Condor-query reliability fix for AQP gridpacks

**Scope:** The original site-local `.condor/cluster.py` has a single-shot
`_aqp_query` that raises on any Condor error. Wenu standard111 DSID 200000
failed on 2026-11-06 with `Condor query error: 1 Failed to receive remote ad.`
This is a Condor backend issue, not evidence of invalid Wenu physics.

This branch provides a guarded installer for a retry-enabled backend. It
requires the original `.condor/cluster.py` to match the production launcher
pinned SHA256 and updates the launcher pin to the new content SHA256. No
JobOptions, matrix-element code, integration results, or working directories
are changed. All existing MadGraph processes retain their already-imported
code and **are not retroactively repaired**.

Run at UChicago AF from the correct host with AthGeneration configured:

```bash
cd ~/NWR
git fetch origin
git switch --track origin/fix/aqp-condor-query-retries-20261106
setupATLAS
asetup 23.6.63,AthGeneration

python3 -m unittest discover -s tests -p 'test_condor_query_retries.py' -v
python3 scripts/install_condor_query_retries.py --check
python3 scripts/install_condor_query_retries.py --apply
python3 -m py_compile .condor/cluster.py
git diff --check
git diff -- scripts/gridpack.sh
```

The installer backs up `.condor/cluster.py` and `scripts/gridpack.sh`
under `.condor/backups/retry-v4-<UTC timestamp>`. It does **not** save the
1.7-GB failed work directory; preserve that separately.

The updated `_aqp_query` performs up to five attempts, waiting
1, 2, 4, 8 seconds before retries, for transient network/Condor contact
errors. A persistent error still fails. Exit status 0 with a harmless
stderr warning is accepted, while `_aqp_states` continues to strictly
verify job IDs, states, and `condor_history` exit code 0.

The install modifies the *local* launcher `scripts/gridpack.sh` so that
its SHA pin matches the newly patched site-local candidate. Do not replace
this pin with a wildcard or disable the check. Review and commit the
local launcher change on this branch for reproducibility.

**To relaunch Wenu standard111 on a fresh workdir** after all checks pass:

```bash
bash scripts/gridpack.sh 'JOs/V+jets/W+jets/W(ev)/standard111/200000' 13000 20 200000
```

Do not re-launch inside or delete
`~/gridpack-work/W_ev_-standard111-200000.uJHHaf`. A MadGraph restart may
clean previous results; recovery must be investigated separately. Do not
interrupt or restart the seven V+jets integrations or WW already running.
