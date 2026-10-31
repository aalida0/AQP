# Wenu Standard111 PR426: 50k LHE to 18k shower EVNT on AF Condor

## 2026-10-31 scheduling blocker

The first attempt (HTCondor job 4059847.0) cannot match execute nodes:

    TARGET.FileSystemDomain == MY.FileSystemDomain
    matched slots = 0 out of 147

The cause is `should_transfer_files = NO` in the old Condor submit
file. The Analysis Facility nodes shown by `condor_q -better-analyze`
do not advertise the same `FileSystemDomain` as the submission host.
Memory was not the decisive obstacle (11 slots satisfied 8 GB).

## Fix

The new submit file deliberately uses:

    should_transfer_files = YES
    when_to_transfer_output = ON_EXIT
    transfer_input_files = /data/.../source_50k_lhe.gz,/data/.../source_50k_lhe.sha256,/home/.../100007
    transfer_output_files = shower_artifacts
    initialdir = /data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_shower/before_accepted18000_seed13311

The executable is the new worker-only
`scripts/run_wenu_fxfx_pr426_condor_transfer.sh`. It uses only files
transferred to `_CONDOR_SCRATCH_DIR`, never tries to read shared
`/home` or `/data` on the execute machine, and calls
`Gen_tf.py --inputGeneratorFile=input.events` with the identical
Pythia8 FxFx shower-only JO as the successful 200-event smoke.
`transfer_output_files=shower_artifacts` returns the EVNT and
diagnostics to **/data on the submit side** through HTCondor.

## Commands on AF login03

Check job state and remove only the confirmed idle obsolete job:

```bash
condor_q 4059847.0 -af ClusterId ProcId JobStatus
condor_rm 4059847.0
```

Then update the branch and prepare the fresh output destination:

```bash
cd ~/AQP/aqp-production-audit
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_aqp_wenu_fxfx_pr426_shower_transfer.py' -v
python3 -m unittest discover -s tests -p 'test_aqp_wenu_fxfx_pr426_shower.py' -v
bash scripts/stage_wenu_fxfx_pr426_before_18000_transfer.sh
condor_submit condor/wenu_fxfx_pr426_before_18000_shower.submit
```

Expected output directory after job exit and transfer:

```text
/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_shower/
  before_accepted18000_seed13311/
    stage_manifest.txt
    shower_artifacts/
      wenu_pr426_before_accepted18000.EVNT.pool.root
      runner_exit_code
      Gen_tf_shower.log
      log.generate
      stages.log
      source_lhe.sha256
```

Monitor the new cluster ID returned from `condor_submit`:

```bash
condor_q <clusterid> -nobatch
condor_q <clusterid> -better-analyze
```

If the new job does not match, check scheduler policy, user priority,
and the remaining memory requirements. `should_transfer_files=YES`
removes the accidental `FileSystemDomain` restriction, but does not
guarantee immediate scheduling.

On a held or failed job, inspect the job's `.err/.out/.log` under
`~/AQP/aqp-production-audit/.aqp_staged/fxfx_pr426_shower/logs`
and any returned `shower_artifacts` before attempting a retry.
Do not delete the input LHE, the existing 200-event EVNT, or the
baseline MadGraph integration.

### Reference

HTCondor User Manual, *Submitting Jobs Without a Shared File System*:
https://htcondor.readthedocs.io/en/main/users-manual/file-transfer.html
