# Internal MadGraph HTCondor — focused preflight (no generation)

Scope (2026-10-30): **stabilize MG5 internal Condor submission and recovery, identify mismatches, and simplify JOs after testing**. The PMG-approved HT2 bias and previously successful Sudakov tolerance patch are out of scope absent new contrary evidence. The FxFx mismatch is deferred.

## 1. Run the offline unit tests

On UChicago in the audit checkout:

    cd ~/AQP/aqp-production-audit
    git fetch origin
    git switch audit/production-framework
    git pull --ff-only
    python3 -m unittest discover -s tests -p 'test_aqp_internal_condor*.py' -v

These use synthetic fixtures. They do NOT exercise HTCondor, MadGraph, Pythia or ATLAS and do not write production files.

## 2. Inspect all four original Wenu integrations

    for cfg in standard111 delta111 delta221 delta441_backup; do
      echo "========== $cfg =========="
      python3 scripts/aqp_internal_condor_preflight.py \
        --process "$HOME/AQP/Wjets/WENU/$cfg/PROCNLO_loop_sm-no_b_mass_0" \
        --scan-gfs
    done

This checks current cards and MINT1 logs, classifies historical failure signatures, and checks basic GF file presence. It does not unpickle a controller checkpoint, compile code, or submit jobs. Passing does not establish physics or scheduler reliability.

To classify an additional historical debug or Condor log:

    python3 scripts/aqp_internal_condor_preflight.py --log /path/to/existing/debug.log

For a static scan of a particular integration JO (never execute it):

    python3 scripts/aqp_internal_condor_preflight.py --joboption /path/to/integration_jo.py

For a generation pilot in an outer Condor job:

    python3 scripts/aqp_internal_condor_preflight.py \
      --joboption joboptions/delta441_production16/100003/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441.py \
      --submit condor/delta441_pilot16_seed237_25k_lhe.submit

Important: MG internal Condor integration uses run_mode=1, cluster_type=condor and a positive cluster_size. Local multicore generation **inside an outer Condor allocation** uses run_mode=2, with nb_core no larger than the outer request_cpus. These are different valid modes. The *current* config card can have been changed since initial integration and is not proof of historical submission settings.

## 3. Manual scheduler checks (read-only)

    condor_ping -name head04.af.uchicago.edu -type SCHEDD WRITE
    condor_q -name head04.af.uchicago.edu -af ClusterId ProcId JobStatus

A pass today does not rule out sporadic SECMAN failures during long MG integrations.

## 4. Interpret failures before modifying anything

- SECMAN:2007/2011: scheduler transport/authentication; investigate credential lifetime, polling and submission paths.
- Bad real number in MINT1 after duplicate submissions: possible overlapping writers to one GF. Do not interpret an overwritten failed log as proof that stored integration grids are invalid.
- Missing MINT0/MINT1 artifacts: distinguish delayed output collection, stale controller state, incomplete worker execution, and missing durable files.
- CPU_OVERCOMMIT: outer Condor request_cpus is smaller than local-multicore JO nb_core; correct before submitting again.
- Duplicate run-card keys: inspect the last effective assignment; do not assume Delta was disabled.

## 5. Fix strategy (separate approval required)

The script is a **diagnostic, not yet a cure** for MG internal Condor crashes. Before implementing a fix, inspect the **installed ATLAS MG5 3.5.11** submit, query, stage-output collection and retry code. Develop mocked regressions for transient SECMAN failure, delayed transfers, duplicate GF submissions, stale status files and restart after partial success. Preserve one active writer per (process, stage, GF); avoid blindly repeating integrations. After the backend is stable, consolidate duplicated W/Z/VV/ttbar JO logic, keeping critical physics settings explicit and tested.

## Handoff

Send ChatGPT: unit-test PASS/FAIL, any ERROR/WARN output from four configurations, and a short excerpt from one relevant failure. Do not post raw private logs or secrets in this public repository.

Fresh sessions by default. Use Codex only for investigations that cannot be resolved with manual commands and GitHub-hosted tests.
