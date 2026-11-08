# Zee/Wenu FxFx: eight tmux controllers and MadGraph internal Condor (10k pilot)

Development branch: `study/vjets-condor-20k-no-syst-20261108` (historical branch name; actual current target is **10,000 accepted EVNT events per configuration**).

**Total target: 80,000 accepted EVNT events, eight simultaneous tmux sessions.** No external `condor_submit` of whole `Gen_tf.py` jobs. Each tmux controller runs `Gen_tf.py` / Pythia8, and MadGraph uses `run_mode=1, cluster_type=condor` to delegate hard-event generation.

The eight existing gridpacks are reused; no reintegration or recompile is intended. The launcher requires explicit selection whenever multiple files match, and stores the resulting eight path mappings in a local manifest rather than Git. The experimental JOs retain nominal signed event weights, MC@NLO-Delta, HT2 bias, folding, FxFx, central PDF 325100 and `store_rwgt_info=True`, but suppress extra PDF and scale systematic variations. This is not an official PMG production.

## Map

| Process | Config | DSID | Seed | Target EVNT |
|---|---|---:|---:|---:|
| Zee | standard111 | 100000 | 481001 | 10000 |
| Zee | delta111 | 100001 | 481002 | 10000 |
| Zee | delta221 | 100002 | 481003 | 10000 |
| Zee | delta441 | 100003 | 481004 | 10000 |
| Wenu | standard111 | 200000 | 481101 | 10000 |
| Wenu | delta111 | 200001 | 481102 | 10000 |
| Wenu | delta221 | 200002 | 481103 | 10000 |
| Wenu | delta441 | 200003 | 481104 | 10000 |

## AF: preflight, smoke, launch

Run these commands from the **same approved AF controller host**; tmux sockets are host-local. Do not run eight resource-intensive controllers on a login node if site policy forbids this.

```bash
cd ~/NWR
git fetch origin
git switch study/vjets-condor-20k-no-syst-20261108

export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh"
asetup AthGeneration,23.6.63

# Condor patch/bootstrap from previous gridpack runs must exist:
# GP_PATCH_ROOT=/path/to/validated/.condor  (if not ~/NWR/.condor)
# A selection file is needed if multiple archives match one configuration.
# Select each exact gridpack interactively; unique candidates are preselected.
bash scripts/vjets_tmux_condor.sh --select
cat /data/$USER/AQP_Vjets_tmx_condor_10k/gridpacks.selected.tsv

bash scripts/vjets_tmux_condor.sh --check

# Test the internal Condor mode with 20 Wenu delta111 accepted EVNT events:
bash scripts/vjets_tmux_condor.sh --smoke
tmux -L aqp-vjets-condor10k attach -t aqp-wenu-delta111-smoke
# Detach with Ctrl-b then d.
condor_q "$USER"
cat /data/$USER/AQP_Vjets_tmx_condor_10k/smoke/Wenu/delta111/exit_code.txt

# ONLY after confirming internal Condor jobs actually ran and the smoke passed:
VJETS_CONFIRMED_SMOKE=1 bash scripts/vjets_tmux_condor.sh --start

tmux -L aqp-vjets-condor10k ls
bash scripts/vjets_tmux_condor.sh --status
condor_q "$USER"
```

The `--start` command launches all eight controllers without waiting for each one to finish. All run directories are unique; any existing work/output directory or tmux session prevents overwrite. It checks exactly one corresponding `2jets` gridpack per configuration. It uses the SHA-pinned MadGraph Condor bootstrap already required by `scripts/gridpack.sh`. Worker-specific environment files prevent sharing seeds, guard directories or DATAPATH between tmux sessions.

Expected main paths:
- Shared Condor workdir: `$HOME/aqp-vjets-tmux-condor/10k/{Zee,Wenu}/{config}/`
- Archive directory: `/data/$USER/AQP_Vjets_tmx_condor_10k/{Zee,Wenu}/{config}/`
- Logs: `run.log`, `exit_code.txt`, `timing.txt`; retained LHE `tmp_LHE_events.tar.gz` and EVNT after success. `gridpack.path` and `gridpack.stat` record the selected archive without reading its entire contents to compute SHA256 during pre-launch.
- Example: `tmux -L aqp-vjets-condor10k attach -t aqp-zee-standard111-10k`.
- Example: `tail -f "$HOME/aqp-vjets-tmux-condor/10k/Wenu/delta111/run.log"`.

**Important resource caveats:** The gridpacks are large, and each is extracted into shared `/home`; eight simultaneous extractions and 8 hard-process trees may exceed AF quotas. Check `df -h "$HOME"` and site policy. The original JOs request 10 times `--maxEvents` at the LHE stage, so each 10k EVNT controller requests 100k LHE events. Condor queue size and CPU-hours must be monitored; `cluster_size=100` is not a guaranteed global concurrency limit. The live bootstrap has only been validated for gridpack integration, **not yet for gridpack-consumption event mode**.

## Audit requirements

For each configuration record real EVNT event count, MadGraph LHE event count, unweighted NWF, HT2 absolute-weight NWF, `sumw`, `sumw2`, `Neff`, per-multiplicity negative fractions, FxFx tried/accepted counts, physical cross-section estimates and errors, Condor CPU-hours and controller wall time. Do not equate nominal signed weights with optional PDF/scale systematic weights. A tmux session or transform exit code of 0 alone does not establish physics validation.

## Duplicate gridpack candidates

The AF gridpack directory can contain original, `clean_v2`, and older `HT2bias` archives. The launcher matches only the current exact `_HT2_<config>` filename, intentionally excluding the differently named legacy `HT2bias` archive. If both original and `clean_v2` exist, choose only after checking file integrity, archived run/proc cards, and unwanted debug artifacts; never select one automatically merely because of its directory name. `--select` records the chosen absolute path for each configuration. `--check`, `--smoke` and `--start` verify the chosen paths still exist among the matching candidates. Delete or move no gridpacks.

## Recovery from the 2026-11-08 pre-tmux SHA256 stall

The original launcher computed `sha256sum "$pack"` **synchronously before launching tmux**. On slow shared `/data` filesystems, a large archive could block this step for a long time. A zero-byte `gridpack.sha256` and missing `session_env.sh` / `run.log` indicate an interrupted or blocked pre-launch; this is **not** an internal Condor failure. The fix avoids full gridpack hashing at launch and starts a persistent tmux shell before sending the worker command.

Safely stop the **specific** old `--smoke` launcher and its identified `sha256sum` child (do not kill unrelated `Gen_tf.py` processes). Before retrying, rename or archive only the incomplete `$HOME/aqp-vjets-tmux-condor/10k/smoke/Wenu/delta111` workdir and `/data/$USER/AQP_Vjets_tmx_condor_10k/smoke/Wenu/delta111` output directory. Then `git pull --ff-only` and rerun `--smoke`. The tmux session should appear promptly and show `Extracting ...` while decompressing the gridpack. Extraction still takes time, but it can now be monitored from tmux.
