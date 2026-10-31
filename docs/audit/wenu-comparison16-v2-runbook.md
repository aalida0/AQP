# AQP Wenu comparison16 v2: runbook (2026-10-31)

**Scope:** generate fresh, comparable Wenu FxFx pilot samples from the *existing* Standard111, Delta111 and Delta221 gridpack archives without rerunning MINT0/MINT1 integration. Phase A generates 1,000 LHE (16 CPU local MG mode=2, existing gridpack) and then showers to 200 accepted EVNT per configuration. Phase B uses the same validated gridpack flow for 25,000 LHE and 5,000 EVNT. Delta441_cleaned_v1 is already validated separately (25k/5k).

**Why Phase A is necessary:** all three old generator wrapper logs exited code 8 after scheduler `condor_q` errors; recovered 1k LHE files are structurally valid and were successfully showered, but this only checks the showering path and does not exercise new gridpack event generation. The old failure mode was linked to Condor scheduler communication. The new workflow uses local MadGraph run_mode=2 in one Condor reservation and avoids MG-managed internal Condor queries. It still requires a valid *outer* HTCondor scheduler.

## Location and safety

- Canonical working branch: `audit/production-framework` (do not merge production changes to main until validated).
- Local checkout: `/home/aalida/AQP/aqp-production-audit`.
- Inputs: `/data/aalida/AQP/Wjets/WENU/gridpacks/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_{standard111,delta111,delta221}.MG3511.GRID.tar.gz`.
- Scripts: `scripts/run_wenu_comparison_16core_lhe.sh` and `scripts/run_wenu_comparison_16core_fxfx.sh`.
- Complete JOs: `joboptions/wenu_comparison16` and `joboptions/wenu_comparison16_shower`.
- Condor configs: `condor/wenu_comparison16_v2/{lhe.submit,shower.submit,smoke.dag,pilot25k.dag}`.
- The production runner extracts gridpacks **only in worker-local scratch**. It checks SHA256 against `.sha256` sidecars, verifies recovered checkpoint and matching/folding run-card settings, fixes known link issues **only in the scratch extraction**, and quarantines stale historical debug logs **only from the scratch extraction**. It never modifies the original gridpacks, process directories or existing recovered events.
- No DAG automatic retries; refuse existing output directories and do not resubmit on ambiguous Condor acknowledgment.
- Keep the independent recovered-LHE shower-only results separate from new full-generation pilot results.

## 1. Stage and run offline/static tests (no job submission)

On UChicago AF:

```bash
cd /home/aalida/AQP/aqp-production-audit
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_aqp_wenu_comparison16_v2.py' -v
bash scripts/stage_wenu_comparison_16core_v2.sh
```

Expect `AQP_WENU_COMPARISON16_V2_STAGING_PASS`. Inspect `.aqp_staged/wenu_compare16_v2/gridpack_inventory.txt`. A failure, including a missing `.sha256` sidecar, is a **stop condition**; do not blindly bypass the preflight or regenerate gridpacks.

## 2. Submit Phase A **once**

```bash
condor_submit_dag .aqp_staged/wenu_compare16_v2/smoke.dag
```

DAG nodes: standard/Delta111/Delta221, each 16-core 1k LHE followed by 1-core 200-EVNT shower. Seeds: 311 / 321 / 322. If submission reports failure or loses its ACK, check scheduler queue and DAGMan event logs before retrying.

Use `condor_q -nobatch`, `condor_history`, `.aqp_staged/wenu_compare16_v2/smoke.dag.*` and `.aqp_staged/wenu_compare16_v2/logs/` for scheduler diagnostics.

## 3. Evaluate Phase A without reruns

Output locations:

```text
/data/aalida/AQP/Wjets/WENU/production_pilot/wenu_compare/smoke16_1k/
  standard111_seed311_lhe/
  standard111_seed311_fxfx/
  delta111_seed321_lhe/
  delta111_seed321_fxfx/
  delta221_seed322_lhe/
  delta221_seed322_fxfx/
```

Check the gate:

```bash
python3 scripts/check_wenu_comparison16_v2_smokes.py
```

It requires each LHE wrapper exit 0, 1,000-event weight audit PASS, verified saved LHE, correct gridpack config/16-core markers, downstream shower exit 0, confirmed FxFx hook/no-MadGraph shower and 200 processed EVNT, plus nonempty EVNT file.

## 4. Phase B **only after 3/3 gate PASS**

```bash
condor_submit_dag .aqp_staged/wenu_compare16_v2/pilot25k.dag
```

Three 16-core 25,000-LHE jobs (seeds 411 / 421 / 422), each paired with a separate FxFx shower to 5,000 EVNT. The LHE production runner also refuses a Phase B run if its corresponding Phase A artifacts are not valid.

## 5. Physics deliverables after Phase B

Report per configuration: weighted NWF from positive/negative absolute LHE weight sums (HT2 bias), raw NWF, sign dilution `1/(1-2f)^2`, exact weighted effective statistics `(Σw)^2/Σw²`, FxFx accepted/tried efficiency, process cross section and its bookkeeping, total generation CPU and wall time, existing integration costs, and an end-to-end cost metric including matching inefficiency and dilution. Run separate Rivet comparisons at sufficient statistics.

**Do not publish smoke-derived 200-EVNT metadata NWF as full 5,000-EVNT production NWF.** Need a like-for-like comparison with Delta441 cleaned_v1. Also note the old recovered Delta221 `/data` LHE file hangs on reads; the gridpack path is different and its checksum is verified on worker scratch.
