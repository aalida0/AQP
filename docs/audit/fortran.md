# Fortran modifications

Direct comparison used the installed 3.5.11 templates ([MG03](evidence.md#mg03), [MG04](evidence.md#mg04)). Original companion files in `100000`–`100003` and central generated copies in `standard111`, `delta111`, `delta221`, and `delta441_backup` have identical hashes for each modified file.

| File | Confirmed executable change | Validation required |
|---|---|---|
| `dummy_fct.f` | Activates the template's commented HT² bias example: square of the sum of transverse energies over **all outgoing legs**, including charged leptons and neutrinos ([E08](evidence.md#e08):86–91). Custom cuts and the user scale function remain stock (:37,68–70). | Hand-constructed kinematic fixtures, soft/collinear limits, zero-bias rejection and end-to-end bias-compensation closure. Do not describe this as a jet-only HT bias or a custom dynamical-scale implementation. |
| `montecarlocounter_MINE.f` → `montecarlocounter.f` | Adds an upper tolerance `100*epsilon(1d0)` for a Sudakov probability and clamps accepted excursions above unity to unity. Negative values and larger upper excursions still terminate ([E09](evidence.md#e09):1561,2300–2311). | Boundary fixtures below zero, at zero/unity, within the upper tolerance, and above it; compare patched/unpatched behavior and count clamp activations in a future isolated validation. Physical adequacy is unestablished. |

SHA256 identities:

- `dummy_fct.f`: `76f47c8fdfacd7d2136f13e5261765ab27aae21752448cae0cb4d05120e9fc08`.
- Counter source: `fee80cac03c15fc5e7b85c791dbb4f7b284fb004faec47b2e3c6a33c9a861f0a`.

**Confirmed integration path.** Generated `fks_singular.f` matches the installed template. Its bias branch multiplies real/Born integration weights and its inverse-bias routine rejects zero bias ([E10](evidence.md#e10):2082–2109,2150–2153). The inspected pole-check threshold remains positive ([E07](evidence.md#e07):22–23). These facts do not establish numerical closure of the modified production.

**High-priority provenance gap.** Clean-gridpack preparation builds/checks `collect_events` only ([E14](evidence.md#e14):96–102). Source identity and existing object files do not prove which compiled integration executables produced the saved grids. No stale-object defect was demonstrated. Require a source/compiler/flags/object/executable manifest and a fresh isolated build before interpreting numerical patch comparisons.
