# One-variable gridpack experiment: store_rwgt_info at integration time

**Branch:** `test/fxfx-pr426-zee2jets`.
**Control (validated only with recompilation):** `tests/1jet/999996`.
**New experimental JO:** `tests/1jet/999995`.
**Analysis:** Zee+0,1j at NLO QCD FxFx, 13 TeV, MC@NLO-Delta, folding 111,
HT² event-generation bias and PR426 exclusive-kT correction.

## Hypothesis

Both the original 0,1j and 0,1,2j Delta111 gridpacks generated hard events
but failed NLO reweighting with `GRIDPACK_RECOMPILE=0`. For the 0,1j sample,
recompilation of an extracted copy produced a valid, Pythia8-showered
20-event EVNT file. Failed no-recompile events lacked `#aMCatNLO` records
expected by `reweight_xsec_events`.

The original 0,1j JO sets:

```python
"store_rwgt_info": not GRIDPACK_MODE,
```

The variant changes this **single executable line** to:

```python
"store_rwgt_info": True,
```

so NLO reweight metadata is requested at **gridpack creation**, not only
after extraction. The source-level change is isolated. It is **not yet
proven** that this corrects the packaged binaries. Other Fortran code and
settings are byte-identical to the already integrated 0,1j reference.
The new JO has a different short name to keep archives distinct.

**Important:** `req_acc=0.5` remains deliberately loose. None of the
generated events or resulting cross sections are fit for physics analysis.

## 1. Preflight on UChicago AF

```bash
cd ~/NWR
git switch test/fxfx-pr426-zee2jets
git pull --ff-only
setupATLAS
asetup 23.6.63,AthGeneration

python3 scripts/check_sample.py tests/1jet/999995
python3 -m unittest discover -s tests -p 'test_zee1jet_rwgt_gridpack_jo.py' -v
bash -n scripts/validate_zee1jet_rwgtgridpack.sh
test -f "${PY8PATH:?PY8PATH missing}/lib/libpythia8.a"
```

The unit tests must all pass before triggering integration. They check
that only `store_rwgt_info` differs from the previously integrated 1j
JO, that the patches are identical, and that the new script targets DSID
999995. No integration is performed by these checks.

## 2. Integrate one fresh gridpack

```bash
cd ~/NWR
bash scripts/gridpack.sh tests/1jet/999995 13000 20 34301
```

This invokes the established Condor integration launcher; do not execute
integration jobs directly on a shared login node. It prints
`RUN`, `OUTPUT`, and the `tmux -L ... attach -t gridpack` command.
The output root is `/data/aalida/NWR/gridpacks/tests-1jet-999995/`.

After completion, check:

```bash
find /data/aalida/NWR/gridpacks/tests-1jet-999995 -name timing.txt \
  -exec grep -H 'result_exit=' {} \;
find /data/aalida/NWR/gridpacks/tests-1jet-999995 \
  -name 'mc_13TeV*.GRID.tar.gz'
```

Expect `result_exit=0` and a valid nonempty `mc_13TeV*` archive.
Check `generation.log` / `log.generate` for
`Setting store_rwgt_info = True` in gridpack-creation mode.
The archived final run card is the authority, not the JO expression.

To audit the archive without unpacking it, set `GP` to the
**actual full path** from `find` above, and run:

```bash
MEMBER=$(tar -tzf "$GP" | grep -E '(^|/)Cards/run_card.dat$' | head -1)
echo "RUN_CARD_MEMBER=$MEMBER"
if [[ -n "$MEMBER" ]]; then
  tar -xOzf "$GP" "$MEMBER" | grep -i -E 'store_rwgt_info|reweight_scale|reweight_pdf|mcatnlo_delta|folding'
fi
```

**Stop** if the effective creation run card did not have
`store_rwgt_info=True`. Otherwise the experiment did not vary
the intended setting.

## 3. One-event-mode test first, with no recompilation

Only on a suitable batch worker that has AthGeneration/23.6.63:

```bash
cd ~/NWR
setupATLAS
asetup 23.6.63,AthGeneration
GP=/absolute/path/to/new_999995_gridpack.GRID.tar.gz

bash scripts/validate_zee1jet_rwgtgridpack.sh "$GP" 20 34302
```

The validator stages a fresh copy and prints `RUN=...`.
It defaults to `GRIDPACK_RECOMPILE=0`, retains failed logs, checks for
Pythia8 and validates **exactly 20** CollectionTree entries.

**If successful**, the new gridpack has passed a functional no-recompile
local test; repeat with one independent seed before trying PanDA.
**If it fails** with `This event file cannot be reweighted [1]`,
the `store_rwgt_info`-at-build hypothesis is insufficient.

For a failed run, inspect the local `RUN` directory:

```bash
python3 scripts/diagnose_gridpack_reweight.py "$RUN" --focus P1_ --max-logs 8
python3 scripts/audit_gridpack_reweight_build.py "$RUN" --focus P1_ddx_emepg/GF1.0
```

For the second command, replace the example focus with a real
`P*/GF*` directory in the current run.

## 4. Only if the no-recompile test fails: compare recompilation

```bash
bash scripts/validate_zee1jet_rwgtgridpack.sh "$GP" 20 34302 --recompile
```

This uses the **same archive and seed** with a new extraction directory.

| No recompilation | Recompile | Interpretation |
|---|---|---|
| PASS | Not needed | Storing metadata at build time is a viable fix for the 1j gridpack |
| FAIL | PASS | Changing store_rwgt_info alone did not solve precompiled binary issue |
| FAIL | FAIL | Further incompatibility; inspect detailed worker logs |

A 1j PASS is necessary but not sufficient to certify the old 2j
gridpack. Apply the validated build change to a new 2j archive
before claiming general resolution.

No gridpack is generated, submitted to PanDA, or uploaded to Rucio
automatically by these commits. Original archives and working JOs are
untouched.
