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
