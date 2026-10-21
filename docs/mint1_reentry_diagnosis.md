# AQP W+jets MINT1 re-entry failure — source-based hypothesis

Status: **source-level mechanism identified, local file provenance not yet validated**. This is a diagnostic note, not authorization to rerun or patch production files.

## Observed

Across 4 W+jets FxFx configurations, 26 `log_MINT1.txt` files end with

```text
At line 1135 of file mint_module.f90 (unit = 12, file = 'mint_grids')
Fortran runtime error: Bad real number in item 15 of list input
```

Two report item 12 instead. In the inspected runs, this follows `imode is 1`. These 26 targets occurred in job campaigns affected by duplicate HTCondor submissions. The four counts are 1, 5, 5, 15 for standard111, delta111, delta221, delta441_backup.

## Upstream v3.5.11 code

https://github.com/mg5amcnlo/mg5amcnlo/blob/v3.5.11/Template/NLO/SubProcesses/mint_module.f90

- `initialise_mint` (line 223): `if (imode.ne.0) call read_grids_from_file`.
- `write_grids_to_file` (line 1074+): `if (imode.ge.1)` writes `MAX` grid records; then `SUM`, `QSM`, `SPE`, `AVE`.
- `read_grids_from_file` (line 1107+): `if (imode.ge.2)` reads the `MAX` grid records, whereas imode 1 skips them; line 1135 reads the `SUM` array: `read (12,*) dummy,(ans(i,kchan),i=1,nintegrals)`.
- `finalise_mint` (line 928) calls `write_grids_to_file`.

**Hypothesis:** when a completed MINT1 job rewrites `mint_grids`, another MINT1 submission targeting the same GF directory subsequently attempts to read this MINT1-format file as if it were still the MINT0 input. The `MAX` records then cause a parsing misalignment and a bad real at the `SUM` read. This can overwrite the log of a previously valid computation.

This is not yet proven to be the cause of every error: check the installed ATLAS 3.5.11 source against upstream, timestamps, grid records, and successful-versus-failed attempts.

## Minimal read-only check on UChicago AF

```bash
cd ~/AQP/Wjets/WENU
for cfg in standard111 delta111 delta221 delta441_backup; do
  proc="$PWD/$cfg/PROCNLO_loop_sm-no_b_mass_0"
  echo "===== $cfg source ====="
  find "$proc" -name mint_module.f90 -type f -print | head -5
done

proc="$PWD/standard111/PROCNLO_loop_sm-no_b_mass_0"
for gf in \
 "$proc/SubProcesses/P2_gu_vedepg/GF7.0" \
 "$proc/SubProcesses/P2_gu_vedepg/GF6.0"; do
  echo "===== $gf ====="
  stat -c '%y %s %n' "$gf"/mint_grids "$gf"/log_MINT1.txt "$gf"/log.txt "$gf"/results.dat
  echo "record labels near SUM:"
  grep -nE '^[[:space:]]*(SUM|QSM|MAX|SPE)[[:space:]]' "$gf/mint_grids" | tail -25
  echo "tail of MINT1 and alternative log:"
  tail -8 "$gf/log_MINT1.txt"
  tail -8 "$gf/log.txt"
done
```

Before any attempted recovery, verify that the actual generated `mint_module.f90` has the same `read/write` conditions. The example above uses GF7.0 (known anomalous) and GF6.0 (comparison candidate; independently verify GF6.0's validity).

## Recovery policy

1. **Do not overwrite the original backup.** Take a filesystem snapshot, or copy only relevant content to a working area with sufficient quota, first.
2. **Do not blindly replace `log_MINT1.txt` with `log.txt`.** The log is only one artifact; verify `mint_grids`, `results.dat`, `res.dat`, `grid.MC_integer`, and their provenance.
3. Distinguish *late failed duplicates* from *failed original computations*. Check HTCondor IDs and timestamps, as well as physical output validity.
4. Only after valid integrations are independently established, develop and test finalization on a copy; do not rerun all 300 GF targets.
5. Recompute timing with the original completed worker attempts, excluding failed rereads. The earlier one-duration-per-GF timing parser is provisional.

The current run cards and exact ATLAS source remain authoritative; upstream is a reference, not a substitute for an ATLAS-specific source audit.

## Confirmed local source check (21 October 2026)

The generated ATLAS 3.5.11 `mint_module.f90` matches upstream in the relevant blocks: the `imode.ge.1` writer includes `MAX` records, whereas the `imode.ge.2` reader consumes them. Both GF6.0 and GF7.0 in `standard111/P2_gu_vedepg` contain these records before `SUM/QSM/SPE`.

**Important correction:** `GF6.0/log.txt` and `GF7.0/log.txt` both explicitly say `Generating events, doing only one iteration` and `imode is 2`. They are NOT recovered MINT1 logs. GF7.0 `log_MINT1.txt` has a bad-real parse error; its separate `imode=2` event generation log has a normal-looking completion, indicating the stored MINT grids were readable in the subsequent phase. Full numerical integrity of all 26 affected GF targets remains to be validated.

Next focus: compare event-generation outputs and gridpack contents for standard111, delta111 and delta221; validate the 15 suspect `delta441_backup` GF integration artifacts and finalize without an unguarded `launch` or blanket recomputation. Timing estimates remain provisional while job provenance is unresolved.
