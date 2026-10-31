#!/usr/bin/env bash
# Stage only. Does not call condor_submit or MadGraph. No gridpack reads.
set -Eeuo pipefail
ROOT=/home/aalida/AQP/aqp-production-audit
ORIG=/home/aalida/AQP/Wjets/WENU/standard111/100000
STAGE="$ROOT/.aqp_staged/fxfx_pr426_ab"

cd "$ROOT"
[[ "$(git branch --show-current)" == "audit/production-framework" ]] || {
  echo "ERROR: wrong branch" >&2; exit 2;
}
[[ ! -e "$STAGE" && ! -L "$STAGE" ]] || {
  echo "ERROR: stage exists; do not silently resubmit: $STAGE" >&2; exit 3;
}
command -v condor_submit >/dev/null || { echo "ERROR: condor_submit unavailable" >&2; exit 4; }
command -v python3 >/dev/null || { echo "ERROR: python3 unavailable" >&2; exit 4; }
bash -n scripts/run_wenu_fxfx_pr426_ab.sh
chmod u+x scripts/run_wenu_fxfx_pr426_ab.sh
for file in dummy_fct.f montecarlocounter_MINE.f; do
  [[ -s "$ORIG/$file" ]] || { echo "ERROR: missing HT2 input: $ORIG/$file" >&2; exit 5; }
done

for variant in before after; do
  jo="joboptions/wenu_fxfx_pr426_ab/$variant/100005/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_$variant.py"
  [[ -s "$jo" ]] || { echo "ERROR: missing $jo" >&2; exit 6; }
  python3 -B - "$jo" <<'PY'
import ast
from pathlib import Path
import sys
p=Path(sys.argv[1]); text=p.read_text()
compile(text,str(p),"exec")
for needle in ("grid_pack=False", "WENU_NB_CORES = 16",
               "REQUIRED_ACCURACY = 0.1", "mcatnlo_delta",
               "FOLDING = \"1, 1, 1\"", "AQP_FXFX_AB_REQUIRE_TXT_ONLY",
               "montecarlocounter_MINE.f", "dummy_fct.f"):
    if needle not in text:
        raise SystemExit(f"{p}: missing {needle}")
if "enable_condor_timing" in text or "shutil.copy(" in text:
    raise SystemExit(f"{p}: unexpected legacy timing or cuts installation")
print("AQP_FXFX_AB_JO_PREFLIGHT_PASS", p)
PY
done

# The patch is tested against current ATLAS 3.5.11 source, but actual
# process-local cuts.f is rechecked separately on the worker before patching.
[[ -n "$(printenv MADPATH || true)" ]] || {
  echo "ERROR: load AthGeneration,23.6.63 first so MADPATH is defined" >&2; exit 7;
}
SOURCE="$(printenv MADPATH)/Template/NLO/SubProcesses/cuts.f"
[[ -s "$SOURCE" ]] || { echo "ERROR: missing MadGraph template" >&2; exit 8; }
python3 -m unittest discover -s tests -p 'test_aqp_fxfx_exclusive_kt_patch.py' -v
python3 scripts/aqp_prepare_fxfx_exclusive_kt_patch.py \
  --source "$SOURCE" > /dev/null

BASE=/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_ab
for variant in before after; do
  for entry in smoke200:311 benchmark50k:411; do
    tag="$(printf '%s' "$entry" | cut -d: -f1)"
    seed="$(printf '%s' "$entry" | cut -d: -f2)"
    dst="$BASE/$tag""_$variant""_seed$seed"
    [[ ! -e "$dst" && ! -L "$dst" ]] || {
      echo "ERROR: pre-existing results; do not resubmit: $dst" >&2; exit 9;
    }
  done
done
mkdir -p "$STAGE/logs"
git rev-parse HEAD > "$STAGE/source_commit.txt"
sha256sum "$ORIG/dummy_fct.f" "$ORIG/montecarlocounter_MINE.f" \
  > "$STAGE/original_ht2_sources.sha256"
sha256sum "$SOURCE" > "$STAGE/atlas_template_cuts.sha256"

echo "AQP_FXFX_PR426_AB_STAGE_PASS"
echo "ONLY the 200-LHE functional smoke is ready to submit:"
echo "  condor_submit condor/wenu_fxfx_pr426_smoke200.submit"
echo "DO NOT submit the 50k test until both 200-LHE jobs pass."
