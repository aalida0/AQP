# Zee/Wenu FxFx Condor event-generation pilot (development only)

**Branch:** `study/vjets-condor-20k-no-syst-20261108`. Never merge into `main` without separate PMG review.

## Objective

Eight completed gridpacks: Zee and Wenu, each with standard111, delta111, delta221, delta441.
Target: **20,000 accepted EVNT events per configuration** (160,000 total), in **four independent 5,000-event chunks per configuration**. First do ONE 20-event smoke, then ONE 5,000-event chunk.

## Changes relative to main

- The existing central PDF (325100), signed nominal weights, HT2 bias, FxFx matching, folding and MC@NLO-Delta settings are unchanged.
- `pdf_variations=[]`, `alternative_pdfs=[]`, `scale_variations=[]` in gridpack and event modes. This suppresses PDF/scale systematic *variations*, **not nominal signed event weights**.
- Event mode defaults to `run_mode=1, cluster_type=condor, nb_core=1, cluster_size=100, cluster_nb_retry=0`, using the existing config dictionary; `EVENT_USE_CONDOR=0` switches only event mode back to `run_mode=0, nb_core=1` for a controlled fallback. Gridpack mode is not modified.
- `store_rwgt_info=True` remains unchanged for compatibility with already-built gridpacks; avoid rewriting frozen cards.

## Important runtime distinction

**MadGraph internal Condor mode != submitting a complete Gen_tf transform to Condor.**
The Athena/Pythia8 controller runs on the invoking compute host, and MadGraph may delegate hard-event generation to Condor. We have **not yet executed a smoke test** of Condor event mode in `AthGeneration,23.6.63`. Ensure a supported controller environment (not a login node if site policy disallows long tasks) with Condor scheduling access, a shared work directory under `/home`, and the validated source-pinned MadGraph Condor bootstrap if required. Never place the worker-visible process directory exclusively on AF `/data` without verifying mounts.

## Configuration map

| Process | Config | DSID |
|---|---|---|
| Zee | standard111 | 100000 |
| Zee | delta111 | 100001 |
| Zee | delta221 | 100002 |
| Zee | delta441 | 100003 |
| Wenu | standard111 | 200000 |
| Wenu | delta111 | 200001 |
| Wenu | delta221 | 200002 |
| Wenu | delta441 | 200003 |

## Preflight and smoke

```bash
cd ~/NWR
git fetch origin
git switch study/vjets-condor-20k-no-syst-20261108
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh"
asetup 23.6.63,AthGeneration
command -v Gen_tf.py
command -v condor_submit
python3 scripts/check_sample.py 'JOs/V+jets/W+jets/W(ev)/delta111/200001'
```

Locate exactly one matching gridpack from `/data/$USER/gridpacks` (avoid ambiguous 1-jet test gridpacks), stage it into a unique run directory under shared `/home`, and copy the corresponding complete JO directory there. Then start a 20-event smoke with `Gen_tf.py --ecmEnergy=13000 --maxEvents=20 --randomSeed=471001 --firstEvent=1 --jobConfig=<absolute JO directory> --outputEVNTFile=delta111_smoke.EVNT.pool.root` and the gridpack **extracted** into the run directory. The existing JO gridpack-detection mechanism must be verified in the logs, rather than assumed. Keep `EVENT_USE_CONDOR=1`; use `EVENT_USE_CONDOR=0` only for a diagnostic comparison.

**Do not launch eight 20k tasks at once.** First confirm the Condor workers were actually used, the gridpack was consumed without reintegration, the transform terminated successfully, and the EVNT/LHE signs are nontrivial.

For production use 4 chunks/configuration with distinct seeds; preserve LHE tarballs, EVNT files, gridpack and JO checksums, transform logs, job wall and CPU accounting. Restore the full PMG variation list for any later official physics systematic sample.

## Audit

Per seed and configuration record:
`N_generated_LHE`, `N_accepted`, `nTried`, `nAccepted`, count NWF, absolute-weight NWF, `sumw`, `sumw2`, `Neff=(sumw)^2/sumw2`, weighted mean observables, cross section estimate and error, and CPU/wall time. Sum signed weights and squared weights before aggregating. Do not average per-job NWF ratios. The 20k pilot is preliminary and not a full physics validation.
