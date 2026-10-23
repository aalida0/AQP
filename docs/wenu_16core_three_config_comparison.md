# Wenu FxFx three-configuration comparison: staged rescue, 16-core smoke, then benchmark

**Prepared, NOT executed or submitted from ChatGPT.** Branch: `dev/wjets-recovery`. The 2026-10-23 Δ441 16-core pilot is the measured reference: 25,000 complete LHE, 5,000 EVNT, generation ~3h46m, LHE nominal abs-weight NWF ~0.18065, Pythia8 FxFx efficiency 41.1692%.

## Why audit before any further generation

The older `scripts/package_wjets_gridpacks.sh` packaged four archives, requiring `job_status.pkl` and a combined LHE for standard111/delta111/delta221. Packaging and MINT1 presence are NOT evidence that the archives can reliably run through `Gen_tf.py` under AthGeneration/23.6.63. Δ441 required fixing libc++ linkage, removing stale `madevent/*_debug.log` from an isolated scratch copy and avoiding a dummy-event FxFx hook in GENtoTXT.

The existing independent physics setups must not be conflated:

| Configuration | `mcatnlo_delta` | `folding` | Origin |
|---|---|---|---|
| standard111 | False | (1,1,1) | `gridpacks/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_standard111.MG3511.GRID.tar.gz` |
| delta111 | True | (1,1,1) | `gridpacks/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta111.MG3511.GRID.tar.gz` |
| delta221 | True | (2,2,1) | `gridpacks/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta221.MG3511.GRID.tar.gz` |
| delta441 | True | (4,4,1) | **already validated in separate pilot** |

### One-command stage and read-only inventory (AF login)

```bash
cd /home/aalida/AQP/Wjets/WENU
curl -fsSL https://raw.githubusercontent.com/aalida0/AQP/dev/wjets-recovery/scripts/stage_wenu_comparison_16core.sh \
  -o stage_wenu_comparison_16core.sh
bash stage_wenu_comparison_16core.sh
```

This downloads three **complete generation JOs**, three complete shower JOs, both batch runners, LHE audit, the inventory, two submit files, and two DAGs. It then runs `bash -n`, `python3 -m py_compile`, checks for pre-existing output paths and audits source `run_card.dat`/GF/checkpoint structures and archive names. It does **not** execute MG or recompute MINT0/MINT1. The full report is saved in `/home/aalida/AQP/Wjets/WENU/wenu_three_gridpack_inventory_20261023.txt`. The inventory does not unpack multi-GB archives or rehash them on the login node; each batch runner checks the archive's saved SHA256 checksum on a compute worker.

If the stage prints `AQP_WENU_ARCHIVE_INVENTORY_CONTAINS_BLOCKERS`, stop and inspect the report; no DAG submission. Passing inventory means **archive candidate only**, not fully validated. Full validation happens on the worker and by the dependent shower.

### Phase A: three independent 16-core smoke tests

Run only after the staging pass:

```bash
cd /home/aalida/AQP/Wjets/WENU
condor_submit_dag wenu_comparison_16core_smoke.dag
```

Each config gets 1,000 LHE using 16 CPU / 32 GB RAM / 90 GB scratch, then a 200-EVNT real Pythia8 FxFx shower using 1 CPU / 8 GB / 20 GB scratch.

| CFG | LHE seed | Shower seed |
|---|---:|---:|
| standard111 | 311 | 3311 |
| delta111 | 321 | 3321 |
| delta221 | 322 | 3322 |

The DAG has no automatic retries. Generation JOs refuse the fresh-process branch; they inspect the pre-existing archived run card **before changing any settings**, verifying intended delta, folding, FxFx, HT2 bias normalization, 13 TeV beams, and PDF ID 325100. Scratch copies get the proven link preflight and debug-log quarantine. Real physical LHE records are generated with MadGraph local `run_mode=2, nb_core=16` and preserved in `/data/aalida/AQP/Wjets/WENU/production_pilot/wenu_compare/smoke16_1k/`.

The shower job starts only when generation exits successfully and its LHE event-count and weight audit pass. It uses the matching config-specific shower JO and checks full FxFx Pythia8 hook plus 200 processed EVNT events.

Run progress:

```bash
condor_q -nobatch
# Attach to an active generation/shower node if desired:
condor_ssh_to_job <ClusterId.ProcId>
cd "$_CONDOR_SCRATCH_DIR"
tail -n 50 -F log.generate
```

After Phase A, inspect each output:

```bash
ROOT=/data/aalida/AQP/Wjets/WENU/production_pilot/wenu_compare/smoke16_1k
for pair in standard111:311 delta111:321 delta221:322; do
  cfg="${pair%:*}"; seed="${pair#*:}"
  echo "==== $cfg ===="
  cat "$ROOT/${cfg}_seed${seed}_lhe/runner_exit_code" 2>/dev/null || true
  cat "$ROOT/${cfg}_seed${seed}_fxfx/runner_exit_code" 2>/dev/null || true
  cat "$ROOT/${cfg}_seed${seed}_lhe/lhe_weight_audit.json" 2>/dev/null || true
  grep -E 'Pythia8 efficiency|Number of events processed:|Using FxFx' \
    "$ROOT/${cfg}_seed${seed}_fxfx/log.generate" 2>/dev/null | tail -n 8
done
```

All six exit codes must be zero, each LHE audit must be PASS with exactly 1,000 complete events, each EVNT must have 200 processed records and a nonzero ROOT output.

### Phase B: matched 16-core pilots (only after Phase A)

```bash
cd /home/aalida/AQP/Wjets/WENU
condor_submit_dag wenu_comparison_16core_25k_pilot.dag
```

The benchmark DAG requests 25,000 LHE and 5,000 EVNT per configuration, exactly matching the Δ441 sample sizes. Seeds: 411/421/422 for MadGraph, 3411/3421/3422 for showers. Its generation runner **refuses to start** unless the corresponding Phase A 1k LHE + 200 EVNT smoke stages finished with zero exit status, and the LHE audit JSON says PASS.

Each benchmark produces `lhe_weight_audit.json`, `Gen_tf.log`, `log.generate`, `jobReport.json`, `prmon.summary.generate.json`, the LHE TXT archive and EVNT root file under `.../production_pilot/wenu_compare/pilot16_25k/`.

### Comparison and caveats

Match the four configs by exact generator version, `ickkw=3`, FxFx `nJetMax=2` and `qCut=20`, HT2 bias, 13TeV, PDF 325100, 25k LHE, 5k EVNT, and CPU allocation 16. For each record the LHE unweighted and absolute-nominal-weight NWF, sign dilution approximation, MadGraph generation wall/CPU time, Pythia8 `accepted/tried` matching efficiency, and EVNT output sanity. **Do not mistake 5000/25000 for matching efficiency** or the LHE sign dilution for true `N_eff=(sum w)^2/sum w^2` of the showered/selected sample. Integration-grid creation cost should be tracked separately from amortized event generation.

The archived Wenu gridpacks and original process trees remain immutable. No scripts run MG from shared /data, and a script refuses to overwrite previous result directories. With unstable SSH, jobs remain ordinary HTCondor batches; the Condor DAG is not tied to SSH.
