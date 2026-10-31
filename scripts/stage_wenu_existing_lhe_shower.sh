#!/usr/bin/env bash
# Read-only preflight for three recovered Wenu LHEs, then write pinned manifest
# under audit checkout. STAGES only: never calls condor_submit or Gen_tf.
set -Eeuo pipefail
ROOT=/home/aalida/AQP/aqp-production-audit
WENU=/home/aalida/AQP/Wjets/WENU
STAGE="$ROOT/.aqp_staged/wenu_existing_lhe_shower_v1"
OUT=/data/aalida/AQP/Wjets/WENU/production_pilot/wenu_recovered_lhe_shower_v1
[[ -d "$ROOT/.git" ]] || { echo "ERROR: missing expected audit checkout" >&2; exit 2; }
[[ ! -e "$STAGE" ]] || { echo "ERROR: preflight already staged: $STAGE" >&2; exit 3; }
command -v condor_submit >/dev/null || { echo "ERROR: condor_submit unavailable" >&2; exit 4; }
bash -n "$ROOT/scripts/run_wenu_existing_lhe_shower.sh"
python3 -B - "$ROOT/joboptions/wenu_existing_lhe_shower" <<'PY'
import pathlib, sys
base = pathlib.Path(sys.argv[1])
for cfg in ("standard111", "delta111", "delta221"):
    p = base / cfg / "100004" / ("mc.aMCPy8EG_Wenu_FxFx_2jets_%s_shower.py" % cfg)
    s = p.read_text()
    compile(s, str(p), "exec")
    if "AQP_FXFX_SHOWER_MADGRAPH_NOT_INVOKED" not in s:
        raise SystemExit("Missing no-MadGraph marker in " + str(p))
    if "generate(" in s or "MadGraphControl" in s:
        raise SystemExit("Forbidden MadGraph generation in " + str(p))
print("AQP_WENU_THREE_JOS_COMPILE_AND_NO_MADGRAPH_CHECK_PASS")
PY
for CFG in standard111 delta111 delta221; do
  SRC="$WENU/$CFG/PROCNLO_loop_sm-no_b_mass_0/Events/run_01/events.lhe.gz"
  [[ -s "$SRC" ]] || { echo "ERROR: missing $SRC" >&2; exit 5; }
  [[ ! -e "$OUT/$CFG" ]] || { echo "ERROR: existing output for $CFG" >&2; exit 6; }
  gzip -t "$SRC" || { echo "ERROR: damaged source gzip $CFG" >&2; exit 7; }
  # Independent read-only structural check; no extraction or grid activity.
  RESULT="$(gzip -cd "$SRC" | awk '
     /^[[:space:]]*<event([[:space:]>])/ {a++}
     /^[[:space:]]*<\/event[[:space:]]*>/ {b++}
     /<\/LesHouchesEvents>/ {end=1}
     END {printf "%d %d %d\n",a,b,end}
  ')"
  [[ "$RESULT" == '1000 1000 1' ]] || {
    echo "ERROR: $CFG LHE count/closing marker unexpected: $RESULT" >&2; exit 8;
  }
  echo "SOURCE_VERIFIED $CFG gzip=OK tags=$RESULT"
done
mkdir -p "$ROOT/.aqp_staged"
mkdir "$STAGE"
for CFG in standard111 delta111 delta221; do
  SRC="$WENU/$CFG/PROCNLO_loop_sm-no_b_mass_0/Events/run_01/events.lhe.gz"
  SHA="$(sha256sum "$SRC" | awk '{print $1}')"
  echo "$CFG $SHA" >> "$STAGE/source_sha.txt"
done
echo "AQP_WENU_3_SOURCE_HASHES_PINNED"
echo "AQP_WENU_STAGE=$STAGE"
echo "STAGED_ONLY: no jobs submitted. To submit ONCE:"
echo "  condor_submit $ROOT/condor/wenu_existing_lhe_shower.submit"
