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

## Newly identified upstream bug candidate: unchecked Popen return codes

**Higher priority than the generic duplicate-submit hypothesis.** In upstream v3.5.11, `CondorCluster.control()` and `control_one_job()` read `status.stderr` and test `status.returncode`, but do not call `wait()`, `poll()` or `communicate()` first. `misc.Popen` is a direct `subprocess.Popen` wrapper. Python can retain `returncode=None` even after the child has exited if the caller only reads its pipes. A nonzero `condor_q` result can thus be treated as a warning and an empty stdout response as no active jobs.

**Consequence to test, not yet observed:** a transient `SECMAN` failure might send *all* tracked jobs through missing-output/completion handling rather than a status-query error. This could magnify re-entry, stale-state and duplicate-writer failures.

A unit test in `tests/test_aqp_condor_backend_audit.py` reproduces the subprocess returncode behavior without accessing Condor. The static audit script diagnoses the **actual ATLAS-installed** cluster module:

```bash
cd ~/AQP/aqp-production-audit
python3 -m unittest discover -s tests -p 'test_aqp_condor_backend_audit.py' -v
MG=/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt
python3 scripts/aqp_condor_backend_audit.py --mg-root "$MG"
```

Do not modify CVMFS or source integration directories. Whether the actual ATLAS-patched build contains the same flaw must be established from the output.

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

## Installed ATLAS confirmation and next mock

User ran the static source audit on UChicago. Exact installed files:

- `cluster.py` SHA256 `feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe`
- `misc.py` SHA256 `000fee5201091e7f74083f64f2f269f36adf89d8697e4d9c936cc42e5efa122e`

Both `CondorCluster.control` (lines 1088–1091) and `control_one_job` (lines 1057–1060) read `status.returncode` without a preceding `wait/poll/communicate`. Both submission methods have generic retry decorators. **Source-level defect pattern confirmed in the installed version; historical causal link remains unproven.**

Next, run the isolated *actual installed-method* mock. It replaces calls to the external `condor_q` command with a Python child that exits 42 and writes `SECMAN:2007`; it does not access the scheduler. Method decorators are stripped to prevent delays or retries. We expect the unpatched code to suppress the failure; this is a diagnostic, not a production fix.

```bash
cd ~/AQP/aqp-production-audit
git pull --ff-only
MG=/cvmfs/atlas.cern.ch/repo/sw/software/23.6/sw/lcg/releases/MCGenerators/madgraph5amc/3.5.11.atlas13-dbd05/x86_64-el9-gcc14-opt
python3 scripts/aqp_condor_status_mock.py --mg-root "$MG"
```

Do not patch CVMFS or live integration process trees. Once mock evidence is obtained, prepare and test a **separate candidate copy** of the two methods with `communicate()`, nonzero status treated as failure, robust output parsing, and no new submission on ambiguous scheduler visibility. Test exit-0 queue-empty, exit-nonzero with stderr, malformed output, and partial listings. The candidate must remain isolated until explicitly approved for a new pilot.

## Direction

Only after evidence collection: design an idempotent submit/status/output-commit controller; test transient scheduler errors, missing/incomplete result files, lost submit acknowledgments, and re-entry/duplicate writers with mocks. Keep this separate from FxFx mismatches and PMG-approved HT2 bias. Then reduce JO duplication by retaining explicit per-variant physics settings and a tiny validated shared compatibility layer.
