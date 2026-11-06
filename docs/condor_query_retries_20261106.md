# Isolated Condor-query retry candidate for AQP gridpacks

**Wenu standard111 failure (2026-11-06):** The scheduler returned
`Failed to receive remote ad`, causing the first integration to abort.
Of 300 jobs, Condor history showed 212 completed and 88 removed.
Safe resume from intermediate results remains unverified.

## Isolation and rollback

The installer does not modify the original `.condor/cluster.py` or
`scripts/gridpack.sh`. It creates `.condor/retry_v4/cluster.py`,
copies its `bootstrap_v3`, and writes a separate launcher
`scripts/gridpack_retry_v4.sh` with its own SHA256 pin.
Existing integrations and WW remain untouched.

## On the AF

```bash
cd ~/NWR
git fetch origin
git switch fix/aqp-condor-query-retries-20261106
git pull --ff-only
setupATLAS
asetup 23.6.63,AthGeneration
python3 -m unittest discover -s tests -p 'test_condor_query_retries.py' -v
python3 scripts/install_condor_query_retries.py --check
python3 scripts/install_condor_query_retries.py --apply
python3 -m py_compile .condor/retry_v4/cluster.py
bash -n scripts/gridpack_retry_v4.sh
sha256sum .condor/cluster.py .condor/retry_v4/cluster.py
```

Run a read-only query through the newly staged function:

```bash
python3 - <<'PY'
import ast, subprocess
from pathlib import Path
src=Path('.condor/retry_v4/cluster.py').read_text()
node=next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == '_aqp_query')
ctx={'subprocess': subprocess, 'ClusterManagmentError': RuntimeError}
exec(compile(ast.Module(body=[node], type_ignores=[]), '<query>', 'exec'), ctx)
rows=ctx['_aqp_query'](['condor_q','-constraint','Owner == "aalida"','-af','ClusterId','ProcId','JobStatus'])
print('LIVE_CONDOR_QUERY_PASS', len(rows))
PY
```

After live checks, launch only the replacement Wenu run with:

```bash
bash scripts/gridpack_retry_v4.sh 'JOs/V+jets/W+jets/W(ev)/standard111/200000' 13000 20 200000
```

Do not delete or relaunch in the failed working directory.
To roll back for future launches use the original `scripts/gridpack.sh`.
Offline unit tests are not proof of production reliability.
