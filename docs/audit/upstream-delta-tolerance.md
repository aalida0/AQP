# Upstream contribution candidate: MC@NLO-Delta Sudakov tolerance (2026-10-30)

**Recommendation: YES — a small separate upstream PR is justified once a reproducer from a real event is documented. Not an urgent AQP production change.** Keep this distinct from the higher-priority MG internal HTCondor status/duplicate-submission fixes.

## Exact source comparison

Official repository: `mg5amcnlo/mg5amcnlo` (https://github.com/mg5amcnlo/mg5amcnlo).

The **exact same upstream** `Template/NLO/SubProcesses/montecarlocounter.f` blob (Git blob `31efda26a57b4a1868be6c17d43182296bf8b81f`) is present in versions v3.5.11, v3.6.7, v3.7.1, v3.8.0, **v3.8.1** (2026-10-09), and the `3.x` branch checked on 2026-10-30. Its original code aborts whenever `probne>1d0`, regardless of roundoff.

User's patched `montecarlocounter_MINE.f` (SHA256 `fee80cac03c15fc5e7b85c791dbb4f7b284fb004faec47b2e3c6a33c9a861f0a`) was compared against the source fingerprint recorded for the installed ATLAS MG5 3.5.11 template, SHA256 `b1741019d4f756eff7461e9b827af22a65d1cf665e08069455f0cfa73d4aaccc`. **Undoing only the exact 4-line tolerance change (including new declaration) reproduces that upstream SHA256 byte-for-byte.** No unrelated source modifications.

## Proposed minimal patch logic

```fortran
      double precision eps
      ...
      eps = 100.d0 * epsilon(1.d0)
      probne = wgt_sudakov
      if(probne.lt.0.d0)then
         write(*,*)'Error in MC@NLO-Delta: Sudakov smaller than 0',probne
         probne=0.d0
         stop 1
      endif
      if(probne.gt.1.d0+eps)then
         write(*,*)'Error in MC@NLO-Delta: Sudakov larger than 1',probne
         stop 1
      endif
      if(probne.gt.1.d0) probne=1.d0
```

The acceptance interval above 1 is `100*epsilon(1.d0)` ≈ **2.220446049250313e-14** in IEEE binary64. Values in `(1,1+eps]` are clamped to 1. Larger values still abort. Existing negative Sudakov behavior is unchanged. This is numerically tiny, but **100 ulps is a heuristic**, not a demonstrated a priori bound on the interpolation roundoff. Obtain a measured overshoot before presenting this as universally justified.

## Independently compiled guard regression (local gfortran, 2026-10-30)

A fixed-form standalone harness copied the *exact conditional guard* (not the entire MG process) from the upstream and patched code, compiled with `gfortran -ffixed-line-length-none` and tested:

| Test probne | Upstream exit | Patched exit/value |
| --- | --- | --- |
| exactly 1 | 0 | 0, 1 |
| `1+epsilon` | **1** | **0, clamped to 1** |
| `1+99*epsilon` | **1** | **0, clamped to 1** |
| `1+100*epsilon` | **1** | **0, clamped to 1** |
| `1+101*epsilon` | **1** | **1, remains rejected** |
| `-epsilon` | 1 | 1 |
| NaN | 0 | 0 |

**The NaN behavior is present in both versions**, and is outside the narrow proposed PR scope; a separate `ieee_is_finite` safeguard would need its own compiler/support discussion. The harness verifies boundary behavior, **not** that real Sudakov overshoots are solely roundoff artifacts or that the full NLO pipeline is unchanged.

## Why upstream might accept / what reviewers will ask

- The code currently performs the `probne=1d0` assignment immediately before `stop 1` (unreachable for a continuation), and can fail on sub-1e-14 overshoots.
- The proposed code gives the clamp a useful execution path, leaves genuine out-of-range results fatal, and changes the computed factor by at most `O(1e-14)` per affected evaluation.
- Still needed to make a convincing PR:
  1. One real unpatched failing `probne` value printed at **17+ significant digits** (the default Fortran listing may hide the overshoot), plus process/version/seed and basic reproduction steps. Avoid large costly production runs.
  2. Validation that the near-unity overshoot arises from legitimate numerical error (e.g., double precision interpolation), rather than a pathological input or implementation problem.
  3. Small automated test of the guard (boundaries, failure above threshold, negative values), with compiler flags and one representative patched/unpatched small run where practical.
  4. Explain the rationale for the factor 100 (conservative ulp budget versus empirical overshoot); consider whether `max` and `min` alter behavior for NaN on different compilers.
- Consider an optional clamp-count diagnostic, but avoid frequent logs in high-statistics event generation.

## Submission recommendation

Submit a **separate** upstream PR against the maintained `3.x` branch, titled e.g. `MC@NLO-Delta: tolerate roundoff-level Sudakov probabilities above unity`, once the above evidence is ready. **Do not combine it** with the independent HTCondor returncode patch; reviewers and tests are different.

No upstream PR, issue or branch was created in this audit. Current AQP priority remains fixing MadGraph internal HTCondor status/retry handling; FxFx mismatch stays deferred.
