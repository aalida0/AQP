# Wenu Delta441: authoritative validated production provenance

**Status corrected after cross-check with the separate October 2026 production-validation conversation.** This document supersedes any recommendation to use raw `WENU/delta441` or `WENU/delta441_backup` as the Delta441 production gridpack.

## Which output to use

| Name | Role | Supported conclusion |
| --- | --- | --- |
| `WENU/delta441` | Earlier process/integration attempt | **Not the validated production artifact.** The read-only 2026-10-30 audit found 300 GF sets but no current `log_MINT1.txt` logs; this does not establish integration success. |
| `WENU/delta441_backup` | Preserved MINT1 grids / historical recovery checkpoint | Original recoverable material, including 15 bad-real log markers from subsequent duplicate MINT1 attempts. Preserve, not selected directly for production. |
| Cleaned Delta441 (earlier notes sometimes call working version `delta441_clean_v1`, gridpack version `delta441_cleaned_v1`) | Cleaned/recovered build with linker fixes, stale debug logs removed and pilot generation checked | **Validated production candidate**; retain exact gridpack/JO provenance. |

The previously verified **final gridpack filename** is:

```text
mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441_cleaned_v1.MG3511.GRID.tar.gz
```

Do not infer an on-disk directory path from the version label; verify the location and SHA256 of this exact archive in the actual production environment. Do **not** substitute a `delta441` or `delta441_backup` gridpack by naming convention alone. Preserve all originals.

## Completed pilot, as recorded in the other AQP conversation (October 23, 2026)

- **25,000 LHE events** generated using **16 CPUs**, and the output event count was checked.
- **5,000 FxFx-showered EVNT events** produced successfully (reported exits 0).
- Pilot negative-weight fractions: **18.36% raw count**, **18.07% absolute-weighted**. The pilot's reported statistical dilution is about **2.4514**, consistent with `(1-2×0.1807)^(-2)`.
- Pilot FxFx acceptance/matching efficiency: **41.1692%**.
- An intermediate event-output name from the earlier validation: `delta441_clean_v1_seed237_25000lhe.TXT.tar.gz`; this is a *pilot event archive*, not the final gridpack. Earlier output was in a `production_pilot/delta441_16cpu_seed237_25k_lhe/` area under `/data`. Do not conflate archive and gridpack.

These demonstrate successful end-to-end generation for the validated cleaned configuration; not full production-scale throughput, independent Rivet agreement, or a certified generator-wide fix.

## How to interpret October 30 historical comparison

The earlier hash comparison of `WENU/delta441` versus `WENU/delta441_backup` showed that **all 300 `mint_grids` changed size**. That finding concerns only **two historical working trees** and has no basis to overturn the successful pilot of the **separate cleaned gridpack**. In the 15 backup-bad-real GF locations, `res.dat` and `results.dat` were 15/15 byte-different (same file size) and `grid.MC_integer` 11/15 byte-different.

No `log_MINT1.txt` files were available in the raw `delta441` tree; its zero bad-real marker count reflects missing logs, **not validated integration**. This issue is separate from the cleaned production pilot.

## Condor patch qualification

A previously generated isolated combined `cluster.py` candidate for `delta441_backup` was source-pinned to **backup**, and must not be copied into the cleaned build. The actual generated-process `bin/internal/cluster.py` for the cleaned gridpack, if used, needs its **own source fingerprint and clean import test**. The source-level Condor status/submission defects have an offline fix, but it has **not** been deployed or validated as a durable, idempotent scheduler recovery protocol.

## Immediate AQP priorities

1. Treat the **cleaned Delta441 gridpack and validated pilot** as the production reference; freeze its JO, generation log, archive checksum, and summary metrics.
2. Compare standard111, delta111, delta221, and **cleaned Delta441** with consistent Wenu selection, HT2-bias treatment and absolute-weighted NWF extraction.
3. Quantify negative-weight dilution, FxFx acceptance and CPU cost from actual generation/integration logs; cross-check pilot metadata and total effective generated events.
4. Run/complete Rivet differential validation against appropriate reference samples.
5. Keep non-physics live Condor reliability testing separate. **Do not regenerate historical MINT grids merely to resolve a backup/raw directory discrepancy.**
