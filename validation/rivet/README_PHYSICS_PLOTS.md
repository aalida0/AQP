# AQP V+jets — physics-normalized Rivet plots (stage 1: preflight)

This development branch starts from the completed 2026-11-18 shape-audit
branch. It does not modify main, generator JOs, original YODA files, or
presentation plots.

## Why old four-way Rivet figures are not physical differential cross sections

The old Zee S111/D111/D221 and Wenu D111/D221 Rivet jobs set
\`Rivet_i.CrossSection = 1.0\` (a dummy 1 pb), while corrected Wenu S111 v1
and both D441 v3 jobs set \`CrossSection = 0.0\` to use the HepMC input
cross section if present. The four-way comparison therefore mixes
incompatible rate-normalization conventions.

The MG5 run card explicitly uses \`event_norm = "bias"\`. The signed
event weights must be propagated exactly: do not set them to ±1, and
never divide by the FxFx acceptance fraction again without establishing
how that efficiency is already represented in the generator XS.

The slides' unit-area plots are visual-only; they do not repair these
metadata or turn all differential rates into pb.

## Step 1. Audit eight already-merged YODA files (login node, read-only)

\`\`\`bash
cd ~/AQP
git fetch origin study/vjets-physical-normalization-20261123
git switch --track origin/study/vjets-physical-normalization-20261123

python3 -m unittest discover -s validation/rivet \
  -p 'test_vjets_physics_preflight.py' -v

python3 validation/rivet/aqp_vjets_physics_preflight.py \
  --out /data/aalida/AQP_Rivet_full/outputs/physics_preflight_20261123.json
\`\`\`

The script checks:
- All eight expected merged files and correct versions;
- finalized/RAW objects and common MC histogram overlap;
- presence and raw text of \`_XSEC\`, \`_EVTCOUNT\`, \`_SUMW\`,
  \`MC_XS\` and \`MC_WEIGHTS\` metadata (if written by this Rivet version).

**It deliberately does not interpret a generic cross-section metadata
number as a validated physical cross section.** Inspect the
\`metadata_blocks\` fields in the JSON and cross-check the production
log.generate and DAOD/EVNT generator metadata independently.

Old v2 Wenu standard111 is not an input to this workflow; only corrected
seed817263 Wenu standard111 v1 is included. Both D441 samples are v3.

## Step 2. Decide if re-finalization can recover rate histograms

Before reprocessing EVNT, inspect the RAW histograms and _XSEC for
a few pilot files. Rivet's \`rivet-merge -e\` is for statistically
equivalent jobs; it merges RAW histograms, re-runs \`finalize()\` and
reconstructs cross-section and event-sum normalization. This may
make it possible to correct the dummy 1 pb cross sections without
rerunning the full EVNT campaign, *once independently validated
physical generator cross sections are available*.

Do **not** combine samples from different folding choices in one merge.
Never stack Zee and Wenu into the same sample. Do not combine
old wrong-seed Wenu S111 v2 with corrected v1.

If data in RAW histograms or event metadata are missing or incompatible,
reprocess the existing EVNT with a consistent Rivet_i JobOptions and
real physical cross sections to a new, versioned output directory.
The prior full EVNT-to-Rivet workflow is in
\`validation/rivet/aqp_rivet_full_local.py\` of the 2026-11-18 full Rivet
bundle; don't overwrite or pretend the old merged YODA files were fixed.

Check that each physical XS and signed sum of weights is stable across
files for a given configuration, includes the correct FxFx treatment and
HT2 bias weights, and that independent samples predict consistent
physics cross sections within their MC uncertainties.

## Step 3. Complete missing analysis families

For four-way MG comparisons, the common MC family has already been
processed. Experimental ATLAS/CMS routines were run for only a subset
of configurations. Reprocess **only missing configurations/analyses**
from existing EVNT files rather than showering again. Use the exact
official Rivet analysis and reference data compatible with the sample's
final state, energy, lepton channel, and fiducial cuts. The Wenu CMS
2017 muon-only routine is not a valid electron-channel comparison.

The official \`MC_WKTSPLITTINGS\` on Rivet 4.1.2 currently fails on MET
projection registration. The custom plugin passed one-file YODA smoke
but has not yet passed an official-equivalence and complete-run check.
Keep it separate from *official* validated plots.

## Step 4. Plot corrected, independently certified YODA

When you have **eight independently validated physical merged YODA files**
and a documented normalization ledger, do **not** use
\`PLOT:NormalizeToIntegral=1\` for rate plots.

Example for Zee, substituting the ACTUAL validated file names under
\`$PHYS\` (these example paths DO NOT yet exist):

\`\`\`bash
PHYS=/data/aalida/AQP_Rivet_full/outputs/physical_v1
OUT=/data/aalida/AQP_Rivet_full/outputs/final_physics_plots_v1
rivet-mkhtml -o "$OUT/Zee/01_four_way_common_MC_shapes" \
  -m '^/(MC_ZJETS|MC_ZINC)/' \
  "$PHYS/Zee/standard111.yoda.gz:Title=MC@NLO, 111" \
  "$PHYS/Zee/delta111.yoda.gz:Title=MC@NLO-Delta, 111" \
  "$PHYS/Zee/delta221.yoda.gz:Title=MC@NLO-Delta, 221" \
  "$PHYS/Zee/delta441.yoda.gz:Title=MC@NLO-Delta, 441"
\`\`\`

Repeat for Wenu with \`MC_WJETS|MC_WINC\`, and plot experimental
analyses in dedicated Rivet galleries with native HEPData references.
Use the existing \`aqp_vjets_mplhep_plot.py\` wrapper on **the NEW
corrected Rivet-generated scripts** as a final styling-only pass,
preserving plot data and Rivet uncertainties.

Keep the original cross-section and uncertainty axis units correct.
Do not apply the presentation normalization script to physical plots.
No arbitrary ratios of integrated histograms or 1/2200 factors.

## Acceptance criteria (report/PMG note)

- XS provenance documented per sample (mg5 generate log or certified
  EVNT metadata; not 1 pb and not an unvalidated MC_XS output).
- Appropriate FxFx/HT2 bias nominal weight preserved event-by-event.
- Re-merged sample has complete and nonduplicated event statistics.
- Same physics normalization convention for S111/D111/D221/D441.
- Cross sections of alternate folding/matching setups physically
  compatible within calculated uncertainties; investigate outliers.
- Rivet histogram bins, errors and ratio panel are unchanged by styling.
- Comparison to data only where the sample matches the experiment's
  fiducial phase-space definition; reference uncertainties retained.

Reference: https://www.heprivet.org/tutorials/merging2/

## 2026-11-23: confirmed cross-section metadata, new discrepancy

The preflight found all eight inputs readable, with RAW and finalized
objects, _XSEC and _EVTCOUNT present. The artificial 1 pb values are
confirmed for all five old v2 files.

The other three merged cross sections are:
- Zee D441 v3: 2210.455 +/- 164.576 pb;
- corrected Wenu S111 v1: 21247.90 +/- 773.997 pb;
- Wenu D441 v3: 6831.097 +/- 1678.537 pb.

The Wenu D441/S111 ratio is ~0.322, even though both use the same
Rivet `CrossSection=0.0` metadata convention and have nearly identical
signed sums of weights (~1e11). This is an **independent additional
cross-section problem**, and it would be premature to use either number
as an independently certified physical rate.

### Next: localize the Wenu discrepancy before applying any XS override

On UChicago AF:

```bash
cd ~/AQP
git pull --ff-only origin study/vjets-physical-normalization-20261123

python3 -m unittest discover -s validation/rivet \
  -p 'test_vjets_xsec_per_file.py' -v

python3 validation/rivet/aqp_vjets_xsec_per_file.py --max-files 20
```

This scans the first 20 original per-file YODA inputs (or fewer if there
are fewer) for selected old/new samples; it prints their XSEC median,
range, merged XS, and sample size. Raw metadata and sample paths are
recorded in `/data/aalida/AQP_Rivet_full/outputs/xsec_per_file_pilot_20261123.json`.

- If Wenu D441 per-file XS clusters at **~6831 pb**, the discrepancy
  arose **before or during individual Rivet file processing**:
  compare generator `log.generate` cross sections / EVNT provenance.
- If the Wenu D441 per-file XS clusters at **~21248 pb**, but the
  merged XS is 6831 pb, investigate `rivet-merge -e` input handling,
  duplicate/missing files and signed-weight cross-section averaging.
- If the per-file XSECs vary considerably, examine outlier job IDs,
  generator seeds and per-file sumW. Increase --max-files or compute
  the full weighted average before diagnosing the merger.

The uncertainty on an individual effective event counter is not the
same as the uncertainty on the generator cross section; do not infer
that 1.98M events guarantee a precise or accurate cross section.

No XS override, renormalized rate plot, new EVNT generation or event
resimulation is authorized by this diagnostic script.

### 2026-11-23: first 20 YODA files and all-files diagnostic

The first 20 Wenu D441 v3 per-file YODA cross sections have
median **21721.48 pb** and range **18193.75–30327.89 pb**,
whereas the merged cross section is **6831.097 pb**. The first
20 corrected Wenu S111 v1 files have median **21213.43 pb** and
range **19537.83–24062.62 pb**, compared with **21247.90 pb**
in the merged sample. The first 20 Zee D441 files have median
**2216.52 pb**, but a 5506.26 pb outlier.

**Do not call this a merge bug yet.** The first 20 sorted files
were unrepresentative of the complete 1,984-file Wenu D441 sample.

The official Rivet merging tutorial describes the equivalent-merge
cross section as a **weighted mean of per-file cross sections**.
The exact weighting in the deployed Rivet 4.1.2 implementation
must be checked: an upstream Rivet issue specifically flags
event-count weighting versus sum-of-weights weighting for samples
with nonuniform event weights. The older diagnostic's
`sum(sumW)/sum(sumW/XS)` construction was a **harmonic proxy** and
must **not** be presented as the Rivet merging formula.

For the completed 1,984-file diagnostic, **1,982** files had a
positive, parseable XS and nonzero signed sum of weights.
The valid-file XS range is 8688.849–82124.980 pb and the median is
20901.370 pb, while the merged XS is only 6831.097 pb.

The first priority is to identify the **two excluded metadata records**,
check negative event-weight sums and compare the arithmetic XS averages
weighted by event count and signed sumW.

```bash
cd ~/AQP
git pull --ff-only origin study/vjets-physical-normalization-20261123

python3 validation/rivet/aqp_vjets_xsec_json_diagnose.py \
  /data/aalida/AQP_Rivet_full/outputs/wenu_d441_xsec_full_20261123.json
```

This reuses the saved JSON; it does not read or modify the YODA files.
Check `EXCLUDED_FILES`, the per-file `sumW` values,
`sumW_all_over_merged`, and the arithmetic XS estimates.

Then inspect the exact file set recorded by the Rivet merger to
distinguish anomalous inputs from a merger bookkeeping problem.
Physical cross sections must subsequently be cross-checked against
the original MG5/Pythia generation logs and HT2 bias treatment.
Do not apply arbitrary normalization corrections to plots.


### 2026-11-23: Wenu D441 invalid XS sentinel ROOT CAUSE

Out of 1984 original per-file YODA inputs, 1982 have positive cross
section and sumW. Two have XS=-1 pb and negative signed weight sums:

- job 001393: XS=-1 pb, sumW=-8267115.
- job 001701: XS=-1 pb, sumW=-1678280.

With all 1984, the original Wenu D441 merge has sumW=100429181665.
With only the other 1982, sumW=100439127060 and the effective-trials
XS is 21116.762525986065 pb. The two bad files contribute
(-8267115-1678280)/(-1)=9945395 spurious effective trials.

The actual merged XS is reproduced with high precision:

    good trials = 100439127060/21116.762525986065 = 4756369.58726
    bad trials  = 9945395
    reconstructed old XS = 100429181665/(4756369.58726+9945395)
                         = 6831.0971155 pb
    observed old XS = 6831.097 pb

This exactly explains the factor-of-three anomaly in the merged
cross section. The actual implementation's effective-trials
denominator is also visible in Rivet AnalysisHandler.cc
(sumw / xsec->val()). The earlier concern about the formula
being an unsupported approximation is resolved by this
numerical reconstruction.

A *guarded and non-destructive* remerge program has been added.
It excludes exactly the two offending YODA files, refuses any
other exclusions or a partial manifest, preserves all original
inputs, and writes its result in a separate output directory.
The corrected XS is provisional until independently checked
against the MG5/Pythia generator cross section.

Run on AF login node (dry run and unit tests):

    cd ~/AQP
    git pull --ff-only origin study/vjets-physical-normalization-20261123
    python3 -m unittest discover -s validation/rivet -p 'test_vjets_remerge_wenu_d441.py' -v
    python3 validation/rivet/aqp_vjets_remerge_wenu_d441.py

Expected: SELECTED=1982, EXCLUDED=2, EXPECTED_XSEC_PB~21116.76,
DRY_RUN_ONLY=YES.

Run actual merge on Condor (single job, 8 GB RAM):

    cd ~/AQP/validation/rivet
    mkdir -p /data/aalida/AQP_Rivet_full/outputs/physics_remerge_condor_logs
    condor_submit aqp_vjets_remerge_wenu_d441.sub

Condor log:
    /data/aalida/AQP_Rivet_full/outputs/physics_remerge_condor_logs/Wenu_D441.out

New, non-overwriting YODA:
    /data/aalida/AQP_Rivet_full/outputs/physics_remerge_Wenu_D441_validXS_20261123/Wenu_delta441_v3_exclude_invalidXS.yoda.gz

The new merge has 1,982,000 events, omitting 2,000 accepted events
(0.10%). Full inclusion could instead be restored by repairing
only the two copied YODA metadata values using *independently
validated* generator XS, not median XS. This validation does not
yet certify any physical-rate prediction.

The other five old v2 samples still have artificial XS=1 pb.
Their normalizations require independent generator XS
provenance before creating final report-scale differential rates.
