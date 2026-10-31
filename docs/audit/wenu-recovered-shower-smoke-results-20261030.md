# Wenu shower-only smoke: 3/3 successful (2026-10-30)

## Scope and inputs

These are independent Pythia8 FxFx shower-only diagnostics of the **existing** recovered 1,000-event LHE archives (not new MadGraph generation, not physics-normalized 25k benchmarks). Sources:

- `standard111`: original `/home/aalida/AQP/Wjets/WENU/standard111/PROCNLO_loop_sm-no_b_mass_0/Events/run_01/events.lhe.gz`.
- `delta111`: corresponding original `/home/.../delta111/.../events.lhe.gz`.
- `delta221`: corresponding independent NFS `/home/.../delta221/.../events.lhe.gz`. **Do not read** the Ceph `/data/.../delta221/.../events.lhe.gz` copy; it previously hung during gzip inspection.
- `delta441_cleaned_v1` is **separately validated**, with 25,000 LHE / 5,000 FxFx EVNT using its own cleaned gridpack.

All three new jobs used the complete JOs at `joboptions/wenu_existing_lhe_shower/<cfg>/100004/`, `scripts/run_wenu_existing_lhe_shower.sh`, and `condor/wenu_existing_lhe_shower.submit`, committing original-input SHA-256 to `source_lhe.sha256` and 1,000-event LHE weight checks to `lhe_weight_audit.json`.

## Actual user-reported results

| Configuration | Runner exit | Athena processed events | EVNT size approx. | FxFx hook | Matching settings |
| --- | ---: | ---: | ---: | --- | --- |
| `standard111` | 0 | 200 | 6.5 MB | `JetMatchingMadgraph` present | doFxFx on, nJetMax 2, qCut 20 |
| `delta111` | 0 | 200 | 7.0 MB | present | same |
| `delta221` | 0 | 200 | 7.1 MB | present | same |

Common observed log markers:

```text
AQP_FXFX_SHOWER_ONLY_USING_INPUT_GENERATOR_FILE
AQP_FXFX_SHOWER_INPUT=recovered.events
AQP_FXFX_SHOWER_MADGRAPH_NOT_INVOKED
AQP_FXFX_SHOWER_CONFIGURATION=FxFx_2jets_qCut20_SoftQCDoff
Pythia8 INFO Adding user hook JetMatchingMadgraph.
JetMatching:doFxFx on
JetMatching:nJetMax 2
JetMatching:qCut 20
PerfMonMTSvc INFO Number of events processed: 200
```

Saved output directories:

```text
/data/aalida/AQP/Wjets/WENU/production_pilot/wenu_recovered_lhe_shower_v1/standard111/
/data/aalida/AQP/Wjets/WENU/production_pilot/wenu_recovered_lhe_shower_v1/delta111/
/data/aalida/AQP/Wjets/WENU/production_pilot/wenu_recovered_lhe_shower_v1/delta221/
```

**Conclusion:** the Pythia8 FxFx shower-only chain is operational for all three old Wenu samples; paired with the independently validated `delta441_cleaned_v1`, all four configurations have passed an LHE-to-EVNT test.

## What these tests do NOT establish

- Do **not** compute FxFx matching efficiency as 200/1000: the Gen_tf transform deliberately requested a maximum of 200 output events, and the Pythia attempted/accepted counters were **not supplied in this log excerpt**.
- No comparable production negative-weight fraction or cross-section has yet been extracted for the three old samples. `lhe_weight_audit.json` contains **nominal LHE sign diagnostics** that should be presented as pilot-only, not substituted for final FxFx/EVNT-weighted performance.
- `Number of events processed: 200` and nonempty EVNT confirm the requested output count, not a complete review of event record weights or differential physics performance.
- No new successful 16-core MadGraph production has yet been demonstrated for `standard111`, `delta111`, `delta221` using their gridpacks. Historical original generator wrappers exited 8 with `condor_q` communication/security errors.
- The MINT/Condor patched candidates remain isolated, not deployed. The shower-only jobs do not exercise this bugfix.

## Next physics step

1. Read each saved `lhe_weight_audit.json` for **raw count NWF**, **absolute-weighted NWF**, **dilution** (nominal LHE), and compare all three to the earlier cleaned Delta441 25k pilot *with different sample-size caveat*.
2. Identify `Pythia8` / FxFx **tried and accepted** event counters in the complete three saved `log.generate` files; compute acceptance only from the correct counters.
3. For a fair generation-cost comparison, run the previously staged independently gated `wenu_comparison16` process from gridpacks (1k LHE+200 EVNT smoke, then 25k LHE+5k EVNT per configuration) after preflights, **not** another integration.
4. Then compare cross sections and Rivet distributions against W+jets reference measurements/simulations.

Avoid unnecessary repetition of the successful 1000-LHE shower-only checks.


## Additional user-reported weight diagnostics (2026-10-30)

The three saved `lhe_weight_audit.json` files were summarized by the user:

| Configuration | LHE events | LHE raw NWF | LHE absolute-weighted NWF | LHE sign dilution `1/(1-2f)^2` |
| --- | ---: | ---: | ---: | ---: |
| `standard111` | 1000 | 29.90% | 24.88% | 3.9606 |
| `delta111` | 1000 | 25.90% | 26.39% | 4.4866 |
| `delta221` | 1000 | 19.00% | 17.61% | 2.3836 |

For reference, *a different, larger* `delta441_cleaned_v1` pilot (25,000 LHE) previously showed 18.36% raw, 18.07% weighted, and 2.4514 dilution. **Do not infer a ranking of delta221 vs delta441 from different statistics**, nor claim delta111 improves weight-sign dilution: in these old 1k LHEs it is *worse* than Standard111.

The complete 200-EVNT `log.generate` metadata `sumOfPosWeights` and `sumOfNegWeights` reported positive magnitudes:

| Configuration | `sumOfPosWeights` | `sumOfNegWeights` | Ratio `sumNeg/(sumPos+sumNeg)` |
| --- | ---: | ---: | ---: |
| `standard111` | 1.940799e7 | 2.283136e6 | 10.526% |
| `delta111` | 1.225215e7 | 1.893612e6 | 13.386% |
| `delta221` | 1.641397e7 | 1.091176e6 | 6.233% |

These are only **metadata-derived post-shower ratios**. Their physical interpretation as the post-FxFx weighted NWF depends on verifying the generator-metadata semantics and event-weight bookkeeping. They must not be conflated with the full 1,000-event LHE fractions. `sumOfPosWeightsNoFilter` and `sumOfNegWeightsNoFilter` equalled the corresponding reported sums in these three snippets; **this does not determine Pythia's FxFx matching rejection rate**. The excerpted grep yielded no attempted/accepted FxFx counters.

**Important statistical limit:** the sign-only proxy `D=1/(1-2f)^2` is not a complete effective-statistical-cost measure for unequal-magnitude HT2-biased weights; compute `N_eff=(sum_i w_i)^2 / sum_i w_i^2` (and appropriate post-FxFx weights) on a properly normalized comparable sample.

Next: inspect the full per-job Pythia8 final statistics, especially tried/accepted counts and veto counters, without rerunning the successful smokes. Then prepare an independent 1k-generation smoke from each existing verified gridpack, and 25k LHE / 5k EVNT matching benchmarks under the staged `wenu_comparison16` framework, **without** MINT0/MINT1 reintegration.
