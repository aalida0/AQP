#!/usr/bin/env bash
# Audit-checkout-only Wenu comparison staging. Never submits or runs MadGraph.
# Does not rewrite legacy /home/.../WENU or any gridpack/source process.
set -Eeuo pipefail
ROOT=/home/aalida/AQP/aqp-production-audit
BASE=/data/aalida/AQP/Wjets/WENU
STAGE="$ROOT/.aqp_staged/wenu_compare16_v2"
cd "$ROOT"
[[ "$(git branch --show-current)" == audit/production-framework ]] || {
  echo "ERROR: expected branch audit/production-framework" >&2; exit 2;
}
[[ ! -e "$STAGE" && ! -L "$STAGE" ]] || {
  echo "ERROR: v2 stage already exists: $STAGE (inspect before retry)" >&2; exit 3;
}
for BIN in python3 condor_submit_dag bash; do
  command -v "$BIN" >/dev/null || { echo "ERROR: missing $BIN" >&2; exit 4; }
done

for script in run_wenu_comparison_16core_lhe.sh run_wenu_comparison_16core_fxfx.sh; do
  bash -n "$ROOT/scripts/$script"
  chmod u+x "$ROOT/scripts/$script"
done

python3 -B - "$ROOT" <<'PY'
from pathlib import Path
import ast
import sys
root=Path(sys.argv[1])
for cfg in ("standard111", "delta111", "delta221"):
    for kind in ("lhe", "shower"):
        if kind == "lhe":
            p=(root / "joboptions/wenu_comparison16" / cfg / "100003" /
               ("mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_%s.py" % cfg))
        else:
            p=(root / "joboptions/wenu_comparison16_shower" / cfg / "100004" /
               ("mc.aMCPy8EG_Wenu_FxFx_2jets_%s_shower.py" % cfg))
        txt=p.read_text()
        compile(txt, str(p), "exec")
        if kind == "lhe":
            for required in ("is_gen_from_gridpack()", "AQP_WENU_EXISTING_GRIDPACK_ONLY",
                             "AQP_WENU_LHE_EVENTS_REQUESTED", "AQP_WENU_PARALLEL_CONFIG_VERIFIED"):
                if required not in txt:
                    raise SystemExit("%s missing %s" % (p, required))
        else:
            for required in ("AQP_FXFX_SHOWER_MADGRAPH_NOT_INVOKED",
                             "AQP_WENU_SHOWER_CONFIG=%s" % cfg,
                             'include("Pythia8_i/Pythia8_FxFx_A14mod.py")'):
                if required not in txt:
                    raise SystemExit("%s missing %s" % (p, required))
            tree = ast.parse(txt)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    if any(alias.name.startswith("MadGraphControl") for alias in node.names):
                        raise SystemExit("%s imports MadGraphControl" % p)
                elif isinstance(node, ast.ImportFrom):
                    if (node.module or "").startswith("MadGraphControl"):
                        raise SystemExit("%s imports MadGraphControl" % p)
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in ("generate", "new_process"):
                        raise SystemExit("%s explicitly invokes MadGraph" % p)
print("AQP_WENU_COMPARE16_V2_JO_STATIC_PREFLIGHT_PASS")
PY

for CFG in standard111 delta111 delta221; do
  PACK="$BASE/gridpacks/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_$CFG.MG3511.GRID.tar.gz"
  [[ -s "$PACK" ]] || { echo "ERROR: gridpack absent: $PACK" >&2; exit 5; }
  [[ -s "$PACK.sha256" ]] || {
    echo "ERROR: missing checksum sidecar required by worker: $PACK.sha256" >&2; exit 6;
  }
  read -r SHA REST < "$PACK.sha256"
  [[ "$SHA" =~ ^[[:xdigit:]]{64}$ ]] || {
    echo "ERROR: malformed checksum in $PACK.sha256" >&2; exit 7;
  }
  for TAG in smoke16_1k pilot16_25k; do
    case "$CFG:$TAG" in
      standard111:smoke16_1k) SEED=311 ;;
      delta111:smoke16_1k) SEED=321 ;;
      delta221:smoke16_1k) SEED=322 ;;
      standard111:pilot16_25k) SEED=411 ;;
      delta111:pilot16_25k) SEED=421 ;;
      delta221:pilot16_25k) SEED=422 ;;
    esac
    for SUFFIX in lhe fxfx; do
      DEST="$BASE/production_pilot/wenu_compare/$TAG/$CFG""_seed$SEED""_$SUFFIX"
      [[ ! -e "$DEST" && ! -L "$DEST" ]] || {
        echo "ERROR: pre-existing output path: $DEST" >&2; exit 8;
      }
    done
  done
  echo "GRIDPACK_CANDIDATE $CFG $(stat -c '%s' "$PACK") bytes checksum-sidecar-found"
done

# Lightweight audit inspects the existing process/run-card and archive metadata.
# It explicitly does NOT hash large Ceph archives or unpack gridpacks.
mkdir -p "$ROOT/.aqp_staged"
mkdir -p "$STAGE"
python3 "$ROOT/scripts/audit_wenu_three_gridpack_candidates.py" \
  > "$STAGE/gridpack_inventory.txt"
if grep -q 'AQP_WENU_ARCHIVE_INVENTORY_CONTAINS_BLOCKERS' \
  "$STAGE/gridpack_inventory.txt"; then
  echo "ERROR: read-only archive inventory found blockers" >&2
  grep -E 'ERROR:|BLOCKED|AQP_WENU_ARCHIVE' "$STAGE/gridpack_inventory.txt" >&2
  exit 9
fi
mkdir -p "$STAGE/logs"
printf '%s\n' "$(git rev-parse HEAD)" > "$STAGE/source_commit.txt"
echo "AQP_WENU_COMPARISON16_V2_STAGING_PASS"
echo "STAGED_ONLY: NO JOBS SUBMITTED"
echo "Audit: $STAGE/gridpack_inventory.txt"
echo "When reviewed, submit Phase A ONCE from the checkout root:"
echo "  condor_submit_dag condor/wenu_comparison16_v2/smoke.dag"
echo "Do not submit the 25k pilot DAG until all 3 generation+shower gates pass."
