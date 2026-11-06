#!/usr/bin/env bash
# Launch the Zee and charge-inclusive Wenu Delta111 0+1j gridpack smokes.
# Each gridpack.sh call creates its own detached tmux server and socket.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd -P)
[[ -n "${MADPATH:-}" ]] || { echo "Set up AthGeneration/23.6.63 first" >&2; exit 2; }
[[ -n "${PY8PATH:-}" && -f "$PY8PATH/lib/libpythia8.a" ]] || {
    echo "MC@NLO-Delta requires PY8PATH/lib/libpythia8.a" >&2; exit 2;
}
for dsid in 910101 910102; do
    python3 "$repo/scripts/check_sample.py" "$repo/tests/1jet/$dsid"
    jo=("$repo"/tests/1jet/"$dsid"/mc.*.py)
    (( ${#jo[@]} == 1 )) || { echo "Expected exactly one JO in $dsid" >&2; exit 2; }
    grep -q '^REQUIRED_ACCURACY = 0.5 ' "${jo[0]}" || { echo "Expected accuracy 0.5 in $dsid" >&2; exit 2; }
done
mkdir -p "$HOME/vjets-1jet-launches"
records=$(mktemp -d "$HOME/vjets-1jet-launches/launch.XXXXXXXX")
echo "LAUNCH_RECORDS=$records"
for dsid in 910101 910102; do
    echo "===== Submitting smoke gridpack for $dsid; randomSeed=$dsid ====="
    bash "$repo/scripts/gridpack.sh" "$repo/tests/1jet/$dsid" 13000 20 "$dsid" \
      | tee "$records/$dsid.launch.txt"
done
echo "BOTH_GRIDPACK_TMUX_LAUNCHED"
echo "Each ATTACH command is recorded in $records/{910101,910102}.launch.txt"
echo "Closing SSH will not interrupt either detached tmux/controller session."
