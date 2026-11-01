# AQP minimal Condor patch — validated scope and deployment gates

**Status (2026-11-01): MINT0 worker validated; full FxFx production NOT approved.**

This document applies to the `aalida0/AQP` **experimental** smoke-test branch.
The frozen, two-file patch and tests live separately in
`validated/condor-mint0-20261101` (copied from `fix/minimal-condor`).
Do not merge the smoke-test helpers or generated process files into `main`.

## What was actually validated

| Validation | Observed result |
| --- | --- |
| Python unit/fault-injection tests | 21/21 PASS on UChicago AF |
| Source-pinned candidate output | SHA256 `2286e475b32323f1e391fb8e64af06fa8e41531abccd4d2c701b7746a22cc5bd` |
| Synthetic `submit2()` worker | HTCondor 4062219.0 PASS |
| Worker exits 17 | HTCondor 4062220.0: rejected, guard retained |
| Successful job with missing output | HTCondor 4062221.0: rejected, guard retained |
| Real FxFx 1-jet `ajob1` MINT0 | HTCondor 4062514.0 PASS; `GF1.0/log_MINT0.txt` and `GF1.0/results.dat` verified |
| Simultaneous jobs through one controller | PENDING two-worker pilot |
| Real MINT0->MINT1->MINT2 stage transitions | NOT TESTED |
| Full FxFx NLO integration and event generation | NOT TESTED |

A separate 56-job attempt (4062447–4062502) was accepted by HTCondor but
all jobs held with `HoldReasonCode=14, SubCode=2` because their `Initialdir`
was under **node-local `login03:/scratch`**, inaccessible to scheduler
`head04`. They were later removed with `condor_rm`; those holds do not
demonstrate integration correctness.

## Exact source and runtime contract

- Use `asetup 23.6.63,AthGeneration` on AF (GCC14 / Python 3.12).
- The pinned MadGraph `cluster.py` source SHA256 is
  `feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe`.
  An Athena setup selecting `atlas15-c33bd` / GCC15 is **not compatible**
  with this candidate, even though it may also report MadGraph version 3.5.11.
- Use candidate
  `~/AQP/aqp-condor-minimal/.aqp_staged/minimal_v2/cluster.py`, with SHA256
  `2286e475b32323f1e391fb8e64af06fa8e41531abccd4d2c701b7746a22cc5bd`.
- Never modify CVMFS or an existing production `PROCNLO_*` process.
- The bootstrap in `smoke/1jet/bootstrap/sitecustomize.py` is **experimental**.
  It loads the pinned backend without editing MadGraph installation files,
  and preserves the LCG `sitecustomize`. Verify it is active before any test.
- `cluster_nb_retry=0`: ambiguous submit acknowledgements and scheduler
  anomalies are **fail-closed**; no blind retry or duplicate submission.
- Give each independent process a new, persistent, writable
  `AQP_CONDOR_GUARD_DIR`. Never delete `*.intent` to bypass an error.
  A guard is deleted only after successful history and required-output checks.

## Filesystem policy on UChicago AF

**Do not launch Condor submissions from `/data`.**
`/scratch` on the login node is a local ext4 filesystem and is not
Condor's shared submit-side `Initialdir`. Neither path can be used for
the process working directory in this deployment.

For small pilot workers, use a **fresh process directory on shared NFS
`/home`**, where the real successful canary ran. Check the **personal**
home quota, not only the `df` report for the shared NFS export.
The old full process was approximately 694 MB; the selected subprocess
31 MB; the archived transfer input set about 140 MB per worker.

For full Wenu/Zee production, a scalable, submit-host-accessible staging
solution must be chosen and tested; the approximately 10 GB personal home
space reported by the user is **not** a green light for a large FxFx gridpack.
Do not adopt HTCondor `-spool` until output retrieval and reconciliation
have been implemented and separately validated.

## Two-real-worker pilot (one controller, two jobs)

No process generation and no 56-worker submission. Both workers are
copied from the *already compiled* original MadGraph MINT0 process in
`/scratch` using the archived input contract of job `4062447.0`.

In the existing AQP smoke worktree (on AF):

```bash
setupATLAS
asetup 23.6.63,AthGeneration
cd ~/AQP/aqp-condor-minimal
git pull --ff-only origin test/condor-fxfx-1jet-smoke

export AQP_CLUSTER_CANDIDATE="$PWD/.aqp_staged/minimal_v2/cluster.py"
export PYTHONPATH="$PWD/smoke/1jet/bootstrap:$(readlink -f "$MADPATH"):${PYTHONPATH:-}"

python3 -m py_compile smoke/1jet/one_real_worker.py
python3 -m unittest discover -s tests -p 'test_condor_minimal.py' -q
sha256sum "$MADPATH/madgraph/various/cluster.py" "$AQP_CLUSTER_CANDIDATE"

# Create TWO DIFFERENT fresh directories (does not submit anything).
python3 smoke/1jet/one_real_worker.py prepare
python3 smoke/1jet/one_real_worker.py prepare
```

Copy the two different `ONE_WORKER_STAGED` paths into `STAGE_A`
and `STAGE_B`. **Run once**:

```bash
STAGE_A="$HOME/AQP/condor-one-worker/mint0-REPLACE_A"
STAGE_B="$HOME/AQP/condor-one-worker/mint0-REPLACE_B"
python3 smoke/1jet/one_real_worker.py run "$STAGE_A" "$STAGE_B" \
  2>&1 | tee "$HOME/AQP/condor-two-worker-pilot.log"
```

The script refuses more than two workers, reuse of a stage, duplicate stage
paths and non-staged inputs. Two real `ajob1` jobs are submitted through
**one** `CondorCluster`, exercising `condor_q` with multiple IDs, partial
completion, history validation and per-worker guard cleanup.

**Required PASS:** `TWO_REAL_AJOB1_PASS`; two distinct submitted job IDs;
both `GF1.0/log_MINT0.txt` and `GF1.0/results.dat` nonempty in their
respective stage directories; both guard directories empty.

**On any error:** stop immediately. Do **not** rerun the command, release,
remove or resubmit workers blindly, or erase `jobid`/`*.intent`.
Use the saved job IDs and `condor_q`/`condor_history` to reconcile.

## Deployment decision

The pilot verifies concurrent MINT0 handling, **not** a production-ready
full FxFx run. Even after it passes, MINT stage transitions and production
filesystem/quota handling remain unvalidated. Freeze source hashes and use
a new isolated pilot process for any later full-workflow testing; never
retrofit the candidate into existing integration/gridpack directories.
