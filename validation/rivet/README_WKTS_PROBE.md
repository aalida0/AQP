# Isolated W+jets splitting-scale diagnosis (Rivet 4.1.2)

## Problem

The full AQP Wenu EVNT-to-Rivet pass failed on its first event in
`MC_WKTSPLITTINGS:LMODE=EL` with

`No projection 'MET' found for parent ...`.

The **published official Rivet implementation already declares**
`MissingMomentum()` as `MET`. Therefore a missing `declare` statement
in published source is **not** an established root cause. The installed
LCG/AthGeneration 4.1.2 plugin may behave differently; this probe is
a controlled way to distinguish that from an event or integration issue.

Source used as physics reference:
https://heprivet.org/analyses/MC_WKTSPLITTINGS/

## Scope of the workaround candidate

`AQP_WKTSPLITTINGS.cc` uses the same selection structure as the published
plugin, preserving the kT jets base-class histograms:

- W electron selection: `LMODE=EL`, lepton pT > 25 GeV,
  |eta| < 3.5, dressing dR = 0.2 unless `SCHEME=BARE`.
- Missing pT > 25 GeV and closest lepton+missing momentum mass
  constrained to 60–100 GeV around 80.4 GeV.
- Leptons are vetoed from jet inputs, kT jets R=0.6 default.
- `MC_KTSPLITTINGS_BASE` books and fills the splitting-scale histograms.

It uses dedicated `AQP_W_MET` and `AQP_W_LEPTONS` projection names to
avoid possible collisions and a **different plugin name**
`AQP_WKTSPLITTINGS` to avoid shadowing Rivet's official plugin.
This is **not yet validated against Rivet 4.1.2 on AF**.

## One-file worker smoke test

On UChicago AF:

```bash
cd ~/AQP
git pull --ff-only origin study/vjets-final-shape-audit-20261118
python3 -m unittest discover -s validation/rivet -p 'test_wkts_probe_contract.py' -v

mkdir -p /home/aalida/AQP/validation/rivet/condor_logs
chmod +x validation/rivet/aqp_wkts_smoke.sh
cd validation/rivet
condor_submit aqp_wkts_smoke.sub
```

The job first runs **official `MC_WKTSPLITTINGS:LMODE=EL` alone**, 
on ONE existing Wenu D441 EVNT file, to check whether the problem was
interference from the other analyses. If that works, the official plugin
is preferred and the alternative plugin is **not** compiled or run.
If it fails, the job builds the alternative plugin against the **same
AthGeneration,23.6.63 environment** used for EVNT processing and tests
it on the same file.

The control and optional workaround outputs are isolated at:

```
/home/aalida/AQP/validation/rivet/condor_logs/wkts_smoke.<cluster>.out
/data/aalida/AQP_Rivet_full/outputs/_wkts_probe/MC_WKTSPLITTINGS_Wenu_delta441_isolated.yoda.gz
/data/aalida/AQP_Rivet_full/outputs/_wkts_probe/AQP_WKTSPLITTINGS_Wenu_delta441_smoke.yoda.gz
```

Check the job exit status and search stdout for **either**
`AQP_WKTS_OFFICIAL_ISOLATED_PASS=` or `AQP_WKTS_SMOKE_PASS=`.
If only the official control passes, run the official routine in a
**separate, dedicated Rivet pass**, not alongside the other Wenu analyses.
Do not run full production before one of these tests passes.
If it fails, report the exact `RIVET_BUILD`, `ATHENA_WKTS` error and the
first `FATAL` line. Do not equate output-file existence with physics
validation. The smoke script refuses to overwrite an existing test YODA.

The submit file sets `should_transfer_files = YES` because setting
it to `NO` causes HTCondor to append an **implicit**
`TARGET.FileSystemDomain == MY.FileSystemDomain` restriction, leaving no
eligible AF slots. The YODA file is still written directly under `/data`;
HTCondor stdout/stderr/event logs remain in `/home`.

If job `4303695.0` was already queued with the previous submit file,
remove that **single idle job** and submit again. Changing the file on
disk does not change a job already in the queue.

No `set -e`, `set -u`, `pipefail`, Condor logs on Ceph, or
explicit `FileSystemDomain` requirements are used.

## Condor HOME environment failure (18 November)

A previous smoke run (cluster `4303695` successor) showed

```text
AQP_WKTS_OFFICIAL_ISOLATED_FAILED exit=2
ERROR source not found: /cvmfs/sft.cern.ch/lcg/releases/gcc/.../AQP_WKTSPLITTINGS.cc
```

This is **not a physics-plugin result**. The source directory was
stored in the generic Bash variable `BASE`; sourcing the ATLAS/LCG setup
overwrites that variable with the GCC toolchain path under CVMFS.
Merely setting `BASE` to an absolute path before `asetup` did not fix it.
The worker now sets `AQP_WKTS_SOURCE_DIR=/home/aalida/AQP/validation/rivet`
**after** `asetup` and uses this unique variable for JobOptions,
plugin source, and plugin build output. A regression test guards that order.

A later run (4303705) confirmed the previous fix was insufficient:
`ERROR ATHENA_JOBOPTIONS_MISSING=/cvmfs/.../gcc/.../aqp_wkts_smoke_evnt.py`.
This was still a path failure **before** the official Rivet analysis
could be evaluated.

After pulling the fix, run the static test, then submit the single-file
probe once more. If the earlier attempt left either isolated-test YODA
file behind, **move it aside rather than delete it**, since the worker
deliberately refuses to overwrite any result. Read the full stdout/stderr
and distinguish an Athena JobOptions path failure from the original
`No projection 'MET'` exception before interpreting the result.

## Working plugin smoke on AF (cluster 4303710)

The official `MC_WKTSPLITTINGS:LMODE=EL` reproduces

```
MC_WKTSPLITTINGS:LMODE=EL::analyze method error:
No projection 'MET' found
AQP_WKTS_OFFICIAL_ISOLATED_FAILED exit=64
```

even when scheduled **alone** in an Athena/Rivet job. The isolated AQP
plugin builds, runs on the existing Wenu D441 EVNT file, and yields:

```
AQP_WKTS_SMOKE_PASS=/data/aalida/AQP_Rivet_full/outputs/_wkts_probe/AQP_WKTSPLITTINGS_Wenu_delta441_smoke.yoda.gz
```

This resolves the runtime blocker for a **custom-named** analysis. It
does **not** identify the exact defect in the official plugin or certify
physics-equivalent output. The published code and custom plugin both
call `MC_KTSPLITTINGS_BASE::init/analyze/finalize` and apply the same
lepton, missing-momentum, W-mass and kT-jet selections. The projection
names, declaration order, and `apply<MissingMomentum>` spelling differ.

Without rerunning Athena, check that the smoke YODA contains at least
one *populated* histogram, not just an object header:

```bash
cd /home/aalida/AQP
git pull --ff-only origin study/vjets-final-shape-audit-20261118
python3 -m unittest discover -s validation/rivet -p 'test_wkts_check_yoda.py' -v
python3 validation/rivet/aqp_wkts_check_yoda.py \
  /data/aalida/AQP_Rivet_full/outputs/_wkts_probe/AQP_WKTSPLITTINGS_Wenu_delta441_smoke.yoda.gz
```

The checker uses Python's standard library only (`gzip` and text
parsing); it does **not** require the `yoda` Python module or `asetup`.
Its parser recognizes histogram entry statistics in YODA V2 and V3
records, including `/RAW/` paths. It intentionally does not infer event
entries from scatter-only records. If the installed Rivet version writes
an unrecognized YODA object type, inspect the `BEGIN YODA_*` lines and
update the parser instead of treating an unparsed object as empty.

Expected `AQP_WKTS_YODA_POPULATED_PASS=N` for `N > 0`, and finite
`sumW` entries for the reported splitting histograms. Signed MC@NLO
weights mean a `sumW` can be negative; that is not automatically an
error. Empty histograms, zero event entries, and NaN/Inf are distinct
checks. This check is not a statistical shape comparison.

**Next production gate:** inspect a sample plot with the original YODA
binning using `mplhep.style.ATLAS`, and check a reference run/selection
on a few EVNT events before triggering the all-four-configuration
Wenu pass. Keep this routine named `AQP_WKTSPLITTINGS` and provenance
explicit; do not imply it is the unmodified official routine.

## Next diagnosis: isolate the MET projection key

The production JO smoke has **passed** for `AQP_WKTSPLITTINGS`, and the
raw YODA checker found **nine populated histograms**. The four
`log10_d_ij` distributions each have 579 entries in the sample,
whereas the `log10_R_i` histograms have different fill multiplicities.
The raw event-weight sums are very large in this biased sample and
are not validated cross sections.

The published `MC_WKTSPLITTINGS` source registers
`MissingMomentum()` with projection key `MET` and calls
`apply<MissingMom>(event,"MET")`. **`MissingMom` is a documented
alias of `MissingMomentum`**, not a distinct projection type; the
initial type-mismatch hypothesis was false.

The new `AQP_WKTSPLITTINGS_METKEY.cc` preserves the published
selection and declaration syntax, changing only the analysis name and
the projection key `MET -> AQP_W_MET`. This is a more controlled
diagnosis of the installed Rivet projection registration than the
earlier `AQP_WKTSPLITTINGS.cc` plugin, which also changed other
projection names and declaration order.

To test on **one existing Wenu D441 EVNT file**:

```bash
cd /home/aalida/AQP
git pull --ff-only origin study/vjets-final-shape-audit-20261118
python3 -m unittest discover -s validation/rivet -p 'test_wkts_probe_contract.py' -v
bash -n validation/rivet/aqp_wkts_metkey_probe.sh
chmod +x validation/rivet/aqp_wkts_metkey_probe.sh
cd validation/rivet
mkdir -p condor_logs
condor_submit aqp_wkts_metkey_probe.sub
```

Check `condor_logs/wkts_metkey.<cluster>.out` for
`AQP_WKTS_METKEY_PASS` or `ERROR METKEY_ATHENA`. If the test
passes, next compare the histogram bins in that YODA file with the
original `AQP_WKTSPLITTINGS` smoke file from the same EVNT input.
**Only if both match** should the minimally modified plugin replace
the exploratory implementation in all-config production.

The new smoke-test YODA output is versioned by a distinct filename
`_wkts_probe/AQP_WKTSPLITTINGS_METKEY_Wenu_delta441.yoda.gz`;
old outputs are never overwritten.

## Acceptance gates before replacing missing W+jets splitting plots

1. Plugin compiles against the actual Athena-compatible Rivet.
2. One-file smoke returns zero with splitting histograms in YODA.
3. Compare the plugin's cuts and at least one event-level histogram
   with the official Rivet code / expected W+jets behavior.
4. Only then add this *named custom routine* to a new versioned Rivet
   job suite and re-run it for all four Wenu configurations.
5. Preserve the original finished YODA and the official-plugin failure
   log for provenance. Do not label custom YODA paths as official without
   explaining the workaround.
