# Delta441 Wenu 16-core production pilot (seed 237)

**Status: prepared, not yet submitted or executed.** Working branch `dev/wjets-recovery`.

## Scope

Use the previously validated clean gridpack **without reintegrating MINT0/MINT1**, using one 16-core HTCondor allocation and MadGraph's local multicore mode (`run_mode=2`, `nb_core=16`). The LHE stage uses the corrected GENtoTXT configuration with no FxFx matching hook attached to Athena's **nonphysical** dummy event. The second batch job reads real LHE records and showers them with Pythia8 FxFx.

| Stage | Job | Target | Resources |
|---|---|---|---|
| LHE | `delta441_pilot16_seed237_25k_lhe.submit` | 25,000 LHE records | 16 CPUs, 32 GB RAM, 90 GB worker-local scratch |
| SHOWER | `delta441_pilot16_seed237_5000evnt.submit` | 5,000 EVNT records | 1 CPU, 8 GB RAM, 20 GB scratch |

`Gen_tf --maxEvents=5000` in the LHE stage produces **25,000 LHE records** because the JobOption configures fivefold LHE oversampling. The FxFx shower stage requests 5,000 **processed EVNT events**. Pythia8 may attempt more LHE records due to matching vetoes; the ratio 5000/25000 must **not** be used as the matching efficiency. The full Pythia8 log is retained for actual matching statistics. If the 25k-event input is insufficient to yield 5k accepted EVNT records, the shower stage fails explicitly while preserving diagnostics.

### Prerequisites

The clean copy from the previously successful DAG must exist at:

`/data/aalida/AQP/Wjets/WENU/gridpacks/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441_cleaned_v1.MG3511.GRID.tar.gz`

The cleaning stage must have written its `cleaned_gridpack.sha256` and `prepare_exit_code=0`. No further cleaning or changes to integration grids are made by this pilot.

### Stage and submit from AF login

```bash
cd /home/aalida/AQP/Wjets/WENU
curl -fsSL https://raw.githubusercontent.com/aalida0/AQP/dev/wjets-recovery/scripts/stage_delta441_pilot16_seed237.sh \
  -o stage_delta441_pilot16_seed237.sh
bash stage_delta441_pilot16_seed237.sh
# Only proceed after AQP_DELTA441_PILOT16_STAGING_PASS
condor_submit_dag delta441_pilot16_seed237_25k_to_5k.dag
```

The staging script fetches all complete JOs, runner scripts, an LHE integrity/weight audit and the DAG configuration. It checks Python compilation, Bash syntax, successful source gridpack packaging and absence of previous outputs. If any check fails, do not submit. Keep the original backup and cleaned archive immutable.

### Output files

```text
/data/aalida/AQP/Wjets/WENU/production_pilot/
├── delta441_16cpu_seed237_25k_lhe/
│   ├── runner_exit_code
│   ├── Gen_tf.log
│   ├── log.generate
│   ├── jobReport.json
│   ├── prmon.summary.generate.json
│   ├── lhe_weight_audit.json
│   ├── delta441_clean_v1_seed237_25000lhe.TXT.tar.gz
│   ├── delta441_clean_v1_seed237_25000lhe.TXT.events
│   └── validated_LHE.events
└── delta441_seed237_fxfx_5000evnt/
    ├── runner_exit_code
    ├── Gen_tf_shower.log
    ├── log.generate
    ├── jobReport.json
    └── seed237_pilot.EVNT.pool.root
```

The LHE audit requires 25,000 complete event tags, a closing LHE tag and finite nominal XWGTUP weights. It reports raw sign count fraction, absolute-nominal-weight sign fraction, signed and absolute nominal weight sums and a dilution factor. This **does not yet establish the HT2-unbiased physical cross section** or sample statistical efficiency after matching.

### Monitor with unstable SSH

The 16-CPU job is an **ordinary batch allocation**; it survives SSH disconnections. It might queue longer than an 8-CPU job because sixteen cores must match on the same host.

```bash
condor_q -nobatch
condor_ssh_to_job <ClusterId.ProcId>
cd "$_CONDOR_SCRATCH_DIR"
tail -n 50 -F log.generate   # While LHE runs
# On a shower worker: tail -n 50 -F log.generate
```

After completion:

```bash
ROOT=/data/aalida/AQP/Wjets/WENU/production_pilot
GEN="$ROOT/delta441_16cpu_seed237_25k_lhe"
SHOWER="$ROOT/delta441_seed237_fxfx_5000evnt"
cat "$GEN/runner_exit_code" "$SHOWER/runner_exit_code"
cat "$GEN/lhe_weight_audit.json"
ls -lh "$GEN"/*.TXT.tar.gz "$SHOWER"/*.EVNT.pool.root
grep -E 'AQP_DELTA441|Using FxFx|Number of events processed:|JetMatching' "$SHOWER/log.generate" | tail -n 80
```

The DAG has `RETRY 0` to prevent accidental expensive regeneration. A failure in the LHE stage blocks SHOWER. Preserve the existing output; never resubmit unchanged into the same fixed output paths. If a wrapper-only failure occurs after LHE creation, validate the archived LHE independently and run a separate shower-only recovery job instead of regenerating MINT2.
