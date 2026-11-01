# Runtime and efficiency

`parsers/`: read MadGraph/Condor integration logs and grid
log.generate archives. Track core-hours and wall time separately,
CPU resource accounting, evictions/retries, FxFx acceptance and weighted
vs raw negative-weight fractions. Normalize comparisons at matched
accepted-event counts.

`reports/`: generate CSV/LaTeX tables with provenance and uncertainty
definitions. This stage is a placeholder.
