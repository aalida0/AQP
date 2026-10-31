# Recovered Wenu LHE -> independent FxFx shower-only smoke (three configurations)

**Stage only, then explicitly submit once.** User's original `standard111`, `delta111` and `delta221` runs each left **1,000 complete LHE events** despite their original AthGeneration transforms exiting 8 after HTCondor `condor_q` connection/security failures. The `delta221` copy under `/data` blocked on reads, but the **independent `/home` NFS copy passed gzip integrity and had 1,000 open and closed events**.

These are **diagnostic recovered LHE samples**, not production-quality normalized statistics. We are checking Pythia8 FxFx compatibility and creating up to **200 accepted EVNT events** per input sample, not running MG generation and not measuring full production rates. Existing validated Delta441 `delta441_cleaned_v1` is a separate production reference (25,000 LHE / 5,000 EVNT).

## Files

- Three complete joboptions: `joboptions/wenu_existing_lhe_shower/{standard111,delta111,delta221}/100004/*.py`. They differ in provenance metadata and `AQP_WENU_SHOWER_CONFIG`. All have Pythia8 A14 NNPDF23LO, aMC@NLO shower interface, FxFx `nJetMax=2`, `qCut=20`, `SoftQCD:inelastic=off`.
- `scripts/run_wenu_existing_lhe_shower.sh`: executed only on an HTCondor worker with private scratch. Streams the original `/home` LHE to worker scratch, pins SHA, checks gzip, validates exactly 1,000 LHE events and finite nominal weights, then runs `Gen_tf.py --inputGeneratorFile=recovered.events --maxEvents=200 --outputEVNTFile=...`.
- `scripts/stage_wenu_existing_lhe_shower.sh`: **read-only preflight** of originals, checks compiled JOs/runner, writes **only** a SHA-256 manifest under audit checkout, does not submit.
- `condor/wenu_existing_lhe_shower.submit`: one cluster with three queue rows, **1 CPU per job**, no DAG retry, no auto resubmission; transferred JO and audit only (not gridpack).
- `tests/test_aqp_wenu_existing_lhe_shower.py`: offline syntax and provenance checks.

## One-time staging on UChicago AF (login03 or equivalent)

```bash
cd /home/aalida/AQP/aqp-production-audit
git pull --ff-only
python3 -m unittest discover \
  -s tests -p 'test_aqp_wenu_existing_lhe_shower.py' -v
bash scripts/stage_wenu_existing_lhe_shower.sh
cat .aqp_staged/wenu_existing_lhe_shower_v1/source_sha.txt
```

Expect exactly three lines `CONFIG, 64_HEX_DIGIT_SHA`, one per Standard111 / Delta111 / Delta221. **Stop** if any source cannot be read or the preflight fails.

Then, after reviewing the manifest and confirming no prior jobs from this stage were submitted:

```bash
condor_submit condor/wenu_existing_lhe_shower.submit
```

**Submit this once only.** Do not repeat after an ambiguous scheduler acknowledgment. First inspect the `.log/.out/.err` files and `condor_q` / `condor_history`. Do not interpret a failed queue query as proof a submitted job does not exist. If the machine or filesystem stalls, diagnose before retrying.

The worker refuses to use `/home` or `/data` for scratch and uses an atomic per-config output-directory claim to block concurrent duplicate execution. It never modifies the original LHE or generated process trees. If any result directory exists, no automatic retry is allowed.

## Result locations and completion criteria

```text
/data/aalida/AQP/Wjets/WENU/production_pilot/wenu_recovered_lhe_shower_v1/
  standard111/
  delta111/
  delta221/
```

Each contains `runner_exit_code`, `source_lhe.sha256`, `lhe_weight_audit.json`, `Gen_tf_shower.log`, `log.generate` and (when successful) an EVNT ROOT file.

Check:

```bash
ROOT=/data/aalida/AQP/Wjets/WENU/production_pilot/wenu_recovered_lhe_shower_v1
for cfg in standard111 delta111 delta221; do
  echo "=== $cfg ==="
  cat "$ROOT/$cfg/runner_exit_code" 2>/dev/null || echo "NOT FINISHED"
  grep -E 'AQP_FXFX_SHOWER|AQP_WENU_SHOWER|JetMatching|Number of events processed:|ERROR|FATAL' \
    "$ROOT/$cfg/log.generate" 2>/dev/null | tail -n 25 || true
  ls -lh "$ROOT/$cfg/"*.EVNT.pool.root 2>/dev/null || true
done
```

PASS requires wrapper exit 0, Pythia8 FxFx matching hook in log, no MadGraph invocation marker, and `Number of events processed: 200` plus nonempty EVNT output. These are isolated tests on old failed-generator-run samples, so do **not** mix their weight statistics with cleaned/fully successful new generation benchmarks.

## Why not existing comparison DAG?

The existing `wenu_comparison_16core_smoke.dag` intentionally regenerates **1000 LHE per configuration** using existing gridpacks, followed by showering. That remains the appropriate next step if a new successful generation is needed. This recovered-file shower-only smoke has a narrower purpose: **reuse existing LHE first** without any MadGraph calls.

## Known limits

- The source `events.lhe.gz` files came from transforms that exited 8. Event completeness does not certify their physical normalization, FxFx metadata or provenance; these are preflight checks and a smoke test.
- A shower pass does not establish the full cross section, CPU cost, or Rivet physics agreement.
- The `delta221` /data copy was observed to hang; this workflow avoids it by reading the verified /home copy.
- The old `condor_q` status and `condor_submit` retry bugs have only been fixed in isolated candidates, not applied to these old process backends. This pipeline avoids MadGraph entirely and uses HTCondor directly.
