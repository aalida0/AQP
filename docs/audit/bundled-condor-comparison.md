# Wenu process-local Condor source comparison — 2026-10-30

Status: **read-only source diff reviewed; runtime module selection still to verify**.

The user compared all four generated-process `bin/internal/cluster.py` files with the exact ATLAS MG5_aMC 3.5.11 `madgraph/various/cluster.py` (central SHA256 `feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe`).

| Configuration | Bundled cluster.py SHA256 | Difference versus central |
| --- | --- | --- |
| standard111 | `624717e154fd9bbf0cb7398f310a93c7d7f48c8d7c1a88bce46cc76844c9e5fc` | Timing-log instrumentation in `submit` / `submit2` |
| delta111 | `10f51467078d72337a0293b09e62d07f68aa6231eae778ef3ec9326ad13d39c0` | Same instrumentation, different output directory |
| delta221 | `f2e95e0143ab6a770679aa7f530d54490fe3f42afaddc6480db761326e8ead16` | Same instrumentation, different output directory |
| delta441_backup | `6c6e193d217313d1b1d04cb28915bf05078109cc8f0da65d9c6f9f1a493adf8b` | Same instrumentation, referring to original `delta441` output directory |

The whole-file diffs contain **only two ~15-line blocks**, setting a customized default `log` value for `ajob1` in steps `0` or `1`, inside `CondorCluster.submit` and `submit2`. There are **no other changes** versus central. Specifically `control` and `control_one_job` are byte-identical with central in all four process bundles. The `@multiple_try()` submission decorators and the problematic `condor_q` exit handling remain unchanged.

The hard-coded `delta441_backup` timing output points to `WENU/delta441/aqp_condor_timing`. This might be an intentional preserved original path after a directory rename, **not established as a defect**. Before reuse, check whether the target exists and is writable.

## Determine the actually imported backend (no generator launch)

The MG5 v3.5.11 launcher `bin/aMCatNLO` imports `internal.amcatnlo_run_interface`; the interface selects `internal.cluster` or `madgraph.various.cluster` depending on whether `madgraph` is importable. Both the launch environment and `sys.path` matter. Run this in **the same AthGeneration environment** used for the integration, with the process-bin directory first on `PYTHONPATH`:

```bash
proc="$HOME/AQP/Wjets/WENU/standard111/PROCNLO_loop_sm-no_b_mass_0"
(
  cd "$proc"
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$proc/bin${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -B - <<'PY'
import os
import internal.amcatnlo_run_interface as ri
print("IMPORT_MODE", "bundled" if ri.aMCatNLO else "central")
print("CLUSTER_MODULE", ri.cluster.__name__)
print("CLUSTER_FILE", os.path.realpath(ri.cluster.__file__))
print("MISC_FILE", os.path.realpath(ri.misc.__file__))
PY
)
```

This imports the interface; it **does not call its run entry point, submit a Condor job, or execute physics generation**. It is not a reproduction of the whole Athena process unless the same setup and Python paths are used. If it fails due to missing dependencies, report the traceback and the setup release; do not change the original process files or run `bin/aMCatNLO` directly.

Independently inspect timing log directories without creating them:

```bash
for cfg in standard111 delta111 delta221 delta441_backup; do
  path="$HOME/AQP/Wjets/WENU/$cfg/aqp_condor_timing"
  [[ "$cfg" == "delta441_backup" ]] && path="$HOME/AQP/Wjets/WENU/delta441/aqp_condor_timing"
  if [[ -d "$path" && -w "$path" ]]; then
    echo "$cfg TIMING_LOG_DIR_OK $path"
  else
    echo "$cfg TIMING_LOG_DIR_ABSENT_OR_NOT_WRITABLE $path"
  fi
done
```

## Next stage

1. Establish central/bundled source at runtime. **Do not patch either until confirmed.**
2. In an isolated **temporary copy**, compose the validated status+submission correction with the existing timing instrumentation, using exact source fingerprints and a strict preservation check.
3. Mock both normal and failure scheduler responses against that exact candidate.
4. Verify lost-acknowledgement reconciliation and any outer-controller retries before attempting an expensive integration. No blanket resubmission.
5. If a live trial is authorized, use a minimal non-physics pilot, not the recovered GF directories.

PMG-approved HT2 bias and previously working tolerance patch remain out of scope; FxFx mismatch is deferred.
