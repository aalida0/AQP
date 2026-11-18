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

The job compiles the plugin against **the same AthGeneration,23.6.63
environment used for EVNT processing**, then processes ONE existing
Wenu D441 EVNT file on a Condor worker.

The outputs are isolated at:

```
/home/aalida/AQP/validation/rivet/condor_logs/wkts_smoke.<cluster>.out
/data/aalida/AQP_Rivet_full/outputs/_wkts_probe/AQP_WKTSPLITTINGS_Wenu_delta441_smoke.yoda.gz
```

Check the job exit status and search the stdout for
`AQP_WKTS_SMOKE_PASS=`. Do not run full production before this passes.
If it fails, report the exact `RIVET_BUILD`, `ATHENA_WKTS` error and the
first `FATAL` line. Do not equate output-file existence with physics
validation. The smoke script refuses to overwrite an existing test YODA.

No `set -e`, `set -u`, `pipefail`, Condor logs on Ceph, or
`FileSystemDomain` requirements are used.

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
