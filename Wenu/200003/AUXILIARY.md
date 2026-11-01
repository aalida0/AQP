# Process-local Fortran auxiliary files

Place any validated process-specific `.f` source overrides *in this directory*, beside the JO and patch files. A JO can fetch them by basename using `get_files -data <name>`, then copy them into the newly generated MadGraph process before compilation.

For example, HT2-biased samples may need `dummy_fct.f` and a pinned `montecarlocounter.f` replacement. This illustrative Wenu configuration has **no HT2 bias** and deliberately contains no Fortran source override. Whole-file replacements must be version- and hash-checked independently.
