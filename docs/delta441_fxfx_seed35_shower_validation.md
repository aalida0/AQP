# Δ441 Wenu FxFx shower-only validation from preserved seed-35 LHE

## Scope and status

This is an **unexecuted, isolated validation test** on branch `dev/wjets-recovery`. It consumes the existing valid, 50-event seed-35 `events.lhe.gz` without loading, extracting, or running the recovered MG gridpack. Its purpose is to distinguish a Pythia8 crash caused by the TXT-only dummy-event configuration from any actual FxFx shower problem. A transform exit code 0 and EVNT output are necessary to claim the test passed.

Known input:
- `/data/aalida/AQP/Wjets/WENU/smoke_tests/delta441_backup/interactive_linkfix/seed35/events.lhe.gz`
- Source SHA256 `e94be1450418afa260a8d412febe09f08256658e4f3e4a28e1cbb5740cd152d8`
- Original LHE version 3.0; 50 opening `<event ...>` tags and 50 closing tags.
- 13 TeV Wenu + 0,1,2 partons, NLO FxFx MC@NLO-Δ, folding (4,4,1), HT2-biased generation, matrix-element PDF LHAPDF 325100.
- Pythia8 A14/NNPDF23LO/EvtGen fragments; FxFx nJetMax=2, qCut=20 GeV; matching hook `JetMatchingMadgraph`.

### Why this avoids the previous failure path

The seed-36 TXT-only transform successfully created its 50-event `delta441_smoke_seed36.TXT.tar.gz` archive before crashing on the transform's single dummy Pythia8 event at `Pythia8::MultipartonInteractions::pTnext`. Its logs had `SoftQCD:inelastic=on` alongside FxFx matching, which is suspicious but not conclusive. The new test uses `--inputGeneratorFile` and `--outputEVNTFile`, so the normal GENtoEVGEN skeleton showers actual LHE events; the JO does not call any MadGraphControl function. For an external hard-process LHE sample, the JO explicitly sets `SoftQCD:inelastic=off` (standard hard-process expectation). This is a diagnostic run only; retain source-level config and results for PMG review before production.

## Files

- `joboptions/fxfx_shower_seed35/100004/mc.aMCPy8EG_Wenu_FxFx_2jets_D441_shower.py`
- `scripts/run_delta441_fxfx_shower_seed35.sh`
- `condor/delta441_fxfx_shower_seed35.submit`

The JO's shortened `physicsShort` is <50 characters. `100004` is an internal smoke-test DSID, not an official assigned DSID.

## Deployment on the AF login node

```bash
cd /home/aalida/AQP/Wjets/WENU
mkdir -p shower_jo/100004 packaging_logs

curl -fsSL https://raw.githubusercontent.com/aalida0/AQP/dev/wjets-recovery/joboptions/fxfx_shower_seed35/100004/mc.aMCPy8EG_Wenu_FxFx_2jets_D441_shower.py -o shower_jo/100004/mc.aMCPy8EG_Wenu_FxFx_2jets_D441_shower.py
curl -fsSL https://raw.githubusercontent.com/aalida0/AQP/dev/wjets-recovery/scripts/run_delta441_fxfx_shower_seed35.sh -o run_delta441_fxfx_shower_seed35.sh
curl -fsSL https://raw.githubusercontent.com/aalida0/AQP/dev/wjets-recovery/condor/delta441_fxfx_shower_seed35.submit -o delta441_fxfx_shower_seed35.submit

chmod +x run_delta441_fxfx_shower_seed35.sh
python3 -m py_compile shower_jo/100004/mc.aMCPy8EG_Wenu_FxFx_2jets_D441_shower.py
bash -n run_delta441_fxfx_shower_seed35.sh

# Verify saved LHE and ensure the output directory is unused:
sha256sum /data/aalida/AQP/Wjets/WENU/smoke_tests/delta441_backup/interactive_linkfix/seed35/events.lhe.gz
test ! -e /data/aalida/AQP/Wjets/WENU/smoke_tests/delta441_backup/seed35_fxfx_showeronly_run01

condor_submit -interactive delta441_fxfx_shower_seed35.submit
```

Once an interactive worker shell is allocated:

```bash
cd "$_CONDOR_SCRATCH_DIR"
ls -l 100004/ run_delta441_fxfx_shower_seed35.sh
bash ./run_delta441_fxfx_shower_seed35.sh
```

For unattended batch execution, submit the exact same submit file with `condor_submit delta441_fxfx_shower_seed35.submit`; the runner copies results to `/data` on exit.

## Validation after the run

```bash
OUT=/data/aalida/AQP/Wjets/WENU/smoke_tests/delta441_backup/seed35_fxfx_showeronly_run01
cat "$OUT/runner_exit_code"
grep -E 'AQP_FXFX_SHOWER|JetMatching|FxFx|Pythia8.*(ERROR|FATAL)|Segmentation fault|ERROR|FATAL|efficiency' "$OUT/log.generate" | tail -n 100
ls -lh "$OUT"
```

Interpretation:
- Exit 0 + nonzero `seed35_fxfx.EVNT.pool.root` + recorded `JetMatchingMadgraph`: initial shower validation passes for this tiny sample (not a statistical FxFx efficiency measurement).
- Pythia crash: inspect `log.generate`, especially first stack frames and Pythia's `SoftQCD` and FxFx settings; do not alter integration grids.
- "No matching input file" error: check that the worker has the locally decompressed `seed35_fxfx.events` and that legacy GENtoEVGEN resolves it as `events.lhe`.
- All results, including logs on failure, are retained in the fixed output directory; new tests should use a different directory rather than overwriting results.

Do not claim full production readiness from this 50-event smoke test alone. Run an adequate statistics test to measure real shower FxFx acceptance before 2M-event production.


## Confirmed live AF smoke result — 2026-10-22, worker c052

**Observed result: PASS for the five-event shower smoke test.** User ran `run_delta441_fxfx_shower_seed35.sh` on interactive worker `c052` (scratch `dir_5493`) and reported the retained output from

`/data/aalida/AQP/Wjets/WENU/smoke_tests/delta441_backup/seed35_fxfx_showeronly_run01/`.

Evidence from user-provided logs:
- `runner_exit_code` is **0**.
- `AQP_FXFX_SHOWER_ONLY_USING_INPUT_GENERATOR_FILE`, `AQP_FXFX_SHOWER_INPUT=seed35_fxfx.events`, and `AQP_FXFX_SHOWER_MADGRAPH_NOT_INVOKED` were recorded.
- Original ATLAS Pythia8 FxFx fragment loaded: `Pythia8_i/Pythia8_FxFx_A14mod.py`.
- `AQP_FXFX_SHOWER_CONFIGURATION=FxFx_2jets_qCut20_SoftQCDoff`.
- `Pythia8 INFO Adding user hook JetMatchingMadgraph.`
- Pythia settings displayed: `JetMatching:doFxFx=on`, `JetMatching:merge=on`, `JetMatching:nJetMax=2`, `JetMatching:qCut=20`, `JetMatching:qCutME=8`.
- `StreamEVGEN INFO Data output: seed35_fxfx.EVNT.pool.root`, a persistent 223 KB EVNT file written on /data.
- Pythia printed `Using FxFx cross section recipe: xs = 2.841e+05 / 1.100e+10`. This small-sample internal cross-section recipe must **not** be interpreted as a production cross section or matching efficiency.

Conclusions:
1. The reconstructed Delta441 MINT1 and subsequent MINT2, `collect_events`, 50-event LHE formation and ATLAS Pythia8 FxFx shower have **all been demonstrated independently**, without rebuilding the expensive gridpack.
2. The previous `Gen_tf --outputTXTFile` run produced an archive, but crashed in its **single Pythia8 dummy event** at `MultipartonInteractions::pTnext`. The successful real-LHE shower with `SoftQCD:inelastic=off` is evidence against an inherent defect in the Delta441 LHE events, but does **not establish root causality** of the dummy-event crash.
3. The successful shower test requested only **five events**, so it **does not measure statistically meaningful FxFx efficiency, signed-weight statistics or production throughput**. Verify EVNT content and accepted/generated event counts in jobReport and event metadata, then conduct a 100–1000-event validation before full Wenu production.
4. Protect persistent input/output files on /data, and structure future production to save LHE/TXT outputs even if showering fails. Keep the test JO separate from production JO until settings and normalization are reviewed.
