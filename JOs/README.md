# JobOptions

Directory names describe the physics channel; inside each channel, keep
`<configuration>/<DSID>/mc.*.py` and its process-local `.f` and
`.patch` files. Each JO remains a complete standalone Python source
suitable for PMG review.

Use a separate `event_generation/grid_submit_<configuration>/<DSID>/`
for the matching Grid JO. Keep the top-level `grid/`, `runtime/`,
and `rivet/` stages independent of the JO source tree.
