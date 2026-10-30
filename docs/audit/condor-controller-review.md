# Internal HTCondor controller — focused source review (2026-10-30)

## Wenu four-configuration preflight findings

User-run read-only preflight of **original** Wenu processes:

| Variant | run_mode | cluster_type | cluster_size | nb_core | GF dirs | MINT1 bad-real log markers |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| standard111 | 1 | condor | 100 | 1 | 300 | 1 |
| delta111 | 1 | condor | 100 | 1 | 300 | 5 |
| delta221 | 1 | condor | 100 | 1 | 300 | 5 |
| delta441_backup | 1 | condor | 100 | 1 | 300 | 15 |

Effective Delta/folding switches all match labels. The `mcatnlo_delta` key appears twice (lines 23 and 65), with the correct effective last entry. No absent `mint_grids`, `res_1.dat`, or `results.dat` were reported by the **presence check**, which does not establish correctness. The 26 error markers repeat an existing historical anomaly; **they do not imply 26 integrations require rerunning**.

## New source-based hypotheses to verify in the installed ATLAS build

Source referenced: upstream MG5_aMC@NLO **v3.5.11**, `madgraph/various/cluster.py` and `madgraph/various/misc.py`. These are **not yet proven identical** to `3.5.11.atlas13-dbd05` installed at UChicago.

1. **Queue disappearance is interpreted as potential completion.** `CondorCluster.control()` queries `condor_q` and passes any tracked job ID absent from its output to `check_termination()` (cluster.py around lines 1069–1111). If scheduler visibility is transient, controller state can diverge from running jobs; delayed artifact visibility then looks like failure. Investigate whether this can lead to overlapping writers in *the installed code*.
2. **Output validation and retry policy are separate.** `check_termination()` tests required files for existence and nonzero size, waits `cluster_retry_wait` (default 300 seconds in `Cluster.__init__`), then stops or resubmits according to `cluster_nb_retry` (default 0) (cluster.py around lines 377–472). A missing file is not necessarily proof that computation failed or is safe to resubmit.
3. **Submission calls are decorated with a generic retry handler.** `CondorCluster.submit()` and `submit2()` have `@multiple_try()` (cluster.py around lines 890, 958); `multiple_try` defaults to five attempts and backs off after exceptions (misc.py around lines 447–473). A retry is *not guaranteed idempotent* if HTCondor accepted the first request but its acknowledgment was lost or unparseable. This is a **potential duplication mechanism**, not a demonstrated cause of the historical 26 errors.
4. **Status-query retries are bounded.** `CondorCluster.control()` has `@multiple_try(nb_try=10,sleep=10)`. Correct handling of `SECMAN:2007/2011` must distinguish retryable authentication/transport failures from a genuine absence of a job; guard against treating an incomplete `condor_q` response as all jobs finished.

No backend patch should be proposed until installed-source differences and original controller logs are checked. **Do not blindly raise `cluster_nb_retry`: that can make duplicate-writer corruption worse.**

## Manual, read-only evidence request (no Codex)

On UChicago:

```bash
MG=/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt
sha256sum "$MG/madgraph/various/cluster.py" "$MG/madgraph/various/misc.py"
grep -nE 'class CondorCluster|def (submit|submit2|control|check_termination)|@multiple_try|cluster_nb_retry|cluster_retry_wait|condor_q' "$MG/madgraph/various/cluster.py" | head -65
for cfg in standard111 delta111 delta221 delta441_backup; do
  f="$HOME/AQP/Wjets/WENU/$cfg/PROCNLO_loop_sm-no_b_mass_0/Cards/amcatnlo_configuration.txt"
  echo "=== $cfg retry config ==="
  grep -niE '^[[:space:]]*(cluster_nb_retry|cluster_retry_wait|cluster_queue|cluster_temp_path|cluster_status_update|cluster_size)[[:space:]]*=' "$f" || true
done
find "$HOME/AQP/Wjets/WENU" -maxdepth 3 -type f \( -name '*debug.log' -o -name '*condor*.log' \) -print | head -30
```

These commands emit source identifiers, card settings and candidate log paths, not production data. If the ATLAS-patched code differs, resolve that difference *before* implementing changes.

## Direction

Only after evidence collection: design an idempotent submit/status/output-commit controller; test transient scheduler errors, missing/incomplete result files, lost submit acknowledgments, and re-entry/duplicate writers with mocks. Keep this separate from FxFx mismatches and PMG-approved HT2 bias. Then reduce JO duplication by retaining explicit per-variant physics settings and a tiny validated shared compatibility layer.
