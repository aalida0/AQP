# Wenu Standard111 FxFx PR426 A/B: reuse the 200-LHE grids for 50,000 LHE

## Incident and correctness (2026-10-31)

The **unpatched** Standard111 direct-LHE run at
`/home/aalida/AQP/fxfx_pr426_standard111_internal/before_200_seed311`
completed MadGraph integration and event generation:

- 300/300 integration jobs completed, followed by 78/78 event-generation jobs.
- MG reported **200 events generated** and wrote `Events/run_01/events.lhe.gz`.
- The AthGeneration 23.6.63 `arrange_output()` subsequently failed with
  `Did not find expected weight MUR1.0_MUF1.0_PDF325100`.
- Root cause: a `MADGRAPH_PDFSETTING` dict with empty PDF variation list
  still causes `get_expected_systematic_names` to require the nominal
  systematics weight, even though none were written. The fix is to set
  `MADGRAPH_PDFSETTING=None`, `my_MGC_instance.pdf_setting=None` and fix
  `lhaid=325100` in the run card; request `systematics_program=none`.
- The failed `arrange_output()` calls `gunzip -f` *before* the weight
  check. Therefore the original 200-LHE file is likely now the **plain**
  `Events/run_01/events.lhe`, **not** the `.lhe.gz` path printed earlier.
- `arrange_output(saveProcDir=False)` deletes the entire process tree upon
  success. Both new 200-LHE JOs must use **`saveProcDir=True`** to preserve
  NLO grids for event-only reuse. The earlier baseline survives because
  the transform failed *before* deletion. No original integration is rerun.

## Offline preflight (does not submit anything)

```bash
cd /home/aalida/AQP/aqp-production-audit
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_aqp_wenu_fxfx_pr426_grid_reuse.py' -v

BEFORE=/home/aalida/AQP/fxfx_pr426_standard111_internal/before_200_seed311
python3 scripts/check_wenu_fxfx_pr426_saved_grids.py before "$BEFORE"
bash scripts/run_wenu_fxfx_pr426_reuse_50k.sh before "$BEFORE" --check
```

A preflight PASS demands the intended baseline `SubProcesses/cuts.f`,
the correct FxFx Standard111 run card, `SubProcesses/job_status.pkl`,
at least one `GF*/mint_grids`, and a complete original **200-event** LHE
(plain or gzip). It **does not** require the old wrapper exit status 0:
the 200-event generation succeeded before the Athena exception.

**Do not remove, re-run, or re-extract the old baseline process**. Failure
of any preflight is an investigation stop condition, not permission to
redo integration.

## Corrected case, one fresh integration only

For new JOs in branch `audit/production-framework` the fixes are:
nominal-only systematics, central PDF 325100, and `saveProcDir=True`.
The **after** case gets the exact PR426 `cuts.f` change before compiling.
The Condor backend remains unmodified, `run_mode=1` internal Condor.

On AF login, `nb_core` is local compilation: use at most 4 by the site's
documented login policy. On a separate approved 16-CPU host that can
submit internal Condor jobs, set `AQP_FXFX_AB_COMPILE_CORES=16`; the JO
supports 16, but a nested `condor_submit -interactive` shell is **not**
scheduler-capable in the user's AF experience.

```bash
source /cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase/user/atlasLocalSetup.sh
asetup AthGeneration,23.6.63

# Login node: limit local subprocess compilation to 4 CPUs.
export AQP_FXFX_AB_COMPILE_CORES=4
bash scripts/run_wenu_fxfx_pr426_internal_condor.sh after 200 311
```

**Do not restart the before case.** The new corrected case will take one
full integration, then output its 200 LHE and preserve process and grids.
If it fails, inspect logs and active Condor children before retrying.

Check the corrected saved grids:

```bash
AFTER=/home/aalida/AQP/fxfx_pr426_standard111_internal/after_200_seed311_compile4
python3 scripts/check_wenu_fxfx_pr426_saved_grids.py after "$AFTER"
bash scripts/run_wenu_fxfx_pr426_reuse_50k.sh after "$AFTER" --check
```

## Only-generation 50k: reuse MINT grids, no re-compilation

MG5_aMC 3.5.11 code explicitly recognizes `--only_generation`
(`-o`) to load `SubProcesses/job_status.pkl` and skip the first two
integration stages; `--nocompile` (`-x`) skips recompilation.

The new runner uses:

```text
launch -f -c -p -o -x --name=run_pr426_50k_seed411
```

- `-c`: MadGraph internal Condor.
- `-p`: parton-only LHE, shower later.
- `-o`: reuse existing integration.
- `-x`: skip compilation when compiled executables are present.
- `--name`: distinct event output; does not overwrite `run_01`.

It creates an **exclusive** output folder, records original `run_card.dat`
as `run_card.before_50k.dat`, changes `nevents` to 50,000, random
seed to 411, disables systematics, and keeps the original integration
accuracy. On scheduler failure, do not automatically retry: the original
MadGraph internal Condor backend can mishandle ambiguous submissions.

After both preflights pass, run directly from a terminal/tmux session
where the internal Condor scheduler is available:

```bash
bash scripts/run_wenu_fxfx_pr426_reuse_50k.sh before "$BEFORE" --execute
bash scripts/run_wenu_fxfx_pr426_reuse_50k.sh after "$AFTER" --execute
```

Output per configuration:

```text
<WORK>/PROCNLO_loop_sm-no_b_mass_0/Events/run_pr426_50k_seed411/events.lhe.gz
<WORK>/only_generation_run_pr426_50k_seed411/aMCatNLO_only_generation.log
```

The runner verifies all 50,000 event tags and the LHE closing marker.
**These do not represent full physical FxFx samples yet**: run Pythia8
FxFx showering in a separate and identical configuration, then evaluate
weighted distributions including `ΔR(j1,j2)` in bins of `pT(W)`.

## Known caveats

- The baseline `before` was integrated using the original *nominal*
  PDF 325100 despite the incorrect systematics weight expectation. The
  corrected `after` JO fixes variation metadata, not the nominal
  matrix elements or FxFx cut except for PR426. Verify the cards/logs.
- `req_acc=0.1` is intentionally loose; confirm sufficient numerical
  accuracy and binwise effective statistics before quantitative claims.
- The biased cross section explicitly marked `DO NOT USE` is **not**
  a physical inclusive cross section.
- The 16-core request applies to **local compilation**; event-only
  generation with `-x` and integration via Condor does not require
  16 CPUs on the launching login node.
