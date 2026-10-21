#!/usr/bin/env bash
# Read-only audit of AQP W+jets MG5_aMC@NLO FxFx gridpack state.
set -euo pipefail

BASE="${1:-$HOME/AQP/Wjets/WENU}"
if [[ ! -d "$BASE" ]]; then
  printf 'ERROR: no W+jets directory: %s\n' "$BASE" >&2
  exit 2
fi

printf 'W+jets base: %s\nAudit date: %s\n' "$BASE" "$(date -Is)"

for cfg in standard111 delta111 delta221 delta441 delta441_backup; do
  dir="$BASE/$cfg"
  printf '\n========== %s ==========\n' "$cfg"
  if [[ ! -d "$dir" ]]; then
    printf 'Directory absent\n'
    continue
  fi

  stat -c 'Directory modified: %y' "$dir"
  proc="$(find "$dir" -mindepth 1 -maxdepth 1 -type d -name 'PROCNLO_*' -print -quit)"
  if [[ -z "$proc" ]]; then
    printf 'MG process directory: absent\n'
  else
    printf 'MG process directory: %s\n' "$proc"
    stat -c 'Process directory modified: %y' "$proc"
    sub="$proc/SubProcesses"
    if [[ -d "$sub" ]]; then
      printf 'GF directories:       '
      find "$sub" -mindepth 2 -maxdepth 2 -type d -name 'GF*' | wc -l
      printf 'results.dat nonempty: '
      find "$sub" -path '*/GF*/results.dat' -type f -size +0c | wc -l
      printf 'MINT1 logs nonempty:  '
      find "$sub" -path '*/GF*/log_MINT1.txt' -type f -size +0c | wc -l
    fi
    run_card="$proc/Cards/run_card.dat"
    if [[ -f "$run_card" ]]; then
      echo 'Relevant run-card settings:'
      grep -Ei '^[^#]*=[[:space:]]*(folding|mcatnlo_delta|req_acc)[[:space:]]*(#|$)' "$run_card" || true
    fi
  fi

  printf 'Step0 event logs: '
  find "$dir/aqp_condor_timing" -maxdepth 1 -name '*__step0.log' -type f 2>/dev/null | wc -l
  printf 'Step1 event logs: '
  find "$dir/aqp_condor_timing" -maxdepth 1 -name '*__step1.log' -type f 2>/dev/null | wc -l
  echo 'Top-level archives:'
  find "$dir" -mindepth 1 -maxdepth 1 -type f -name '*.tar.gz' -printf '  %f (%s bytes)\n'
  echo 'Recent local generation messages:'
  for log in "$dir/gridpack.log" "$dir/log.generate"; do
    if [[ -f "$log" ]]; then
      echo "  $log"
      grep -E 'Setting up grids|Computing upper envelope|All jobs finished|Generating events|FileNotFoundError|SECMAN:2007' "$log" | tail -8 || true
    fi
  done
done

printf '\n========== GRIDPACK ARCHIVES ANYWHERE UNDER WENU (depth <= 5) ==========\n'
find "$BASE" -maxdepth 5 -type f \( -name '*.GRID.tar.gz' -o -name '*GRID*.tar.gz' \) \
  -printf '%p (%s bytes)\n'

printf '\n========== ACTIVE W+JETS CONDOR JOBS ==========\n'
if command -v condor_q >/dev/null 2>&1; then
  condor_q -af ClusterId ProcId JobStatus Iwd Args 2>&1 |
    grep '/AQP/Wjets/WENU/' || true
else
  echo 'condor_q not in PATH'
fi
