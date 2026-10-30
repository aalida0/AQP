# Wenu Delta441: active versus backup artifact audit (2026-10-30)

**PRODUCTION-PROVENANCE CORRECTION (2026-10-30):** The word *active* below identifies one of two **historical source trees** in this comparison, **not** the validated Delta441 production candidate. That is the separate cleaned `delta441_cleaned_v1` gridpack (25,000 LHE / 5,000 FxFx EVNT pilot). See [wenu-delta441-validated-production.md](wenu-delta441-validated-production.md).


**Read-only results provided by user** from `scripts/aqp_compare_delta441_active_backup.py`, followed by the updated active Delta441 event-log and timeline audits.

| Finding | Active `WENU/delta441` | Historical `WENU/delta441_backup` |
| --- | ---: | ---: |
| GF directories | 300 | 300 |
| GF with all four nonempty `mint_grids`, `grid.MC_integer`, `res.dat`, `results.dat` | 300 | 300 |
| `log_MINT1.txt` with bad-real marker | 0 | 15 |
| GF with MINT1 log file | **0** | **300** |
| Per-stage Condor timing log directory available | **No** | **No** (hardcoded timing path in backup points at active `delta441`, which is absent) |

The 15 GF targets with a bad-real marker in **backup** are all present in **active**; for every one, the active `mint_grids` file is nonempty and has a **different byte size** from the backup file. The other three integration artifacts remain nonempty and have **equal byte sizes** but different modification times. This is consistent with the active process being reassembled/reintegrated after backup, but it is **not proof** that those files are numerically correct, that other files are byte-identical, or that each affected GF was successfully recomputed.

**Critical interpretation:** `BAD_REAL_MINT1=0` for active Delta441 is because the 300 `log_MINT1.txt` files are **absent**; it must not be reported as 300 successful MINT1 jobs. Current grid presence is 300/300, but numerical validation and provenance remain open.

The event-log and MINT1 trace scripts targeting **active** Delta441 found no timing directory, no current MINT1 logs, and therefore cannot reconstruct Delta441 scheduling. Never equate lack of records with lack of duplicate jobs.

## Next low-impact integrity checks

1. Read-only file content hashes for `mint_grids` and selected artifacts in the **15 backup-bad GF paths**, comparing active and backup. Identical byte size does not imply identical content.
2. Evaluate the full set of 300 GF for which `mint_grids` sizes differ, to test whether the differences are concentrated in the 15 recovered channels or represent general repacking.
3. Inspect the actual MINT-mode grid records (MAX/SUM/QSM/SPE) and independent physics validation of process result summaries and pilot LHE (where already available).
4. Search for retained runtime or Condor history logs elsewhere before concluding scheduling provenance is lost.
5. The patched Delta441 backend SHA in the earlier four-candidate list pertains to **`delta441_backup`**, not active `delta441`. Do not install it into active Delta441; audit active `bin/internal/cluster.py` separately if future work requires it.

No current/backup process should be overwritten or used for a live Condor pilot. Preserve original outputs.
