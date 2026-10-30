# Wenu 2026-10-30 internal HTCondor event-log evidence

## New direct evidence

The user executed the read-only event-log audit against the original Wenu processes:

| Configuration | GF/stage timing logs | Distinct submit IDs | Extra IDs | Logs with >1 submission | GF MINT1 bad-real errors | Bad-real GF with >1 submit ID in step1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| standard111 | 600 | 603 | 3 | 3 | 1 | 1 |
| delta111 | 600 | 641 | 41 | 41 | 5 | 5 |
| delta221 | 600 | 744 | 144 | 144 | 5 | 5 |
| delta441_backup | **0 (directory unavailable)** | unknown | unknown | unknown | 15 | unknown |

Across three configurations with available timing logs: **1,800 log files, 1,988 distinct submission records, 188 files with multiple submit IDs**, and **11 of 11** bad-real MINT1 GF targets are in step1 logs with multiple distinct submit IDs.

Specific correlations:

- standard111 `P2_gu_vedepg/GF7.0`: `2879558.0`, `2882483.0`.
- delta111 `P2_dxg_veuxepg/GF2.0`: `2880959.0`, `2882472.0`.
- delta221 `P1_gu_vedep/GF2.0`: `2881016.0`, `2882379.0`.

The earlier theory that MINT1 bad-real errors arose during reentry into an already-updated `mint_grids` now has **substantial direct corroboration**; this is stronger than the source-level hypothetical duplicate risk. But the logs do not yet prove **the exact job interleaving**, whether it was an automatic MadGraph retry versus human/outer orchestration, or physical grid corruption. The 15 delta441 errors cannot be given a scheduler explanation from the absent `WENU/delta441/aqp_condor_timing` directory.

Important nuance: `000` events with distinct job IDs prove *separate submissions*, but do **not** alone prove simultaneous execution. `001` repeated for a **single** job after eviction is a different phenomenon. A later submission after prior termination is an important distinguishable scenario because MINT1 may reread a file rewritten by the previous attempt.

The audit also counted nonzero termination-log files 1, 5, 5 in these configurations, matching the bad-real error counts numerically; per-file correlation has **not** yet been established from those aggregate counts and must not be asserted.

## Next evidence step — read-only timeline

The `scripts/aqp_wenu_mint1_trace.py` tool prints per-stage duplicate-log counts and complete relevant event timelines for the 11 GF targets with existing bad-real errors. It classifies event ordering based on **record sequence within an HTCondor user log**, not unambiguously synchronized wall times or CPU concurrency.

Run on UChicago:

```bash
cd ~/AQP/aqp-production-audit
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_aqp_wenu_mint1_trace.py' -v
python3 scripts/aqp_wenu_mint1_trace.py --base "$HOME/AQP/Wjets/WENU"
```

The analyzer uses **no MadGraph imports, scheduler calls, grid writes or production changes**. It distinguishes:

- `previous_terminated_before_next_submit`: strong evidence of a sequential re-entry attempt;
- `next_submitted_before_previous_terminal`: overlap of job lifetime/submission, but not necessarily concurrent execution;
- `ambiguous_or_no_terminal`: output insufficient.

Corroborate a representative timeline with the raw event log and with the GF `log_MINT1.txt` before stating a historical root cause.

## Operational decision

- **Do not repeat the old Wenu integrations.** The user previously obtained valid-looking 300/300 grid artifact presence checks; provenance and numerical integrity remain separate acceptance issues.
- The four isolated patched bundled `cluster.py` candidates passed source-fingerprint verification and the standard111 mock tests, but were not installed.
- Require a unique submission identity and reconciliation against `condor_q`, `condor_history`, event logs, and GF artifacts before any stage retry.
- A new live pilot should be **disposable/non-physics**, with explicit guarantees against two active writers. Avoid touching the four original process trees.
- Keep AQP production `main` minimal; audit code and forensic notes remain in `audit/production-framework`.
