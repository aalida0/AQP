#!/usr/bin/env bash
# Prepare Wenu standard111, delta111, delta221 read-only audit + 16-core DAGs.
# This command STAGES and AUDITS only. It does not submit or execute MadGraph.
set -euo pipefail
cd /home/aalida/AQP/Wjets/WENU
ROOT=https://raw.githubusercontent.com/aalida0/AQP/dev/wjets-recovery
mkdir -p wenu_compare16_jo wenu_compare16_shower_jo packaging_logs
fetch() {
  local src="$1" dst="$2"
  curl --fail --silent --show-error --location "$ROOT/$src" -o "$dst"
  [[ -s "$dst" ]] || { echo "ERROR: empty fetch $src" >&2; exit 3; }
  echo "FETCHED $dst"
}
fetch scripts/audit_wenu_three_gridpack_candidates.py audit_wenu_three_gridpack_candidates.py
fetch scripts/audit_wenu_delta441_lhe.py audit_wenu_delta441_lhe.py
fetch scripts/run_wenu_comparison_16core_lhe.sh run_wenu_comparison_16core_lhe.sh
fetch scripts/run_wenu_comparison_16core_fxfx.sh run_wenu_comparison_16core_fxfx.sh
fetch condor/wenu_comparison_16core_lhe.submit wenu_comparison_16core_lhe.submit
fetch condor/wenu_comparison_16core_fxfx.submit wenu_comparison_16core_fxfx.submit
fetch condor/wenu_comparison_16core_smoke.dag wenu_comparison_16core_smoke.dag
fetch condor/wenu_comparison_16core_25k_pilot.dag wenu_comparison_16core_25k_pilot.dag
for cfg in standard111 delta111 delta221; do
  mkdir -p "wenu_compare16_jo/$cfg/100003" "wenu_compare16_shower_jo/$cfg/100004"
  fetch "joboptions/wenu_comparison16/$cfg/100003/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_${cfg}.py" \
    "wenu_compare16_jo/$cfg/100003/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_${cfg}.py"
  fetch "joboptions/wenu_comparison16_shower/$cfg/100004/mc.aMCPy8EG_Wenu_FxFx_2jets_${cfg}_shower.py" \
    "wenu_compare16_shower_jo/$cfg/100004/mc.aMCPy8EG_Wenu_FxFx_2jets_${cfg}_shower.py"
done
chmod +x run_wenu_comparison_16core_lhe.sh run_wenu_comparison_16core_fxfx.sh
bash -n run_wenu_comparison_16core_lhe.sh
bash -n run_wenu_comparison_16core_fxfx.sh
python3 -m py_compile audit_wenu_three_gridpack_candidates.py audit_wenu_delta441_lhe.py \
  wenu_compare16_jo/*/100003/*.py wenu_compare16_shower_jo/*/100004/*.py
command -v condor_submit_dag >/dev/null || { echo "ERROR: HTCondor DAG command unavailable" >&2; exit 4; }
for entry in \
  standard111:311 \
  delta111:321 \
  delta221:322; do
  cfg="${entry%:*}"
  seed="${entry#*:}"
  for suffix in lhe fxfx; do
    dest="/data/aalida/AQP/Wjets/WENU/production_pilot/wenu_compare/smoke16_1k/${cfg}_seed${seed}_${suffix}"
    if [[ -e "$dest" || -L "$dest" ]]; then
      echo "ERROR: refusing to reuse an existing output path: $dest" >&2
      exit 5
    fi
  done
done
echo "==== READ-ONLY EXISTING GRIDPACK INVENTORY ===="
python3 audit_wenu_three_gridpack_candidates.py | tee wenu_three_gridpack_inventory_20261023.txt
if grep -q AQP_WENU_ARCHIVE_INVENTORY_CONTAINS_BLOCKERS wenu_three_gridpack_inventory_20261023.txt; then
  echo "ERROR: inventory has blockers; DO NOT SUBMIT. Audit first." >&2
  exit 10
fi
echo "AQP_WENU_COMPARE16_STAGING_PASS"
echo "Ready for supervised Phase A smoke submission only:"
echo "    condor_submit_dag wenu_comparison_16core_smoke.dag"
echo "Phase B 25k-LHE benchmark requires all three smoke results to pass first."
