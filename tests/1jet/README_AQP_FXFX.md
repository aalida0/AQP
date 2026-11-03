# FxFx 0+1-jet MC@NLO-Delta diagnostic branch

**Branch:** `test/aqp-fxfx-1jet-20261103`.
Derived from the 2026-11-03 main JOs. Six complete DSID-local
0+1-jet FxFx Delta111 smoke JOs share the same full PMG
event-mode PDF/scale variations and `store_rwgt_info=True`
at BOTH gridpack integration and event generation.

| Channel | Test DSID | Full 0+1+2j JO |
|---|---|---|
| Zee | `910001` | `100001` delta111 |
| Wenu (W+) | `910002` | `200001` delta111 |
| OS WW -> lnu lnu | `910003` | `300011` delta111 |
| WZ -> lllnu | `910004` | `300012` delta111 |
| ZZ -> 4l | `910005` | `300013` delta111 |
| ZZ -> 2l2nu | `910006` | `300014` delta111 |

Only `@2` removal, `PYTHIA8_nJetMax=1`, accuracy 0.5
(smoke only), and the description differ from the parents.
All required Fortran sources/PR426 patches are byte-identical.

## Static checks
```bash
cd ~/NWR
git fetch origin
git switch test/aqp-fxfx-1jet-20261103
git pull --ff-only
python3 -m unittest discover -s tests -p test_fxfx_1jet_configs.py -v
for d in tests/1jet/91000{1..6}; do python3 scripts/check_sample.py "$d"; done
bash -n scripts/validate_fxfx_1jet.sh
```

## Integration and event-generation test
```bash
setupATLAS
asetup 23.6.63,AthGeneration
test -f "${PY8PATH:?set PY8PATH}/lib/libpythia8.a"
bash scripts/gridpack.sh tests/1jet/910001 13000 20 34311
# Use the NEW archive path from the launcher:
GP=/absolute/path/to/mc_13TeV.new1jet.GRID.tar.gz
bash scripts/validate_fxfx_1jet.sh tests/1jet/910001 "$GP" 20 34312
```

Start with Zee and Wenu. VV JOs retain archived MadSpin decay
instructions, but these are **unvalidated for Delta FxFx** and may
need process-specific changes. Do not run Condor integration on
shared login nodes. These 1j studies use `req_acc=0.5` and are not
suitable for cross sections, negative-weight fractions, or physics
publication. A 20-event success also does NOT prove the full PMG
uncertainty weights are present; audit LHE and EVNT weight names.

No Rucio/PanDA submissions or integration jobs are started by these commits.
