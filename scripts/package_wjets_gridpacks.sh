#!/usr/bin/env bash
# Package existing W+jets MG5 3.5.11 process directories without touching source
# files or consuming home-directory disk space for intermediate archives.
# Usage: bash package_wjets_gridpacks.sh standard111 delta111 delta221
# Optional: AQP_WENU_HOME=... AQP_WENU_DATA=...
set -euo pipefail

BASE="${AQP_WENU_HOME:-$HOME/AQP/Wjets/WENU}"
DEST="${AQP_WENU_DATA:-/data/$USER/AQP/Wjets/WENU/gridpacks}"
PROC_NAME="PROCNLO_loop_sm-no_b_mass_0"
TMPFILE=""

cleanup() {
  if [[ -n "$TMPFILE" && -e "$TMPFILE" ]]; then
    rm -f -- "$TMPFILE"
  fi
}
trap cleanup EXIT

if (( $# == 0 )); then
  echo "Usage: $0 standard111 [delta111] [delta221]" >&2
  echo "delta441_backup is deliberately not eligible yet." >&2
  exit 2
fi

if [[ ! -d "$BASE" ]]; then
  echo "ERROR: source base not found: $BASE" >&2
  exit 1
fi
mkdir -p "$DEST"
DEST_REAL="$(realpath -e "$DEST")"
case "$DEST_REAL" in
  /data/*) ;;
  *) echo "ERROR: destination must be under /data, got $DEST_REAL" >&2; exit 1;;
esac

echo "Source base: $BASE"
echo "Archive output: $DEST_REAL"
df -h "$DEST_REAL"
for CFG in "$@"; do
  case "$CFG" in
    standard111|delta111|delta221) ;;
    *) echo "ERROR: unknown or not-yet-validated configuration: $CFG" >&2; exit 2;;
  esac

  SRC="$BASE/$CFG/$PROC_NAME"
  if [[ ! -d "$SRC" ]]; then
    echo "ERROR: missing process: $SRC" >&2
    exit 1
  fi
  if [[ ! -s "$SRC/SubProcesses/job_status.pkl" ||
        ! -s "$SRC/Events/run_01/events.lhe.gz" ]]; then
    echo "ERROR: source does not have saved job-state and combined LHE: $CFG" >&2
    exit 1
  fi

  TARGETS="$(find "$SRC/SubProcesses" -mindepth 2 -maxdepth 2 -type d -name 'GF*' | wc -l)"
  if [[ "$TARGETS" -ne 300 ]]; then
    echo "ERROR: expected 300 GF targets for $CFG, got $TARGETS" >&2
    exit 1
  fi

  NAME="mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_${CFG}.MG3511.GRID.tar.gz"
  FINAL="$DEST_REAL/$NAME"
  if [[ -e "$FINAL" || -L "$FINAL" ]]; then
    echo "SKIP $CFG: archive already exists: $FINAL"
    continue
  fi
  TMPFILE="$(mktemp "$DEST_REAL/.${NAME}.partial.XXXXXXXX")"
  echo "Packaging $CFG from $SRC ..."
  # Rewrites only member names, not relative symlink targets.
  # No temp archive is created in /home.
  tar -czf "$TMPFILE" \
    --transform="flags=r;s@^${PROC_NAME}@madevent@" \
    -C "$BASE/$CFG" "$PROC_NAME"

  # Full archive listing also forces gzip decompression/CRC validation.
  # awk must read all records to avoid SIGPIPE under pipefail.
  if ! tar -tzf "$TMPFILE" | awk '
    $0=="madevent/" {root=1}
    $0=="madevent/SubProcesses/" {sub=1}
    $0=="madevent/Cards/run_card.dat" {card=1}
    END { if (!(root && sub && card)) exit 1 }
  '; then
    echo "ERROR: archive missing required structure or unreadable: $CFG" >&2
    exit 1
  fi

  # Hard link atomically claims the final filename without overwriting it.
  ln -- "$TMPFILE" "$FINAL"
  rm -f -- "$TMPFILE"
  TMPFILE=""
  sha256sum "$FINAL" > "$FINAL.sha256"
  echo "SUCCESS: $FINAL"
  ls -lh "$FINAL" "$FINAL.sha256"
done
echo "Finished. Source process directories were not modified."
