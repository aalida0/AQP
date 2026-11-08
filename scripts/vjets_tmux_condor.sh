#!/usr/bin/env bash
# Eight independent tmux Gen_tf controllers using MadGraph internal Condor.
set -euo pipefail
usage() {
  echo "Usage: bash scripts/vjets_tmux_condor.sh --check|--smoke|--start|--status"
}
(( $# == 1 )) || { usage; exit 2; }
mode=$1
case "$mode" in --check|--smoke|--start|--status) ;; *) usage; exit 2;; esac
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
packs_dir=${VJETS_GRIDPACK_ROOT:-/data/$USER/gridpacks}
work_root=${VJETS_WORK_ROOT:-$HOME/aqp-vjets-tmux-condor/10k}
out_root=${VJETS_OUT_ROOT:-/data/$USER/AQP_Vjets_tmx_condor_10k}
patchroot=${GP_PATCH_ROOT:-$repo/.condor}
socket=aqp-vjets-condor10k
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
# Validate ALL matches and workdirs before launching any session.
for rec in "${records[@]}"; do
  IFS='|' read -r proc cfg dsid seed rel sess run out <<< "$rec"
  python3 "$repo/scripts/check_sample.py" "$repo/$rel" >/dev/null
  mapfile -d '' matches < <(find "$packs_dir" -type f -name "mc_*${proc}_FxFx_2jets_*_${cfg}.MG3511.GRID.tar.gz" -print0)
  (( ${#matches[@]} == 1 )) || { echo "Expected exactly 1 gridpack for $proc $cfg, got ${#matches[@]}" >&2; printf '%s\n' "${matches[@]:-}" >&2; exit 2; }
  if tmux -L "$socket" has-session -t "$sess" 2>/dev/null || [[ -e "$run" || -e "$out" ]]; then
    echo "Existing session/work/output: $sess $run $out; refusing overwrite" >&2; exit 2
  fi
  printf '%s %-12s DSID=%s SEED=%s PACK=%s\n' "$proc" "$cfg" "$dsid" "$seed" "${matches[0]}"
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
for rec in "${records[@]}"; do
  IFS='|' read -r proc cfg dsid seed rel sess run out <<< "$rec"
  mapfile -d '' matches < <(find "$packs_dir" -type f -name "mc_*${proc}_FxFx_2jets_*_${cfg}.MG3511.GRID.tar.gz" -print0)
  pack=${matches[0]}
  mkdir -p "$run/guard" "$run/jo" "$out"
  cp -a "$repo/$rel" "$run/jo/$dsid"
  cp "$repo/scripts/vjets_tmux_condor_worker.sh" "$run/worker.sh"
  events=10000
  if [[ $mode == --smoke ]]; then events=20; fi
  printf 'repo_sha=%s\nprocess=%s\nconfig=%s\ndsid=%s\nseed=%s\nrequested_evnt=%s\ngridpack=%s\n' \
    "$git_sha" "$proc" "$cfg" "$dsid" "$seed" "$events" "$pack" > "$out/manifest.txt"
  sha256sum "$pack" > "$out/gridpack.sha256"
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
  tmux -L "$socket" new-session -d -s "$sess" -c "$run" "$cmd"
  tmux -L "$socket" set-window-option -t "$sess" remain-on-exit on 2>/dev/null || true
  printf 'LAUNCHED=%s LOG=%s/run.log\n' "$sess" "$run"
done
echo 'Monitor: tmux -L aqp-vjets-condor10k ls; condor_q "$USER"'
echo 'Status: bash scripts/vjets_tmux_condor.sh --status'
