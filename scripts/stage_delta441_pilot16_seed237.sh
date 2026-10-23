#!/usr/bin/env bash
# Stage complete Wenu Delta441 16-core 25k LHE -> 5k FxFx EVNT DAG.
# Run on UChicago AF login node; staging does not execute generators.
set -euo pipefail
cd /home/aalida/AQP/Wjets/WENU
ROOT=https://raw.githubusercontent.com/aalida0/AQP/dev/wjets-recovery
mkdir -p production16_jo/100003 production16_shower_jo/100004 packaging_logs
fetch() {
  local src="$1" dst="$2"
  echo "Downloading $src"
  curl --fail --silent --show-error --location "$ROOT/$src" -o "$dst"
  [[ -s "$dst" ]] || { echo "ERROR: empty download $dst" >&2; exit 10; }
}
fetch joboptions/delta441_production16/100003/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441.py \
  production16_jo/100003/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441.py
fetch joboptions/delta441_production16_shower/100004/mc.aMCPy8EG_Wenu_FxFx_2jets_D441_shower.py \
  production16_shower_jo/100004/mc.aMCPy8EG_Wenu_FxFx_2jets_D441_shower.py
fetch scripts/audit_wenu_delta441_lhe.py audit_wenu_delta441_lhe.py
fetch scripts/run_delta441_16cpu_seed237_25k_lhe.sh run_delta441_16cpu_seed237_25k_lhe.sh
fetch scripts/run_delta441_16cpu_seed237_fxfx_5000evnt.sh run_delta441_16cpu_seed237_fxfx_5000evnt.sh
fetch condor/delta441_pilot16_seed237_25k_lhe.submit delta441_pilot16_seed237_25k_lhe.submit
fetch condor/delta441_pilot16_seed237_5000evnt.submit delta441_pilot16_seed237_5000evnt.submit
fetch condor/delta441_pilot16_seed237_25k_to_5k.dag delta441_pilot16_seed237_25k_to_5k.dag

chmod +x run_delta441_16cpu_seed237_25k_lhe.sh run_delta441_16cpu_seed237_fxfx_5000evnt.sh
bash -n run_delta441_16cpu_seed237_25k_lhe.sh
bash -n run_delta441_16cpu_seed237_fxfx_5000evnt.sh
python3 -m py_compile \
  audit_wenu_delta441_lhe.py \
  production16_jo/100003/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441.py \
  production16_shower_jo/100004/mc.aMCPy8EG_Wenu_FxFx_2jets_D441_shower.py

DATA=/data/aalida/AQP/Wjets/WENU
CLEAN="$DATA/gridpacks/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441_cleaned_v1.MG3511.GRID.tar.gz"
if [[ ! -s "$CLEAN" ]]; then
  echo "ERROR: previously verified cleaned gridpack missing: $CLEAN" >&2
  exit 20
fi
if [[ ! -s "$DATA/smoke_tests/delta441_backup/clean_gridpack_v1/cleaned_gridpack.sha256" ]]; then
  echo "ERROR: successful clean-gridpack checksum report missing" >&2
  exit 21
fi
if [[ "$(cat "$DATA/smoke_tests/delta441_backup/clean_gridpack_v1/prepare_exit_code" 2>/dev/null)" != 0 ]]; then
  echo "ERROR: clean-gridpack preparation did not finish successfully" >&2
  exit 22
fi
for target in \
  "$DATA/production_pilot/delta441_16cpu_seed237_25k_lhe" \
  "$DATA/production_pilot/delta441_seed237_fxfx_5000evnt"; do
  if [[ -e "$target" ]]; then
    echo "ERROR: destination already exists; do not overwrite prior output: $target" >&2
    exit 23
  fi
done
command -v condor_submit_dag >/dev/null || {
  echo "ERROR: condor_submit_dag unavailable" >&2; exit 24;
}
echo 'AQP_DELTA441_PILOT16_STAGING_PASS'
echo 'Submit: condor_submit_dag delta441_pilot16_seed237_25k_to_5k.dag'
