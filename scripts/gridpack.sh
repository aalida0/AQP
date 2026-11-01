#!/usr/bin/env bash
set -euo pipefail

# Run stage: executed by a dedicated tmux server that inherits asetup.
if [[ "${1:-}" == --run ]]; then
    run=$2
    cd "$run"
    started=$(date +%s)
    printf 'start_epoch=%s\n' "$started" > timing.txt
    sha256sum "$GP_JO"/mc.*.py > jo.sha256

    rc=0
    /usr/bin/time -v -o controller_cpu.txt \
        Gen_tf.py --ecmEnergy="$GP_ECM" --maxEvents="$GP_EVENTS" \
        --firstEvent=1 --randomSeed="$GP_SEED" \
        --outputTXTFile=events.tar.gz --jobConfig="$GP_JO" \
        > generation.log 2>&1 || rc=$?

    ended=$(date +%s)
    printf 'end_epoch=%s\nwall_seconds=%s\ntransform_exit=%s\n' \
        "$ended" "$((ended-started))" "$rc" >> timing.txt

    shopt -s nullglob
    packs=(mc_*GRID.tar.gz)
    if (( rc == 0 )); then
        if (( ${#packs[@]} != 1 )) || [[ ! -s "${packs[0]:-}" ]]; then
            echo "ERROR: expected exactly one nonempty MadGraph GRID.tar.gz" >> generation.log
            rc=1
        elif ! tar -tzf "${packs[0]}" >/dev/null; then
            echo "ERROR: gridpack archive integrity check failed" >> generation.log
            rc=1
        fi
    fi

    mkdir -p "$GP_OUT"
    if (( rc == 0 )); then
        pack="${packs[0]}"
        dest="$GP_OUT/$(basename "$pack")"
        cp "$pack" "$dest.partial" && mv "$dest.partial" "$dest" && rm "$pack" || rc=1
    fi
    for file in generation.log log.generate controller_cpu.txt timing.txt jo.sha256; do
        [[ ! -f "$file" ]] || cp "$file" "$GP_OUT/"
    done
    printf 'result_exit=%s\n' "$rc" | tee -a timing.txt
    cp timing.txt "$GP_OUT/timing.txt"
    exit "$rc"
fi

# Launch stage: a fresh /home workdir (Condor-accessible); output in /data.
if (( $# < 1 || $# > 4 )); then
    echo "Usage: bash scripts/gridpack.sh JO_DIR [ecm_GeV=13000] [maxEvents=2000] [seed=12345]" >&2
    exit 2
fi

repo=$(cd "$(dirname "$0")/.." && pwd -P)
jo=$(cd "$1" && pwd -P)
[[ ( "$jo" == "$repo"/JOs/* || "$jo" == "$repo"/tests/* ) \
    && "$(basename "$jo")" =~ ^[0-9]+$ ]] || {
    echo "Expected a DSID directory under JOs/ or tests/" >&2; exit 2;
}
python3 "$repo/scripts/check_sample.py" "$jo" || exit 2
for cmd in Gen_tf.py condor_submit tmux /usr/bin/time; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "PRECHECK_FAILED: missing $cmd (check AthGeneration setup and installed tools)" >&2
        exit 2
    }
done

# The existing, source-pinned v3 candidate is still experimental.
patchroot="${GP_PATCH_ROOT:-$repo/.condor}"
candidate="$patchroot/cluster.py"
bootstrap="$patchroot/bootstrap_v3"
[[ -f "$candidate" && -f "$bootstrap/sitecustomize.py" ]] || {
    echo "Missing source-pinned Condor v3 patch/bootstrap in $patchroot" >&2; exit 2;
}
[[ "$(sha256sum "$candidate" | cut -d' ' -f1)" == ab60358a273531522835cd64c0f76acaca91faed1d426374ae8c04796ca4ef3c ]] || {
    echo "Unexpected Condor candidate hash" >&2; exit 2;
}
[[ -n "${MADPATH:-}" && -f "$MADPATH/madgraph/various/cluster.py" ]] || {
    echo "Run setupATLAS && asetup 23.6.63,AthGeneration" >&2; exit 2;
}
[[ "$(sha256sum "$MADPATH/madgraph/various/cluster.py" | cut -d' ' -f1)" == feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe ]] || {
    echo "MadGraph cluster.py differs from pinned 3.5.11 source" >&2; exit 2;
}

base="$HOME/gridpack-work"
mkdir -p "$base"
[[ "$(realpath -e "$base")" == "$(realpath -e "$HOME")"/* ]] || {
    echo "Condor workdir must be in shared HOME" >&2; exit 2;
}
name="$(basename "$(dirname "$(dirname "$jo")")")-$(basename "$(dirname "$jo")")-$(basename "$jo")"
name=$(printf '%s' "$name" | tr -c '[:alnum:]_.-' '_')
run=$(mktemp -d "$base/$name.XXXXXX")
mkdir -p "$run/jo" "$run/guard"
cp -a "$jo" "$run/jo/"
dsid=$(basename "$jo")
export GP_JO="$run/jo/$dsid"
export GP_ECM="${2:-13000}" GP_EVENTS="${3:-2000}" GP_SEED="${4:-12345}"
export GP_OUT="/data/$USER/gridpacks/$name/$(basename "$run")"
mkdir -p "$GP_OUT"
[[ -w "$GP_OUT" ]] || { echo "Cannot write output directory $GP_OUT" >&2; exit 2; }
export DATAPATH="$GP_JO:${DATAPATH:-}"
export AQP_CLUSTER_CANDIDATE="$candidate"
export AQP_CONDOR_GUARD_DIR="$run/guard"
export PYTHONPATH="$bootstrap:$(realpath -e "$MADPATH"):${PYTHONPATH:-}"

# Fail before integration if bootstrap did not actually replace cluster.py.
python -c 'import madgraph.various.cluster as c; assert hasattr(c, "_aqp_states"); print("CONDOR_BACKEND_OK")'

socket="gp-$(basename "$run")"
printf -v cmd '%q ' bash "$repo/scripts/gridpack.sh" --run "$run"
tmux -L "$socket" new-session -d -s gridpack -c "$run" "$cmd"
printf 'RUN=%s\nOUTPUT=%s\nATTACH=tmux -L %q attach -t gridpack\n' \
    "$run" "$GP_OUT" "$socket"
