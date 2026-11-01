# Source patch inventory

- `fxfx_exclusive_kt.patch`: upstream MG5_aMC PR #426 (merged 2026-09-28), reformatted to patch a *generated* `SubProcesses/cuts.f`. Corrects MadGraph inclusive-jet count vs Pythia exclusive-kT FxFx mismatch. **Must be dry-run tested and physics validated against the pinned MG5 3.5.11.**
- `delta_tolerance.patch`: **MISSING**. Add the previously verified numerical-tolerance fix, specifically pinned to the correct source, before enabling this Delta441 example. Do not invent a threshold or skip an expected patch.
- Condor `cluster.py`: the verified runtime candidate is maintained on a separate test branch. Once approved, place its source-pinned runtime patch/launcher alongside this JO. Unlike Fortran source patches, the Condor backend needs to be bootstrapped by the AF **before Athena/MG5 imports**.

The JO calls `get_files -data` to retrieve each required source patch by filename, then `patch --dry-run --forward -p1` followed by `patch --forward -p1` in the fresh process directory. A missing/reversed/incompatible patch must abort the build. Never change CVMFS or modify production inputs in place.

For manual verification, from the DSID directory:

```bash
patch --dry-run --batch --forward -p1 -d "$PROC_DIR" -i "$PWD/fxfx_exclusive_kt.patch"
```
