# Wenu Standard111 FxFx PR426: terminal-driven internal Condor A/B

**Physics change under test:** upstream MG5_aMC PR #426, `passcuts_fxfx()`, inclusive to exclusive $k_T$ criterion. This is **not** the Condor backend patch. CERN PMG work item #252 notes that JOs overwriting `cuts.f` require special handling. The original Wenu Standard111 JO copies `dummy_fct.f` and `montecarlocounter_MINE.f` but not `cuts.f`.

Two identical full JOs, differing only in `FXFX_APPLY_PR426=False/True` and the provenance label:
`joboptions/wenu_fxfx_pr426_internal_condor/{before,after}/100006/*.py`.

Both use MG5_aMC 3.5.11.atlas13 via AthGeneration/23.6.63, direct LHE `generate(grid_pack=False)` with fresh integration, `req_acc=0.1`, Wenu+0,1,2j, Standard111, PDF 325100, Pythia8 shower deferred, same original custom Fortran, and **unmodified** MG `cluster.py`. Execution `run_mode=1`, `cluster_type=condor`, `cluster_size=100`, `nb_core=16` by default (optionally 32 on an allocated 32-CPU machine). The two cases use different working directories, and the patcher refuses unknown or already patched generated source. **The live codepath has not yet been tested.**

## Tradeoffs and risks

- Internal Condor may submit many GF subjobs and make progress without booking 16 cores in a single outer batch allocation; it is **not guaranteed faster** if the AF scheduler is congested.
- The original internal Condor code is known (from offline reproductions) to mishandle `condor_q` failure and ambiguous `condor_submit` acknowledgments. It is deliberately unchanged here for an identical physics A/B. If scheduler errors occur, **do not resubmit** until orphaned/duplicate child jobs have been reconciled; failed logs are not proof that children are absent.
- The launcher is terminal-attached. A lost SSH session can interrupt `Gen_tf.py` while Condor child jobs continue. Use `tmux` and check the local AF policy for running MadGraph's front-end, compilation and waiting on login nodes. Internal Condor offloads channel jobs but not every local step.
- Working directory is under `/home/aalida/AQP/fxfx_pr426_standard111_internal`, **not** Ceph `/data`, because NLO subprocesses must access the shared process tree. This uses NFS quota. Keep the two working directories until outputs and metadata are independently audited.
- Early 200-LHE tests are for compilation, integration, hook/log verification only. `req_acc=0.1` is too loose for final differential/normalization claims; the extended 50k run needs per-bin statistical and integration-uncertainty assessment. The 50k runner is gated on both 200 LHE runs, same seed 311, passing; use seed 411 for both extended runs.
- `event_norm=bias` alone does not mean HT2 bias is active; a historical `dummy_fct.f` example has `bias_wgt=1d0` active. Check file body and report correct bias semantics.

## Minimal commands (run inside tmux, on an AF-approved host)

```bash
cd /home/aalida/AQP/aqp-production-audit
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_aqp_wenu_fxfx_pr426_internal_condor.py' -v
python3 -m unittest discover -s tests -p 'test_aqp_fxfx_exclusive_kt_patch.py' -v

source /cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase/user/atlasLocalSetup.sh
asetup AthGeneration,23.6.63

python3 scripts/aqp_prepare_fxfx_exclusive_kt_patch.py \
  --source "$MADPATH/Template/NLO/SubProcesses/cuts.f" \
  | tail -n 4

# Run ONE version at a time; each run invokes MadGraph internal Condor.
bash scripts/run_wenu_fxfx_pr426_internal_condor.sh before 200 311
bash scripts/run_wenu_fxfx_pr426_internal_condor.sh after 200 311
```

Monitor in another terminal:

```bash
condor_q -nobatch
tail -f ~/AQP/fxfx_pr426_standard111_internal/before_200_seed311/Gen_tf.log
```

After both exit 0 and valid LHE archives are confirmed:

```bash
bash scripts/run_wenu_fxfx_pr426_internal_condor.sh before 50000 411
bash scripts/run_wenu_fxfx_pr426_internal_condor.sh after 50000 411
```

**Do not** launch the 50k until reviewing the 200-event `log.generate` files. The user may choose a tighter `req_acc` for publishable numerical comparisons; source/JO changes must then be made identically in both cases.

## What demonstrates the FxFx fix?

The correct before/after `AQP_FXFX_AB_ACTIVE_CUTS_SHA256` must differ, while `AQP_FXFX_AB_BASELINE_CUTS_SHA256` and all other inputs match. Both must compile and produce LHE. Shower using identical Pythia8 FxFx settings in a **separate** run. Compare `\Delta R(j_1,j_2)` distribution and binned `p_T(W)`, especially `\Delta R<1`, with weighted uncertainty estimates. Same random seed is not an event-by-event pairing guarantee.

References: https://github.com/mg5amcnlo/mg5amcnlo/pull/426 ; https://gitlab.cern.ch/atlas-physics/pmg/mcjoboptions/-/work_items/252


## 2026-10-31 update: local parallel compilation

MG5_aMC 3.5.11 has separate concurrency paths. `run_mode=1` delegates integration to HTCondor, while `nb_core` controls the local `P*` subprocess compilation pool via `cluster.MultiCore`. We set `nb_core` to environment-controlled `AQP_FXFX_AB_COMPILE_CORES` (16 by default; optional 32 only if allocated). The two JOs remain identical outside the FxFx patch flag/case label.

**Do not launch 16/32 compilation workers on a shared login/head node.** The updated runner rejects login/head hosts. Use the supplied `condor/wenu_fxfx_pr426_interactive16.submit` to obtain a 16-CPU interactive allocation, if the site supports internal Condor submissions from execute nodes. That nested-submission permission must be checked first.

Run from the login node:

```bash
cd /home/aalida/AQP/aqp-production-audit
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_aqp_wenu_fxfx_pr426_internal_condor.py' -v
condor_submit -interactive condor/wenu_fxfx_pr426_interactive16.submit
```

Then inside the allocated interactive shell:

```bash
hostname -s
condor_q -nobatch
cd /home/aalida/AQP/aqp-production-audit
source /cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase/user/atlasLocalSetup.sh
asetup AthGeneration,23.6.63
export AQP_FXFX_AB_COMPILE_CORES=16
bash scripts/run_wenu_fxfx_pr426_internal_condor.sh before 200 311
bash scripts/run_wenu_fxfx_pr426_internal_condor.sh after 200 311
```

Expect `Compiling on 16 cores`; integration afterward remains `run_mode=1` with the original unpatched internal Condor scheduler backend. The launcher now creates **new distinct directories** named `before_200_seed311_compile16` and `after_200_seed311_compile16`, preserving the earlier one-core attempt.

**Before interrupting the currently running serial attempt**, check whether it has already submitted integration channels (using its `Gen_tf.log`, `log.generate` and `condor_q`). If Condor child tasks exist, do not blindly restart: reconcile their state, as the original backend can suffer ambiguous scheduler responses. A new local JO does not alter an already running MadGraph process.

If the interactive worker cannot run `condor_q`/`condor_submit`, do **not** run 16 cores on the login node. Use an AF-approved multicore interactive host with scheduler access or an outer Condor batch workflow. A 16-core interactive allocation stays reserved even while waiting for independently scheduled child jobs, so performance/resource cost is not guaranteed to improve.

The 50k smoke gate checks that both `*_200_seed311_compile16/runner_exit_code` files are 0; only then launch 50k with the same compile-core count.


## 2026-10-31 correction: run directly from terminal; no nested Condor interactive

Nested scheduler submission from a Condor interactive job was not working for this user. Consequently, run the **MadGraph controller directly from a terminal on a host with Condor submit access**, with `run_mode=1`. The prior `condor_submit -interactive` recommendation is superseded.

The specific AF facility presentation (2025) states that shared login nodes permit **at most 4 CPU cores / 16 GB memory per user**. The 24-core setting is technically supported in the JO, but may **only** be used from a separate dedicated/authorized host with at least 24 usable CPUs and access to the Condor scheduler. Running a 24-core local compilation on login03 is outside the stated AF limits. Source: https://indico.cern.ch/event/1496325/contributions/6303179/attachments/3108793/5511601/Analysis%20Facility%20at%20UChicago.pdf

```bash
# Shared AF login03 / head04: at most four local compiling workers;
# internal Condor integration remains parallel on batch nodes.
export AQP_FXFX_AB_COMPILE_CORES=4
bash scripts/run_wenu_fxfx_pr426_internal_condor.sh before 200 311
bash scripts/run_wenu_fxfx_pr426_internal_condor.sh after 200 311
```

```bash
# ONLY on an approved 24-core host that permits MG internal HTCondor
# submissions directly from the controller terminal:
export AQP_FXFX_AB_COMPILE_CORES=24
bash scripts/run_wenu_fxfx_pr426_internal_condor.sh before 200 311
bash scripts/run_wenu_fxfx_pr426_internal_condor.sh after 200 311
```

The work directories carry `_compile4` or `_compile24`; both compare identical FxFx settings except PR426, and the original 1-core attempt remains untouched. `nb_core` affects local compilation; `run_mode=1` continues to schedule integration channels on HTCondor.

**If the old single-core run is still active:** check its `Gen_tf.log` and child Condor jobs before stopping. Do not resubmit the same run with the original scheduler backend without reconciling unknown/duplicate jobs. Once one A/B compilation test is stopped cleanly before internal Condor submissions, its results are not reusable as a passing 200-LHE smoke.
