#!/usr/bin/env bash
# FxFx Standard111 PR426 A/B: generate 50k LHE from EXISTING integrated NLO grids.
# This does not recompile or repeat MINT0/MINT1 and does not use gridpacks.
# By default does preflight only; --execute launches generation.
set -Eeuo pipefail

CASE="${1:-}"
WORK="${2:-}"
MODE="${3:---check}"
case "$CASE" in before|after) ;; *) echo "Usage: $0 before|after ABSOLUTE_WORKDIR [--execute]" >&2; exit 2 ;; esac
case "$MODE" in --check|--execute) ;; *) echo "ERROR: expected --check or --execute" >&2; exit 2 ;; esac
[[ "$WORK" == /* && -d "$WORK" ]] || { echo "ERROR: absolute existing workdir required" >&2; exit 2; }
WORK="$(realpath "$WORK")"
case "$WORK/" in /home/aalida/AQP/fxfx_pr426_standard111_internal/*) ;; *)
  echo "ERROR: refusing workdir outside isolated FxFx PR426 tree" >&2; exit 3 ;;
esac
ROOT=/home/aalida/AQP/aqp-production-audit
PROCDIR="$WORK/PROCNLO_loop_sm-no_b_mass_0"
python3 "$ROOT/scripts/check_wenu_fxfx_pr426_saved_grids.py" "$CASE" "$WORK"

RUN=run_pr426_50k_seed411
OUT="$WORK/only_generation_$RUN"
CARD="$PROCDIR/Cards/run_card.dat"
PREVIOUS="$OUT/run_card.before_50k.dat"
[[ ! -e "$PROCDIR/Events/$RUN" ]] || {
  echo "ERROR: existing run: $PROCDIR/Events/$RUN" >&2; exit 4;
}
if [[ "$MODE" == "--check" ]]; then
  echo "AQP_FXFX_AB_ONLY_GENERATION_PREFLIGHT_PASS"
  echo "Plan: nevents=50000, iseed=411, no scale/PDF variations"
  echo "Command: launch -f -c -p -o -x --name=$RUN"
  echo "This skips MINT0/MINT1; prior grids and 200 LHE retained."
  exit 0
fi

[[ ! -e "$OUT" && ! -L "$OUT" ]] || {
  echo "ERROR: existing only-generation output path: $OUT" >&2; exit 5;
}
[[ -n "$(printenv MADPATH || true)" ]] || {
  echo "ERROR: first load AthGeneration,23.6.63" >&2; exit 6;
}
for command in condor_q flock python3; do
  command -v "$command" >/dev/null || { echo "Missing $command" >&2; exit 6; }
done
mkdir -p "$OUT"
exec 8>"$WORK/.aqp_pr426_only_generation.lock"
flock -n 8 || { echo "ERROR: another only_generation holds workdir lock" >&2; exit 7; }

cp -p "$CARD" "$PREVIOUS"
python3 - "$CARD" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1])
src=p.read_text()
updates={"nevents":"50000","iseed":"411","systematics_program":"none","lhaid":"325100"}
for key,value in updates.items():
    pattern=re.compile(r"(?mi)^(\s*)([^=\n!#]*)(\s*=\s*"+re.escape(key)+r"\b[^\n]*)$")
    matches=list(pattern.finditer(src))
    if not matches:
        if key in ("nevents","iseed","lhaid"):
            raise SystemExit("REQUIRED_RUN_CARD_KEY_MISSING "+key)
        continue
    src,n=pattern.subn(lambda m: m.group(1)+value+m.group(3),src)
    if n!=len(matches):
        raise SystemExit("RUN_CARD_REWRITE_COUNT_ERROR "+key)
p.write_text(src)
print("AQP_PR426_RUN_CARD_50K_READY")
PY

# On a failed/aborted scheduler run the modified card is intentionally left
# in place; do NOT automatically retry or restore before reconciling workers.
unset ATHENA_CORE_NUMBER
export OMP_NUM_THREADS=1
COMMAND="launch -f -c -p -o -x --name=$RUN"
printf '%s\n' "$COMMAND" > "$OUT/command.txt"
printf '%s\n' "$PROCDIR" > "$OUT/process_path.txt"
echo "AQP_FXFX_PR426_ONLY_GENERATION_START $CASE"
echo "BACKUP=$PREVIOUS"
echo "WARNING: MG internal Condor remains unpatched. Check child jobs on failure."

set +e
(
  cd "$PROCDIR"
  python3 ./bin/aMCatNLO "$OUT/command.txt"
) > "$OUT/aMCatNLO_only_generation.log" 2>&1
ret=$?
set -e
printf '%s\n' "$ret" > "$OUT/aMCatNLO_exit_code"
if [[ "$ret" -ne 0 ]]; then
    tail -n 80 "$OUT/aMCatNLO_only_generation.log" >&2
    exit "$ret"
fi
EVENT="$PROCDIR/Events/$RUN/events.lhe.gz"
if [[ ! -s "$EVENT" ]]; then
    echo "ERROR: no LHE at $EVENT" >&2
    exit 10
fi
python3 - "$EVENT" <<'PY'
from pathlib import Path
import gzip,sys,re
path=Path(sys.argv[1]); beg=end=0; closed=False
with gzip.open(path,"rt",errors="replace") as stream:
    for line in stream:
        beg += bool(re.fullmatch(r"<event(?:\s[^>]*)?>", line.strip()))
        end += bool(re.fullmatch(r"</event\s*>", line.strip()))
        closed|="</LesHouchesEvents>" in line
if (beg,end)!=(50000,50000) or not closed:
    raise SystemExit(f"LHE_BAD_EVENT_COUNT {beg}/{end}, closed={closed}")
print("AQP_FXFX_PR426_50000_LHE_PASS",beg)
PY
sha256sum "$EVENT" > "$OUT/events.lhe.gz.sha256"
echo "AQP_FXFX_PR426_ONLY_GENERATION_50K_PASS $CASE"
echo "LHE=$EVENT"
