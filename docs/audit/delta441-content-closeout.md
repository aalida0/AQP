# Wenu Delta441 closeout gate before returning to sample validation

**Scope:** active `WENU/delta441` compared with historical `WENU/delta441_backup`. Never treat backup as the active physics sample.

## Established facts

Both directories have 300 GF directories and all four tracked grid artifacts are nonempty for each GF. Backup contains 15 `log_MINT1.txt` bad-real markers, while the active process has **no MINT1 logs at all** (not 300 verified successful jobs). For each of those 15 backup GF channels, active `mint_grids` has a changed file size; other artifacts have unchanged file sizes but different mtimes.

In standard111/delta111/delta221, the **11/11** documented bad-real MINT1 GF channels each had a second submitted job: original worker exit 0, duplicate worker exit 2, and duplicate execution after the original's termination. That strongly supports erroneous re-entry, but does not identify which controller launched each duplicate.

## One targeted read-only check

`scripts/aqp_delta441_content_audit.py` computes SHA-256 content comparisons of **all 300 pairs of `mint_grids`**, even for equal-length files, and compares all four files for each of the 15 previously affected backup GF directories. All other artifact files are compared by presence/size in default mode. The optional `--all-artifacts` mode hashes all four artifacts across all 300 GFs.

```bash
cd ~/AQP/aqp-production-audit
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_aqp_delta441_content_audit.py' -v
python3 scripts/aqp_delta441_content_audit.py --base "$HOME/AQP/Wjets/WENU"
```

**Interpretation:**
- If the changed grid hashes are exactly the 15 former bad-real GF channels, the active process is consistent with a targeted recovery. Equal grids for other GF paths is strong evidence they were preserved, but not proof of physics correctness.
- If more grids differ, record how many and identify whether it is a broad reintegration or repackaging, rather than asserting corruption.
- If any file is missing or empty, **do not regenerate the full grid**. First inspect only affected GF and any existing gridpack/LHE tests.
- If content is readable and plausible, proceed to independent physics checks with **existing** gridpacks / already-generated events. Full MINT numerical integrity requires physics-level cross-section stability and successful events; byte hashes alone cannot certify it.

No scheduler query, production edit, Condor job or integration run is performed.

## Project decision after closeout

**Stop doing historical Condor forensics unless the physics checks fail.** Keep the four source-pinned bundled patch candidates and their checks in the audit branch; they are not ready for unattended production until durable submission identity/reconciliation and a disposable live test are completed. Do not install a backup-derived Delta441 candidate into active Delta441.

Primary AQP work to resume: quantify Wenu FxFx per config (weighted/unweighted negative-weight fraction, (D=(1-2f_\mathrm{weighted})^{-2}), matching efficiency, timing and integrated effective event cost), then Rivet differential cross-checks against references; maintain a separate audit for generator reliability. Preserve all gridpacks and frozen event samples.


## Actual content comparison — user-run results, 2026-10-30

The newly added offline tests passed (user reported `OK`). The active/backup content audit reported:

- 300/300 GF directories on both sides, 300 common.
- For `mint_grids`, **300/300 changed byte size** (and therefore byte content); not confined to the 15 backup bad-real channels.
- Among **15 backup-bad-real GF channels** only: `grid.MC_integer` **11 same-size content changes / 4 byte-identical**; `res.dat` and `results.dat` **15/15 same-size content changes** each. The remaining 285 GF channels' non-grid artifacts were **not hashed** (the tool reports `SAME_SIZE_NOT_HASHED`, not `IDENTICAL`).
- All four artifacts were previously found nonempty at all 300 GF for both active and backup.
- Active `delta441` lacks `log_MINT1.txt` for all 300 channels; `0` bad-real markers there means **no relevant logs to inspect**, not proof of success.
- Thus the active process differs systematically from backup. A different MINT stage, broad regeneration or a reconstructed snapshot are hypotheses; none established by sizes alone.

**Decision:** Stop historical provenance investigation here, unless a downstream physics or structural check fails. Do **not** conclude active grids are corrupted, and do **not** reintegrate. Preserve the backup and active copies. Check a representative pair's `MAX/SUM/QSM/SPE` record structure if needed to distinguish stage-level format differences. Continue physics validation of **existing** Wenu gridpacks and successfully generated+showered pilot events (verify cross-section/weights and output integrity), then populate the folding-comparison report (weighted and unweighted NWF, dilution, FxFx efficiency, per-stage CPU and wall time). Separate a Condor non-physics reliability pilot from these physics deliverables.

Previously prepared `delta441_backup` Condor patched candidate **must not** be installed in the active `delta441` process. The submission/status corrections remain offline validated but do not implement idempotent recovery.

