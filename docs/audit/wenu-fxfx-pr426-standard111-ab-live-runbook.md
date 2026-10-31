# Standard111 FxFx PR426 before/after — technical smoke runbook

## Source physics and provenance

CERN PMG work item #252 (user screenshot): FxFx generator uses *inclusive* $k_T$ clustering in `passcuts_fxfx()`, while Pythia8 uses an *exclusive* $k_T$ jet-resolution criterion; old FxFx jobs can suppress close-by hard partons, notably `ΔR(j1,j2)<1` and boosted `pT(V)`. PR #426 corrects `Template/NLO/SubProcesses/cuts.f` in MG5_aMC, not `cluster.py`.

Upstream PR: https://github.com/mg5amcnlo/mg5amcnlo/pull/426 . Source patch utility: `scripts/aqp_prepare_fxfx_exclusive_kt_patch.py`. The old code and corrected code are both checked against the *generated* process's `SubProcesses/cuts.f`.

The pasted Wenu Standard111 legacy JO copies `dummy_fct.f` and `montecarlocounter_MINE.f`, **not** `cuts.f`; therefore it is the new-style **cuts.f handling** category in the PMG issue. These custom HT2 files **must remain unchanged**.

## Scope and implementation

- two complete JOs:
  - `joboptions/wenu_fxfx_pr426_ab/before/100005/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_before.py`
  - `joboptions/wenu_fxfx_pr426_ab/after/100005/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_after.py`
- They are identical except `FXFX_APPLY_PR426 = False/True` and the case label.
- Both start from fresh MG process `loop_sm-no_b_mass`, Wenu + 0,1,2 partons, Standard111, with identical `HT2` custom functions and PDF 325100; `ickkw=3`, `ptj=8` GeV, `jetradius=1`, `event_norm=bias`, `req_acc=0.1`.
- Both do **direct LHE generation** via `generate(grid_pack=False)`, no old gridpacks and no inherited integrations. `run_mode=2, nb_core=16` inside an outer Condor job, so **this does not validate our internal Condor backend fix**.
- The `after` job inserts PR426 into freshly generated `SubProcesses/cuts.f` **before** `generate()`; the `before` job confirms the original stock cuts. The installed MG template and original Wenu JO remain unchanged.
- The runner produces TXT/LHE, NOT a physical Pythia shower. Showering of produced LHE and physics comparisons come **after** successful generation smoke tests.
- Each direct-LHE JOB uses `--maxEvents 40` for 200 LHE or `--maxEvents 10000` for 50k LHE, using `nevents = 5 * runArgs.maxEvents`, as in the original JO. This distinction is intentional.

## Preflight and 200-LHE smoke

Run **on the UChicago login node** (does not launch MG until submission):

```bash
cd /home/aalida/AQP/aqp-production-audit
git pull --ff-only

source /cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase/user/atlasLocalSetup.sh
asetup AthGeneration,23.6.63

python3 -m unittest discover -s tests -p 'test_aqp_fxfx_exclusive_kt_patch.py' -v
python3 -m unittest discover -s tests -p 'test_aqp_wenu_fxfx_pr426_ab.py' -v
bash scripts/stage_wenu_fxfx_pr426_ab.sh
```

Require `AQP_FXFX_PR426_AB_STAGE_PASS`. The source code comparison script refuses unknown/partly patched `cuts.f`. If missing old custom Fortran sidecar, **stop** and correct staging, not physics.

**Submit smoke only once:**

```bash
condor_submit condor/wenu_fxfx_pr426_smoke200.submit
```

The submit file queues exactly 2 independent 16-core jobs (before and after, same random seed 311), using the original HT2 Fortran files from
`/home/aalida/AQP/Wjets/WENU/standard111/100000/`. Runtime output:
`/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_ab/smoke200_{before,after}_seed311/`.

Check results:

```bash
BASE=/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_ab
for CASE in before after; do
  DIR="$BASE/smoke200_${CASE}_seed311"
  echo "===== $CASE ====="
  cat "$DIR/runner_exit_code"
  grep -E 'AQP_FXFX_AB_(CASE|PR426_ENABLED|BASELINE_CUTS_SHA256|ACTIVE_CUTS_SHA256|REQUESTED_LHE)' "$DIR/log.generate" | tail -20
done
```

If job failure occurs, inspect `Gen_tf.log`, `log.generate`, Condor `.aqp_staged/fxfx_pr426_ab/logs/`, and `atlas_setup.log` before any resubmission. A missing output path is not permission to resubmit ambiguous submissions blindly.

## Extended test (not yet approved)

After both smoke runners exit 0 and 200 complete LHE events are confirmed, the runner permits the 50k comparison using `condor/wenu_fxfx_pr426_benchmark50k.submit`. The two jobs are same except patch flag, seed 411, no gridpack packaging.

**Caution:** `req_acc=0.1` is for functional integration/generation, not a precision cross-section comparison. For a quantitative physics comparison with reliable uncertainties, reduce the target integration error if this run has excessive numerical error, and verify final per-bin effective statistics. Do not claim the patch should yield exactly 15–20% on this sample.

## Differential study after generation

Shower old/new samples with identical Pythia8 A14 / FxFx `nJetMax=2`, `qCut=20`, fixed shower configuration and matched event-count targets, compare `ΔR(j1,j2)` and `ΔR(b,b)` (where relevant) versus `pT(W)`. Our Wenu final state does not have a mandatory pair of heavy-flavor b jets, so `ΔR(b,b)` should be shown only on appropriately selected events, not treated as a primary channel observable. Include cross section and weights, total tried/accepted counts, and per-bin weighted errors.

**Status:** A/B source/JOs/Condor runner are committed; no A/B live jobs have been submitted from this conversation. Source-variant validation and compilation must run in AF environment.
