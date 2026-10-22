#!/usr/bin/env bash
# Download and validate a three-stage HTCondor DAG for the Delta441 sample.
# Run on a UChicago AF login node; NO MadGraph execution occurs here.
set -euo pipefail
cd /home/aalida/AQP/Wjets/WENU
BASE=https://raw.githubusercontent.com/aalida0/AQP/dev/wjets-recovery
mkdir -p parallel_jo/100003 parallel_shower_jo/100004 packaging_logs

fetch() {
  local src="$1" dst="$2"
  echo "Fetching $src -> $dst"
  curl --fail --silent --show-error --location "$BASE/$src" -o "$dst"
  [[ -s "$dst" ]] || { echo "ERROR: empty download $dst"; exit 10; }
}
fetch scripts/prepare_wenu_delta441_clean_gridpack_v1.sh prepare_wenu_delta441_clean_gridpack_v1.sh
fetch scripts/run_delta441_clean_v1_8cpu_seed137_1000lhe.sh run_delta441_clean_v1_8cpu_seed137_1000lhe.sh
fetch scripts/run_delta441_clean_v1_seed137_fxfx_shower.sh run_delta441_clean_v1_seed137_fxfx_shower.sh
fetch joboptions/delta441_parallel/100003/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441.py \
  parallel_jo/100003/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441.py
fetch joboptions/delta441_parallel_shower/100004/mc.aMCPy8EG_Wenu_FxFx_2jets_D441_shower.py \
  parallel_shower_jo/100004/mc.aMCPy8EG_Wenu_FxFx_2jets_D441_shower.py
fetch condor/delta441_gridpack_clean_v1.submit delta441_gridpack_clean_v1.submit
fetch condor/delta441_clean_v1_8cpu_seed137_1000lhe.submit delta441_clean_v1_8cpu_seed137_1000lhe.submit
fetch condor/delta441_clean_v1_seed137_fxfx_shower.submit delta441_clean_v1_seed137_fxfx_shower.submit
fetch condor/delta441_clean_8cpu_1000lhe.dag delta441_clean_8cpu_1000lhe.dag

chmod +x prepare_wenu_delta441_clean_gridpack_v1.sh \
  run_delta441_clean_v1_8cpu_seed137_1000lhe.sh \
  run_delta441_clean_v1_seed137_fxfx_shower.sh
bash -n prepare_wenu_delta441_clean_gridpack_v1.sh
bash -n run_delta441_clean_v1_8cpu_seed137_1000lhe.sh
bash -n run_delta441_clean_v1_seed137_fxfx_shower.sh
python3 -m py_compile \
  parallel_jo/100003/mc.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441.py \
  parallel_shower_jo/100004/mc.aMCPy8EG_Wenu_FxFx_2jets_D441_shower.py

DATA=/data/aalida/AQP/Wjets/WENU
for path in \
 "$DATA/gridpacks/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441_cleaned_v1.MG3511.GRID.tar.gz" \
 "$DATA/smoke_tests/delta441_backup/clean_gridpack_v1" \
 "$DATA/smoke_tests/delta441_backup/delta441_clean_v1_8cpu_seed137_1000lhe" \
 "$DATA/smoke_tests/delta441_backup/delta441_clean_v1_seed137_fxfx_shower"; do
  if [[ -e "$path" ]]; then
    echo "ERROR: planned output exists; do not resubmit unchanged DAG: $path" >&2
    exit 20
  fi
done
command -v condor_submit_dag >/dev/null || {
  echo "ERROR: condor_submit_dag missing from PATH"; exit 21;
}
echo "AQP_DELTA441_DAG_STAGE_PREFLIGHT_PASS"
echo "Submit once: condor_submit_dag delta441_clean_8cpu_1000lhe.dag"
