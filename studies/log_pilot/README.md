# AQP: balanced FxFx log pilot

Compare **160 log.generate files** across Zee and Wenu. Run 10 logs for each v2 standard111/delta111/delta221 configuration (5,000 events/job), and 50 logs for each delta441 v3 configuration (1,000 events/job). Aborted delta441 v2 tasks are excluded. Main branch and production JOs are unchanged.

## Run

On lxplus or UChicago AF with authenticated ATLAS Rucio:

```bash
git fetch origin work/aqp-50k-log-comparison
git switch work/aqp-50k-log-comparison
setupATLAS
lsetup rucio
rucio whoami
bash studies/log_pilot/download_aqp_logs.sh /data/aalida/AQP/aqp_log_comparison
```

The downloader calls the analysis script and **prints the entire summary table** at the end; no separate analysis command is necessary. Files saved alongside the logs:

- `aqp_results.txt`: terminal summary including all eight configurations, dilution, generation times and metric coverage.
- `aqp_summary.csv`: aggregate results for each configuration.
- `aqp_per_log.csv`: individually parsed log counters.
- `aqp_50k_log_pilot.tar.gz`: archive containing sampled logs, manifests, and results.

To rerun analysis alone:

```bash
python3 studies/log_pilot/compare_aqp_logs.py /data/aalida/AQP/aqp_log_comparison
```

## Definitions / limitations

* Weighted NWF = absolute negative weight sum / total absolute weight sum, appropriate when generation bias causes nonunit weights.
* Unweighted NWF = negative event count / total event count (when logged).
* FxFx efficiency = sum(accepted) / sum(tried), never mean of job efficiencies.
* Dilution = 1/(1-2f)^2, an **equal absolute weight approximation**. For biased samples the exact effective sample size needs sum(w^2).
* Generation seconds/event is shown only when identifiable in logs; approximate log-timestamp span is reported separately.
* A v3 shower-only job and a v2 generation-plus-shower job must **not** be directly compared as equal-cost generation. Establish matching timing scope/CPU allocation first.
* Incomplete or unrecognized metric fields are printed as NA, never guessed.
* Sampling of a Rucio container may return incomplete jobs; actual coverage is shown, and raw manifests are retained.

Run offline checks with `python3 -m unittest discover -s studies/log_pilot -p 'test_*.py' -v`.
