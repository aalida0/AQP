#!/usr/bin/env bash
# Eight independent tmux Gen_tf controllers using MadGraph internal Condor.
set -euo pipefail
usage() {
  echo "Usage: bash scripts/vjets_tmux_condor.sh --select|--check|--smoke|--start|--status"
}
(( $# == 1 )) || { usage; exit 2; }
mode=$1
case "$mode" in --select|--check|--smoke|--start|--status) ;; *) usage; exit 2;; esac
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
packs_dir=${VJETS_GRIDPACK_ROOT:-/data/$USER/gridpacks}
work_root=${VJETS_WORK_ROOT:-$HOME/aqp-vjets-tmux-condor/10k}
out_root=${VJETS_OUT_ROOT:-/data/$USER/AQP_Vjets_tmx_condor_10k}
patchroot=${GP_PATCH_ROOT:-$repo/.condor}
socket=aqp-vjets-condor10k
selection_file=${VJETS_GRIDPACK_SELECTION:-$out_root/gridpacks.selected.tsv}
configs=(standard111 delta111 delta221 delta441)
records=()
for proc in Zee Wenu; do
  for i in "${!configs[@]}"; do
    cfg=${configs[i]}
    if [[ $proc == Zee ]]; then
      dsid=$((100000+i)); seed=$((481001+i))
      jo_rel="JOs/V+jets/Z+jets/Z(ee)/$cfg/$dsid"
    else
      dsid=$((200000+i)); seed=$((481101+i))
      jo_rel="JOs/V+jets/W+jets/W(ev)/$cfg/$dsid"
    fi
    session="aqp-${proc,,}-$cfg-10k"
    records+=("$proc|$cfg|$dsid|$seed|$jo_rel|$session|$work_root/$proc/$cfg|$out_root/$proc/$cfg")
  done
done

# Strictly match the current 2-jet HT2 gridpacks, excluding older HT2bias
# candidates. Never guess between original and clean_v2 copies.
candidates_for() {
  local proc=$1 cfg=$2
  find "$packs_dir" -type f \
    -name "mc_*${proc}_FxFx_2jets_HT2_${cfg}.MG3511.GRID.tar.gz" -print0 | sort -z
}
resolve_pack() {
  local proc=$1 cfg=$2 selection match found=0
  local -a candidates=() chosen=()
  mapfile -d '' candidates < <(candidates_for "$proc" "$cfg")
  if [[ -s "$selection_file" ]]; then
    mapfile -t chosen < <(awk -F '\t' -v p="$proc" -v c="$cfg" \
      '$1==p && $2==c {print $3}' "$selection_file")
    (( ${#chosen[@]} == 1 )) || {
      echo "Expected one manifest entry for $proc $cfg in $selection_file" >&2; return 2;
    }
    selection=${chosen[0]}
    for match in "${candidates[@]}"; do
      [[ "$selection" == "$match" ]] && found=$((found + 1))
    done
    (( found == 1 )) || {
      echo "Manifest path missing/wrong for $proc $cfg: $selection" >&2; return 2;
    }
  else
    (( ${#candidates[@]} == 1 )) || {
      echo "Found ${#candidates[@]} gridpacks for $proc $cfg. Run --select to pin one:" >&2
      printf '%s\n' "${candidates[@]}" >&2
      return 2
    }
    selection=${candidates[0]}
  fi
  printf '%s\n' "$selection"
}
if [[ $mode == --select ]]; then
  [[ -d "$packs_dir" ]] || { echo "Missing $packs_dir" >&2; exit 2; }
  [[ -t 0 ]] || { echo "--select needs an interactive terminal" >&2; exit 2; }
  mkdir -p "$(dirname "$selection_file")"
  tmp=$(mktemp "${selection_file}.tmp.XXXXXX")
  trap 'rm -f "$tmp"' EXIT
  for rec in "${records[@]}"; do
    IFS='|' read -r proc cfg dsid seed rel sess run out <<< "$rec"
    mapfile -d '' choices < <(candidates_for "$proc" "$cfg")
    (( ${#choices[@]} > 0 )) || { echo "No gridpack for $proc $cfg" >&2; exit 2; }
    if (( ${#choices[@]} == 1 )); then
      selected=${choices[0]}
    else
      echo "Choose a verified gridpack for $proc $cfg (do not assume clean_v2 is correct):"
      for j in "${!choices[@]}"; do
        printf ' %s) %s\n' "$((j+1))" "${choices[j]}"
      done
      read -r -p "Selection [1-${#choices[@]}]: " index
      [[ "$index" =~ ^[0-9]+$ ]] && (( index >= 1 && index <= ${#choices[@]} )) || {
        echo "Invalid selection" >&2; exit 2;
      }
      selected=${choices[index-1]}
    fi
    printf '%s\t%s\t%s\n' "$proc" "$cfg" "$selected" >> "$tmp"
  done
  mv -f "$tmp" "$selection_file"
  trap - EXIT
  echo "Wrote explicit gridpack selection: $selection_file"
  echo "Review with: cat $selection_file"
  exit 0
fi
if [[ $mode == --status ]]; then
  for rec in "${records[@]}"; do
    IFS='|' read -r proc cfg dsid seed rel sess run out <<< "$rec"
    state="NO_TMUX"
    if tmux -L "$socket" has-session -t "$sess" 2>/dev/null; then state="TMUX_PRESENT"; fi
    if [[ -f "$out/exit_code.txt" ]]; then state+=" exit=$(cat "$out/exit_code.txt")"; fi
    printf '%-25s %s\n' "$sess" "$state"
  done
  echo 'Smoke:'
  [[ -f "$out_root/smoke/Wenu/delta111/exit_code.txt" ]] && cat "$out_root/smoke/Wenu/delta111/exit_code.txt" || true
  exit 0
fi
if [[ $mode == --smoke ]]; then
  records=("Wenu|delta111|200001|481901|JOs/V+jets/W+jets/W(ev)/delta111/200001|aqp-wenu-delta111-smoke|$work_root/smoke/Wenu/delta111|$out_root/smoke/Wenu/delta111")
fi
for cmd in Gen_tf.py tmux condor_submit python3; do
  command -v "$cmd" >/dev/null || { echo "Missing $cmd: setup AthGeneration,23.6.63 first" >&2; exit 2; }
done
[[ -n "${MADPATH:-}" && -f "$MADPATH/madgraph/various/cluster.py" ]] || {
  echo "MADPATH unavailable; run asetup AthGeneration,23.6.63" >&2; exit 2;
}
candidate="$patchroot/cluster.py"
bootstrap="$patchroot/bootstrap_v3/sitecustomize.py"
[[ -s "$candidate" && -s "$bootstrap" ]] || { echo "Missing validated .condor bootstrap: $patchroot" >&2; exit 2; }
[[ "$(sha256sum "$candidate" | cut -d' ' -f1)" == ab60358a273531522835cd64c0f76acaca91faed1d426374ae8c04796ca4ef3c ]] || {
  echo "Condor patch has unexpected SHA256" >&2; exit 2;
}
[[ "$(sha256sum "$MADPATH/madgraph/various/cluster.py" | cut -d' ' -f1)" == feb07ff8af81eb5524ee810d6f4976502457fdf45106a9e2702d1ea46b7ef7fe ]] || {
  echo "Different MadGraph cluster.py version" >&2; exit 2;
}
export PYTHONPATH="$(dirname "$bootstrap"):$(realpath -e "$MADPATH"):${PYTHONPATH:-}"
export AQP_CLUSTER_CANDIDATE="$candidate"
python3 -c 'import madgraph.various.cluster as c; assert hasattr(c,"_aqp_states"); print("CONDOR_BACKEND_OK")'
[[ -d "$packs_dir" ]] || { echo "Missing $packs_dir" >&2; exit 2; }
# Validate all eight selected packs and workdirs before launching any session.
resolved_records=()
for rec in "${records[@]}"; do
  IFS='|' read -r proc cfg dsid seed rel sess run out <<< "$rec"
  python3 "$repo/scripts/check_sample.py" "$repo/$rel" >/dev/null
  pack=$(resolve_pack "$proc" "$cfg") || exit 2
  if tmux -L "$socket" has-session -t "$sess" 2>/dev/null || [[ -e "$run" || -e "$out" ]]; then
    echo "Existing session/work/output: $sess $run $out; refusing overwrite" >&2; exit 2
  fi
  resolved_records+=("$rec|$pack")
  printf '%s %-12s DSID=%s SEED=%s PACK=%s\n' "$proc" "$cfg" "$dsid" "$seed" "$pack"
done
if [[ $mode == --check ]]; then
  echo "PREFLIGHT_OK: eight gridpacks and JOs" 
  df -h "$HOME" "$packs_dir"
  exit 0
fi
if [[ $mode == --start && ${VJETS_CONFIRMED_SMOKE:-0} != 1 ]]; then
  echo 'Run --smoke, verify internal Condor success, then set VJETS_CONFIRMED_SMOKE=1' >&2; exit 2
fi
mkdir -p "$work_root" "$out_root"
home_real=$(realpath -e "$HOME"); work_real=$(realpath -e "$work_root")
case "$work_real" in "$home_real"/*) ;; *) echo "Workdir must be in shared HOME" >&2; exit 2;; esac
git_sha=$(git -C "$repo" rev-parse HEAD)
for rec in "${resolved_records[@]}"; do
  IFS='|' read -r proc cfg dsid seed rel sess run out pack <<< "$rec"
  mkdir -p "$run/guard" "$run/jo" "$out"
  cp -a "$repo/$rel" "$run/jo/$dsid"
  cp "$repo/scripts/vjets_tmux_condor_worker.sh" "$run/worker.sh"
  events=10000
  if [[ $mode == --smoke ]]; then events=20; fi
  printf 'repo_sha=%s\nprocess=%s\nconfig=%s\ndsid=%s\nseed=%s\nrequested_evnt=%s\ngridpack=%s\n' \
    "$git_sha" "$proc" "$cfg" "$dsid" "$seed" "$events" "$pack" > "$out/manifest.txt"
  # Never block a controller launch hashing multi-GB archives on shared /data.
  # Record path, size and mtime; users can compute the full SHA256 offline.
  stat -Lc 'gridpack_size_bytes=%s\ngridpack_mtime_epoch=%Y' "$pack" > "$out/gridpack.stat"
  printf '%s\n' "$pack" > "$out/gridpack.path"
  sha256sum "$run/jo/$dsid"/mc.*.py > "$out/jo.sha256"
  # Per-session environment is essential: tmux servers retain their first environment.
  {
    for spec in "VJETS_RUN:$run" "VJETS_OUT:$out" "VJETS_PACK:$pack" \
      "VJETS_SEED:$seed" "VJETS_PROC:$proc" "VJETS_CFG:$cfg" \
      "VJETS_DSID:$dsid" "VJETS_EVENTS:$events" \
      "AQP_CONDOR_GUARD_DIR:$run/guard" "AQP_CLUSTER_CANDIDATE:$candidate" \
      "PYTHONPATH:${PYTHONPATH:-}" "MADPATH:${MADPATH:-}" \
      "PY8PATH:${PY8PATH:-}" "DATAPATH:$run/jo/$dsid:${DATAPATH:-}"; do
      name=${spec%%:*}; value=${spec#*:}
      printf 'export %s=%q\n' "$name" "$value"
    done
    echo 'export EVENT_USE_CONDOR=1'
  } > "$run/session_env.sh"
  chmod 600 "$run/session_env.sh"
  printf -v cmd 'bash %q %q' "$run/worker.sh" "$run/session_env.sh"
  # Create a persistent shell, configure exit preservation, THEN run worker.
  # Otherwise a fast worker failure can destroy the tmux session before
  # remain-on-exit is set, erasing the reason for failure.
  tmux -L "$socket" new-session -d -s "$sess" -c "$run"
  tmux -L "$socket" set-window-option -t "$sess" remain-on-exit on
  tmux -L "$socket" send-keys -t "$sess" "$cmd" C-m
  printf 'LAUNCHED=%s LOG=%s/run.log\n' "$sess" "$run"
done
echo 'Monitor: tmux -L aqp-vjets-condor10k ls; condor_q "$USER"'
echo 'Status: bash scripts/vjets_tmux_condor.sh --status'
