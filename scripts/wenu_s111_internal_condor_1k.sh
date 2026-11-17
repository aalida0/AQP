#!/usr/bin/env bash
# Live 1k Wenu Standard111 FxFx pilot using MadGraph internal Condor (run_mode=1).
# Run the Athena controller from /home; MadGraph dispatches ME jobs to Condor.
# No set -e, set -u or pipefail. Existing gridpack is read-only on /data.

REPO=$(cd "$(dirname "$0")/.." && pwd -P) || exit 2
JO="$REPO/tests/wenu_s111_patched_condor_pilot/299903"
GP="/data/$USER/gridpacks/tests-wenu_s111_patched_explicit_seed-299901/tests-wenu_s111_patched_explicit_seed-299901.5ZTi6X/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2_standard111_seedcheck.MG3511.GRID.tar.gz"
PATCHROOT="${GP_PATCH_ROOT:-$REPO/.condor}"
CANDIDATE="$PATCHROOT/cluster.py"
BOOTSTRAP="$PATCHROOT/bootstrap_v3"
OUT="/data/$USER/AQP/Wenu_S111_seed817263_condor_1k"

if [[ ! -d "$JO" || ! -s "$GP" ]]; then
    echo "ERROR: missing 299903 JO directory or source gridpack" >&2
    exit 2
fi
python3 "$REPO/scripts/check_sample.py" "$JO" || exit 2
python3 "$REPO/scripts/test_wenu_condor_query_v2.py" || exit 2
for cmd in Gen_tf.py condor_submit python3 sha256sum; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: $cmd not available. Setup AthGeneration 23.6.63." >&2
        exit 2
    fi
done

if [[ ! -f "$CANDIDATE" || ! -f "$BOOTSTRAP/sitecustomize.py" ]]; then
    echo "ERROR: missing existing pinned Condor backend under $PATCHROOT" >&2
    exit 2
fi
if [[ "$(sha256sum "$CANDIDATE" | cut -d' ' -f1)" != "ab60358a273531522835cd64c0f76acaca91faed1d426374ae8c04796ca4ef3c" ]]; then
    echo "ERROR: Condor backend differs from the tested source-pin" >&2
    exit 2
fi
if [[ -z "${MADPATH:-}" || ! -f "$MADPATH/madgraph/various/cluster.py" ]]; then
    echo "ERROR: MADPATH missing: run setupATLAS && asetup AthGeneration,23.6.63" >&2
    exit 2
fi
if [[ "$(sha256sum "$MADPATH/madgraph/various/cluster.py" | cut -d' ' -f1)" != "feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe" ]]; then
    echo "ERROR: MadGraph cluster.py version differs from pinned MG5 3.5.11" >&2
    exit 2
fi

BASE="$HOME/gridpack-work"
mkdir -p "$BASE" || exit 2
RUN=$(mktemp -d "$BASE/WenuS111_condor1k.XXXXXX") || exit 2
# Keep every failed/successful attempt independently for reproducibility.
OUT="$OUT/$(basename "$RUN")"
mkdir -p "$RUN/guard" "$RUN/backend" || exit 2
cp -a "$JO" "$RUN/" || exit 2
python3 "$REPO/scripts/build_wenu_condor_query_v2.py" \
    "$CANDIDATE" "$RUN/backend/cluster.py" || exit 2
python3 "$REPO/scripts/build_wenu_condor_bootstrap_v2.py" \
    "$BOOTSTRAP" "$RUN/backend/cluster.py" "$RUN/bootstrap" || exit 2
cd "$RUN" || exit 2

export DATAPATH="$RUN/299903:${DATAPATH:-}"
export AQP_CLUSTER_CANDIDATE="$RUN/backend/cluster.py"
export AQP_CONDOR_GUARD_DIR="$RUN/guard"
export PYTHONPATH="$RUN/bootstrap:$(realpath -e "$MADPATH"):${PYTHONPATH:-}"

# Verify that the patched backend is actually imported, not only staged.
python3 -c 'import madgraph.various.cluster as c; assert hasattr(c, "_aqp_states"); assert getattr(c._aqp_query, "_wenu_query_v2", False); print("CONDOR_BACKEND_QUERY_V2_OK", c.__file__)' || exit 2

echo "RUN=$RUN"
echo "INPUT_GRIDPACK=$GP"
echo "OUTPUT=$OUT"
sha256sum "$GP" > gridpack.sha256 || exit 2
sha256sum 299903/mc.*.py > jo.sha256 || exit 2

echo "Extracting input gridpack into /home workdir (Condor-visible)..."
tar -xzf "$GP" > gridpack_extract.log 2>&1
rc=$?
if (( rc != 0 )) || [[ ! -s madevent/Cards/run_card.dat || ! -f madevent/bin/aMCatNLO ]]; then
    echo "ERROR: gridpack extraction failed: rc=$rc" >&2
    tail -50 gridpack_extract.log
    exit 3
fi

printf 'run=%s\nintegration_seed=817263\nshower_seed=928431\nrequested_events=1000\nrun_mode=1\ncluster_size=100\n' "$RUN" > pilot_metadata.txt
echo "STARTING: internal Condor parton generation + Athena/Pythia8 shower"
started=$(date +%s)
Gen_tf.py --ecmEnergy=13000 --maxEvents=1000 \
    --randomSeed=928431 --firstEvent=1 --jobConfig=299903 \
    --outputEVNTFile=EVNT.pool.root 2>&1 | tee run.log
pipeline_rc=("${PIPESTATUS[@]}")
rc="${pipeline_rc[0]}"
if (( rc == 0 && pipeline_rc[1] != 0 )); then rc="${pipeline_rc[1]}"; fi
printf 'elapsed_seconds=%s\ntransform_exit=%s\n' "$(( $(date +%s ) - started ))" "$rc" >> pilot_metadata.txt

mkdir -p "$OUT" || exit 4
for f in run.log log.generate pilot_metadata.txt gridpack.sha256 jo.sha256; do
    if [[ -f "$f" ]]; then
        cp -f "$f" "$OUT/" || echo "WARNING: could not copy $f to $OUT" >&2
    fi
done

if (( rc != 0 )); then
    echo "ERROR: generation failed (exit $rc); logs copied to $OUT" >&2
    exit "$rc"
fi
if [[ ! -s EVNT.pool.root || ! -s log.generate ]]; then
    echo "ERROR: generation completed without EVNT.pool.root or log.generate" >&2
    exit 5
fi
if [[ -e "$OUT/EVNT.pool.root" ]]; then
    echo "ERROR: EVNT already exists in output directory; refusing overwrite" >&2
    exit 6
fi
cp -p EVNT.pool.root "$OUT/EVNT.pool.root.partial" || exit 7
mv "$OUT/EVNT.pool.root.partial" "$OUT/EVNT.pool.root" || exit 7
echo "PILOT_SUCCESS: $OUT/EVNT.pool.root"
