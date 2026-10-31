# AQP Wenu Standard111 FxFx exclusive-kT regression (upstream MG5 PR #426)

**Purpose:** test *only* the FxFx physics mismatch raised in PMG, not the Condor backend reliability fix. Scope is Standard111 Wenu+0,1,2 jets before/after the exact same physics-level change in `passcuts_fxfx()`. This is a controlled technical proof-of-concept, **not** production-quality integration.

## Authoritative references

- CERN PMG work item (provided by user; may require CERN authentication): https://gitlab.cern.ch/atlas-physics/pmg/mcjoboptions/-/work_items/252
- Public MG5_aMC PR #426: https://github.com/mg5amcnlo/mg5amcnlo/pull/426
- Upstream PR merged into `3.5.17` on 2026-09-28; **does not by itself demonstrate inclusion in the ATLAS `3.5.11.atlas13` build**.
- Source: `Template/NLO/SubProcesses/cuts.f`, function `passcuts_fxfx(p,pQCD,nQCD)`.
- Change replaces the old inclusive `amcatnlo_fastjetppgenkt_etamax_timed(...)` jet-count test by exclusive `amcatnlo_fastjetdmergemax(nQCD-2) < ptj**2`, with the proper `nQCD>1` and `ptj>0` guard. Preserve the subsequent `FxFx_ren_scales` cut.

## Two isolated cases

- `before`: source from the **same** ATLAS MG5_aMC 3.5.11.atlas13 environment without the FxFx correction.
- `after`: the identical process, created in a separate clean directory, with **only** the PR #426 change applied and checked.
- Keep the entire Condor backend **unchanged between cases**; use *outer* Condor with `run_mode=2` local multicore to prevent old internal `condor_q` bugs from contaminating the FxFx test.
- Wenu + 0,1,2 partons, Standard111, `mcatnlo_delta=False`, `folding=1,1,1`, `ickkw=3`, `ptj=8`, `jetradius=1`, matching parameters `nJetMax=2`, `qCut=20`, same PDFs, event bias, scales, MadSpin/EvtGen, random seed(s), and Pythia8 A14 settings.
- `req_acc=0.1` is for a functional smoke only, not a final cross-section / NWF precision claim. Start with ~200 LHE events each to prove correct code is in effect and successfully builds; target 50,000 LHE each after clean smoke. Independently integrate both variants with the same accuracy and random control; never reuse old gridpacks/grids.

## Safe first step: generate a patched template copy (does not install patch)

```bash
cd /home/aalida/AQP/aqp-production-audit
git pull --ff-only
python3 -m unittest discover -s tests -p 'test_aqp_fxfx_exclusive_kt_patch.py' -v

source /cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase/user/atlasLocalSetup.sh
asetup AthGeneration,23.6.63
SRC="$MADPATH/Template/NLO/SubProcesses/cuts.f"
test -f "$SRC"
grep -A32 -B2 -n -i 'logical function passcuts_fxfx' "$SRC"
python3 scripts/aqp_prepare_fxfx_exclusive_kt_patch.py --source "$SRC"

BASE="$HOME/AQP/fxfx_pr426_standard111_ab"
mkdir -p "$BASE/after_source"
python3 scripts/aqp_prepare_fxfx_exclusive_kt_patch.py \
  --source "$SRC" --output "$BASE/after_source/cuts.f" --write

sha256sum "$SRC" "$BASE/after_source/cuts.f"
```

**Stop condition:** If source shape does not match upstream 3.5.11, our helper *refuses* the patch. Do not bypass it, and do not mix versions. The output is a standalone candidate source file: **not yet installed into process or ATLAS MadGraph**.

### Process-creation and execution requirements (not yet implemented/approved)

1. Create two entirely clean (no reused integration grids) NLO process directories from the same pinned MadGraph build.
2. Before compiling or integrating the `after` process, install the patched `cuts.f` **in that generated process's actual compiled SubProcesses source path**, while leaving `before` untouched. Verify the patch has propagated to the active compiled Fortran source, not only to a detached file. Confirm generated source contains the expected function and the `amcatnlo_fastjetdmergemax` symbol exists in the old release's FastJet bridge.
3. Confirm source equivalence outside the exact PR #426 FxFx function and log before/after SHA256s; ensure no Condor `cluster.py` changes, and `run_mode=2` in both.
4. For a smoke, run fresh integration and ~200 direct-LHE events per case; capture full runtime and function-compilation logs. Then 50,000 LHE per case if successful.
5. Shower both using exactly the same Pythia8 settings; measure tried/accepted and post-shower weight handling.
6. Make a differential `\Delta R(j_1,j_2)` (especially <1) comparison at an explicitly defined level (ME partons and particle-level anti-kt jets), with statistical bands and a binwise effective-statistics diagnostic; examine high-W-pT boosted regions and inclusive jet multiplicities. Compare pre/post rates and cross sections with appropriate normalization. **Same-seed events are not generally event-by-event equivalent after code change**.
7. Do not infer a positive physics patch effect from successful generation alone. Do not use `req_acc=0.1` production output to claim precision rates.

### State of implementation

The helper `scripts/aqp_prepare_fxfx_exclusive_kt_patch.py` and its offline unit tests are in the `audit/production-framework` branch. **No live Wenu A/B process tree, new integration job, or live Condor job has yet been created/submitted by this helper.** A separate generation runner/JO is needed and must be preflighted before first submission.
