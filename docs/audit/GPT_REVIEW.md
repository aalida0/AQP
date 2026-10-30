# Independent review — Wenu audit (2026-10-30)

Reviewed commit: `e09b0223dc72a8a74d8f19db5c5c2911e444c02b` on `audit/production-framework`.

## Verdict

**Source-inspection audit: useful and credible. Production readiness: NOT ESTABLISHED.** The reports distinguish confirmed observations from unperformed tests, cite locally hashed source evidence, and make no unsupported claims of physics validity. This review does not constitute a source-level rerun on UChicago or a validation of event outputs.

## Confirmed, actionable issues

1. **C01 — artifact publication can fail silently.** The runner's EXIT handler retains the body's exit status even when a subsequent required copy fails. Define success by durable, verified outputs plus an atomic completion manifest, not only a successful generator command.
2. **C02/C03 — input identity is insufficient.** Check the archive against the expected SHA256 before extraction, pin code downloads to an immutable commit, and stage complete bundles atomically. A present checksum *file* is not a checksum verification.
3. **C04 — failed attempts can block recovery.** Fixed output directories and zero retries are not intrinsically wrong, but they require safe distinction between partial, failed and complete results. Avoid automatic recomputation of recovered expensive grids.
4. **Duplicate run-card key.** The audited recovered card has case-variant `mcatnlo_delta` assignments; the effective value is true under the inspected parser. Normalize/reject duplicates to avoid fragile semantics; this is **not** evidence that Delta was disabled.

## Physics-validation blockers

1. **P01 — HT-squared bias compensation and normalization.** The supplied `dummy_fct.f` sums transverse energies of *all final-state legs*, not only jets. Validate precisely which LHE/shower weights compensate it, and compare signed yields to a controlled reference. Never infer physical cross sections from a biased integration-summary field.
2. **FxFx effective configuration / matching.** Matching thresholds and multiplicities are internally plausible in the inspected source, but the *resolved* shower fragment, effective Pythia settings, matching veto, and matched signed cross section have not been validated. Specifically check whether any custom FxFx `passcuts_fxfx` change is deployed; the present audit does **not** prove a matching implementation defect.
3. **Recovery provenance.** Reconstructed stage-1 checkpoint metadata and successful restart do not prove the integrations were made by the current compiled executables. Require a reproducible hash manifest of cards, Fortran, compiler flags, executable binaries, grid contents and checkpoint state before reusing grids as physics reference.
4. **Numerical patch.** The `100*epsilon(1d0)` upward Sudakov clamp has been described but not validated. Boundary-test its actual behavior, measure frequency under representative conditions and confirm the exact patched file was compiled in each run.
5. **Statistical performance.** For a biased-weight sample use `S=sum(w)`, `A=sum(abs(w))`, `Q=sum(w*w)`, sign dilution `A^2/S^2`, and effective statistics `S^2/Q`. Record positive/negative absolute sums and per-bin estimates. Do not conflate unweighted negative-event count with the weighted NWF.
6. **Scale/PDF weights.** Existing scale/PDF lists do not imply recorded weights when reweight switches are disabled. First document whether the comparison is nominal-only; decide uncertainty production separately. NNLO PDF with an NLO ME is a defensible choice if intentionally documented, not a standalone bug.

## Important scope distinction

The audit concentrates on the **Delta441 pilot and its runner**. It has not established that all findings apply to `standard111`, `delta111`, `delta221`, earlier Z+jets samples, VV+jets, or ttbar+jets. Build a per-configuration matrix before generalizing. Existing successful shower/Condor exits are operational evidence only.

## Minimal next steps (no Codex needed initially)

1. **Manual, read-only:** verify the branch and report files with `git fetch origin && git switch audit/production-framework && git pull --ff-only` inside the audit checkout.
2. **ChatGPT / GitHub:** implement a small, offline, dependency-light Python test suite for normalized run cards, signed-weight statistics, archive hashes and publication failure injection; commit on the audit branch after review.
3. **Manual UChicago commands:** run these isolated tests and paste only a terse PASS/FAIL summary, SHA and any failing traceback. No generation, integration or job submission.
4. **Codex only when needed:** use a *fresh* MadAgents/Codex session for a bounded question that requires environment-wide source inspection or complex debugging. Read this review and `docs/audit/README.md` as context. Return evidence, not a long narrative.

## Collaboration protocol

- Repo: `aalida0/AQP`; branch `audit/production-framework`; never modify `main` for the audit.
- Each task starts from a fresh context; Git commits and `docs/audit/` carry state between sessions.
- Push only sanitized summaries, source hashes, and tested scripts approved for a **public** repo. No ATLAS-internal material, credentials, raw logs, gridpacks or event samples.
- Every run/test report should identify the Git commit, inputs, command and verdict.
- Do not launch production tasks or change generator settings without explicit user approval.
