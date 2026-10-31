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

## 2026-10-31 second AF submit policy: /data initialdir rejected

The transfer-based submit attempt returned:

```text
ERROR: Failed to commit job submission into the queue.
ERROR: Submitting jobs from /data is not permitted!
```

This is a distinct, AF-specific **submit-time** rejection caused by the
`initialdir=/data` in the previous Condor submit file, *not* a file
transfer or Pythia8 failure. HTCondor supports file-level
`transfer_output_remaps`; it should not be used to remap an entire output
directory. The corrected workflow uses:

```ini
initialdir = /home/aalida/AQP/aqp-production-audit/.aqp_staged/fxfx_pr426_shower/returned/before_accepted18000_seed13311
should_transfer_files = YES
transfer_output_files = shower_artifacts,wenu_pr426_before_accepted18000.EVNT.pool.root
transfer_output_remaps = "wenu_pr426_before_accepted18000.EVNT.pool.root = /data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_shower/before_accepted18000_seed13311/wenu_pr426_before_accepted18000.EVNT.pool.root"
```

The worker preserves the ROOT file in its top-level scratch directory;
HTCondor returns **small** `shower_artifacts/` diagnostics to `/home`
and remaps **only the large ROOT file** to `/data`. If the physics
shower fails before creating an EVNT, the worker creates a **zero-byte
placeholder** to let Condor transfer its diagnostics; never count such
an EVNT as produced, even if it appears in `/data`.

The old failed `condor_submit` already left a `/data` destination with
a single `stage_manifest.txt`. The updated staging script accepts
exactly that state (or an absent destination) but refuses any real data,
previous Condor outputs, or nonempty `/home` IWD. No deletion is needed.

From the **login terminal**:

```bash
cd ~/AQP/aqp-production-audit
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_aqp_wenu_fxfx_pr426_shower_transfer.py' -v
bash scripts/stage_wenu_fxfx_pr426_before_18000_transfer.sh
condor_submit -dry-run /tmp/wenu_pr426_shower.ad condor/wenu_fxfx_pr426_before_18000_shower.submit
condor_submit condor/wenu_fxfx_pr426_before_18000_shower.submit
```

Do not remove `/data/.../before_accepted18000_seed13311` because
it contains a valid preflight manifest. On job completion:

```bash
HOME_OUT=/home/aalida/AQP/aqp-production-audit/.aqp_staged/fxfx_pr426_shower/returned/before_accepted18000_seed13311/shower_artifacts
DATA_OUT=/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_shower/before_accepted18000_seed13311
cat "$HOME_OUT/runner_exit_code"
cat "$HOME_OUT/evnt_transfer_status.txt"
ls -lh "$DATA_OUT/wenu_pr426_before_accepted18000.EVNT.pool.root"
```

Require exit code `0`, EVNT transfer status `EVNT_NONEMPTY`,
and a nonzero-sized ROOT file before running the differential FxFx study.
The `/data` remap has not been live-tested on this AF and might be
subject to additional local policy; in that case inspect the scheduler
error, without repeating LHE/MadGraph generation.

## 2026-10-31 third AF submit policy: Ceph in transfer_input_files rejected

Second corrected submit attempt returned:

```text
ERROR: Failed to commit job submission into the queue.
ERROR: Submitting jobs with TransferInputFiles From Ceph is not permitted
```

This **supersedes the earlier direct Ceph input-transfer recipe** in
this runbook. The scheduler explicitly rejects
`transfer_input_files = /data/...`. It had not started any shower.

To eliminate both known AF submit-policy blockers and the untested
`/data` output remapping, the final revised submit file now has:

```ini
initialdir = /home/aalida/AQP/aqp-production-audit/.aqp_staged/fxfx_pr426_shower/returned/before_accepted18000_seed13311
executable = /bin/bash
arguments = run_wenu_fxfx_pr426_condor_transfer.sh before 18000 13311
should_transfer_files = YES
transfer_executable = False
transfer_input_files = source_50k_lhe.gz,source_50k_lhe.sha256,/home/aalida/AQP/aqp-production-audit/joboptions/wenu_fxfx_pr426_shower/100007,/home/aalida/AQP/aqp-production-audit/scripts/run_wenu_fxfx_pr426_condor_transfer.sh
transfer_output_files = shower_artifacts,wenu_pr426_before_accepted18000.EVNT.pool.root
```

**All paths HTCondor reads or writes on the submit side are NFS /home.
No Ceph appears in initialdir, transfer_input_files, or output remaps.**
Input to HTCondor is an ephemeral checksum-verified compressed LHE
copy in /home; the original compressed LHE on /data is never changed.

The heavy EVNT is temporarily transferred to /home only. After
a successful job with full diagnostics, execute the guarded
`scripts/finalize_wenu_fxfx_pr426_before_18000_transfer.sh`, which
checks source SHA256, Pythia FxFx hook/metadata, worker exit code,
and output ROOT SHA256. It copies the EVNT to /data, verifies the
copy, and removes only the temporary /home copies. The /home JO
and small logs are retained.

**Current commands on AF:**

```bash
cd ~/AQP/aqp-production-audit
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_aqp_wenu_fxfx_pr426_shower_transfer.py' -v
bash scripts/stage_wenu_fxfx_pr426_before_18000_transfer.sh

# The previous two errors were submit-time policy checks which -dry-run
# is NOT guaranteed to reproduce; actual submit is necessary.
condor_submit condor/wenu_fxfx_pr426_before_18000_shower.submit
```

Once the new job finishes and the output sandbox has transferred back:

```bash
cd ~/AQP/aqp-production-audit
bash scripts/finalize_wenu_fxfx_pr426_before_18000_transfer.sh
```

Temporary returned `/home` artifacts:

```text
/home/aalida/AQP/aqp-production-audit/.aqp_staged/fxfx_pr426_shower/returned/before_accepted18000_seed13311/
  source_50k_lhe.gz             # transient until successful finalization
  source_50k_lhe.sha256         # small record, retained
  shower_artifacts/             # logs, worker exit code, source checksum
  wenu_pr426_before_accepted18000.EVNT.pool.root  # transient
```

Final verified EVNT on `/data`:

```text
/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_shower/before_accepted18000_seed13311/
  wenu_pr426_before_accepted18000.EVNT.pool.root
  evnt.sha256
  finalize_status.txt
  stage_manifest.txt
```

**No physics sample may be used from the zero-byte placeholder** that
the worker can emit in failure cases. The finalizer requires worker
`runner_exit_code=0`, `EVNT_NONEMPTY`, nonempty ROOT file, and the
correct hash. If the next submit is still rejected by AF policy,
preserve the returned error and consult AF's current site documentation
or support; do not silently change site constraints or rerun
MadGraph integration.

Official AF storage overview: https://af.uchicago.edu/hardware
