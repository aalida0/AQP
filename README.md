# FxFx production

One PMG-reviewable JobOption per configuration/DSID under `JOs/`, with its
Fortran sources and patches alongside it. The same JO builds a Condor
gridpack or consumes a gridpack for ATLAS Grid event generation.

## Gridpack smoke test (0,1 jets; accuracy 0.1)

Run on the UChicago Analysis Facility, from a fresh home checkout
(`~/NWR` is supported; the GitHub repository is still `aalida0/AQP`):

```bash
cd ~/NWR
setupATLAS
asetup 23.6.63,AthGeneration
python3 scripts/check_sample.py tests/1jet/999999
bash -n scripts/gridpack.sh
bash scripts/gridpack.sh tests/1jet/999999 13000 10 34123
```

The launcher checks a source-pinned Condor bootstrap at
`<checkout>/.condor/cluster.py` and
`<checkout>/.condor/bootstrap_v3/sitecustomize.py` before starting
anything. These are **local, ignored test assets**, not production
dependencies: copy the exact validated files from the old AF test
checkout, without changing them. You may override the folder using
`GP_PATCH_ROOT=/absolute/path`.

The tmux-launched run uses a unique shared `~/gridpack-work/` directory.
On success, the gridpack, logs, and elapsed/controller timing are saved to
`/data/$USER/gridpacks/`. It does not count remote Condor CPU-hours yet.
The test uses standard matching/folding 111 with no HT2 bias and applies
the FxFx exclusive-kT source patch before compilation. It is a **smoke
test only**, not a validated physics sample.

Production JOs, Grid submission automation and Rivet validation remain
separate stages. Do not move a live Condor work directory during a job.

## Archived gridpack to PMG weights to Pythia8 EVNT (experimental)

On **2026-11-01**, a 20-event ATLAS EVNT smoke test **passed** with
**AthGeneration/23.6.63**, reusing the existing Zee 0,1j FxFx integration
grids while recompiling the event-generation executables. The run used
the PMG Zee PDF and scale weight recipe; ROOT verified 20 EVNT entries.
This is a **technical smoke test**: it is not ATLAS production approval
or physics validation. The smoke gridpack has coarse accuracy (0.1).

For a 1000-event follow-up on the UChicago Analysis Facility:

    cd ~/NWR
    git switch test/gridpack-storage-cleanup
    git pull --ff-only
    setupATLAS
    asetup 23.6.63,AthGeneration
    python3 -m unittest discover -s tests -p 'test_zee*py' -v
    bash scripts/validate_zee1jet_gridpack.sh \
      /data/aalida/gridpacks/tests-1jet-999999/tests-1jet-999999.PIDu18/mc_13TeV.aMCPy8EG_Zee_FxFx_1jet_smoke.MG3511.GRID.tar.gz \
      1000 34130 --recompile

The wrapper stages an independent copy under ~/gridpack-validation/,
preserves the archived gridpack, checks the SHA-256 manifest, and validates
the EVNT CollectionTree count. It writes validation_summary.json and
validation_summary.log in the printed VALIDATION_DIR after successful
event generation and showering.

The previously successful 20-event run can be summarized without rerunning:

    python3 scripts/summarize_zee1jet_validation.py \
      ~/gridpack-validation/zee1jet.kvihmIXG \
      --json ~/gridpack-validation/zee1jet.kvihmIXG/validation_summary.json

**Statistics interpretation:** the LHE negative-weight fraction is
**pre-FxFx veto**. Weighted NWF uses the absolute nominal sums
(S_negative_abs / (S_positive_abs + S_negative_abs)); raw NWF uses
N_negative / N_total. Statistical dilution is 1/(1-2*f)^2.
Post-FxFx weighted NWF is extracted from ATLAS MetaData:
sumOfNegWeights / (sumOfPosWeights + sumOfNegWeights), with both
metadata sums representing positive magnitudes. This measures signed
nominal weights after showering, not the raw fraction of negative EVNT
events. The no-filter metadata sums distinguish generator filtering
from Pythia8 FxFx matching. FxFx efficiency needs Pythia8
tried/accepted counters;
do **not** estimate it using EVNT / all generated LHE events, since
the shower can stop reading the input as soon as enough EVNT events
have been accepted. Any unavailable counters are reported as unknown,
not invented. Validate the full PDF/scale weight inventory and physics
distributions before any production use.

### First quantitative 1000-event smoke outcome (2026-11-01)

Sample: Zee +0,1j NLO FxFx, standard MC@NLO matching, folding 111,
no HT2 bias, 13 TeV, coarse test integration accuracy 0.1.
From the retained summary (seed 34130):

- 5000 LHE: nominal weighted NWF 20.82%, dilution 2.936.
- 1000 EVNT: ATLAS nominal signed weight metadata
  sumOfPosWeights=4.847110e6 and sumOfNegWeights=9.927816e5;
  weighted NWF 17.00%, dilution 2.296.
- Matching-efficiency denominator: unknown from this log.
- LHE header: 163 weight IDs; central label MUR1.0_MUF1.0_PDF325100.
  Inventory, event-level weights, and distributions still require a
  dedicated systematic/physics validation.

The change in weighted NWF across stages is a **shower/selection** effect
in this sample, **not** evidence of MC@NLO-Delta improvement because
Delta matching is disabled. The 20.82% and 17.00% values also have
different event-selection populations; do not directly convert their
ratio into matching acceptance.
