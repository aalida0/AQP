#!/usr/bin/env bash
# Recover a PR426 200-event FxFx shower that stopped BEFORE Gen_tf.
# Uses the existing 50k LHE; no MadGraph, no integration, no re-decompression.
# Places decompressed LHE and EVNT in /data; only JO/logs remain in /home.
set -Eeuo pipefail
CASE="${1:-}"
case "$CASE" in before|after) ;; *) echo "Usage: $0 before|after" >&2; exit 2;; esac
WORK="/home/aalida/AQP/fxfx_pr426_standard111_shower/${CASE}_accepted200_seed13311"
DATA_DIR="/data/aalida/AQP/Wjets/WENU/fxfx_pr426_standard111_shower/${CASE}_accepted200_seed13311"
JO="$WORK/100007/mc.aMCPy8EG_Wenu_FxFx_2jets_PR426_shower.py"
[[ -d "$WORK" && -s "$JO" && -s "$WORK/source_lhe.sha256" ]] || {
  echo "ERROR: missing pre-staged shower input/JO under $WORK" >&2; exit 3;
}
for f in Gen_tf_shower.log runner_exit_code wenu_pr426_"$CASE"_accepted200.EVNT.pool.root; do
  [[ ! -e "$WORK/$f" ]] || { echo "ERROR: $f already exists; inspect before recovery" >&2; exit 3; }
done
[[ -f "$WORK/input.events" && ! -L "$WORK/input.events" ]] || {
  echo "ERROR: original staged input.events must be an existing regular file" >&2; exit 3;
}
exec 9>"$WORK/.aqp_resume_shower.lock"
flock -n 9 || { echo "ERROR: another recovery is running" >&2; exit 3; }
[[ ! -e "$DATA_DIR" && ! -L "$DATA_DIR" ]] || {
  echo "ERROR: /data target already exists: $DATA_DIR; inspect before retry" >&2; exit 3;
}
mkdir -p "$(dirname "$DATA_DIR")"
mkdir "$DATA_DIR"
on_exit() {
  rc=$?
  trap - EXIT
  printf '%s\n' "$rc" > "$WORK/runner_exit_code"
  echo "AQP_PR426_RESUME_EXIT=$rc CASE=$CASE"
  exit "$rc"
}
trap on_exit EXIT
stage() { echo "AQP_PR426_SHOWER_STAGE=$1" | tee -a "$WORK/shower_stage.log"; }

stage COPYING_STAGED_LHE_TO_DATA
cp -p "$WORK/input.events" "$DATA_DIR/input.events"
cmp -s "$WORK/input.events" "$DATA_DIR/input.events" || {
  echo "ERROR: staged decompressed LHE copy differs" >&2; exit 11;
}
rm -- "$WORK/input.events"
ln -s "$DATA_DIR/input.events" "$WORK/input.events"
stage VERIFIED_STAGED_LHE_ON_DATA

# Keep the original compressed LHE in /home until both comparisons finish;
# archive a byte-identical copy in /data for later transfer/showering.
SOURCE="$(awk 'NR==1 {print $2}' "$WORK/source_lhe.sha256")"
SHA="$(awk 'NR==1 {print $1}' "$WORK/source_lhe.sha256")"
[[ -f "$SOURCE" && "$SHA" =~ ^[0-9a-f]{64}$ ]] || {
  echo "ERROR: invalid original source SHA or path" >&2; exit 12;
}
[[ "$(sha256sum "$SOURCE" | awk '{print $1}')" == "$SHA" ]] || {
  echo "ERROR: original source LHE changed" >&2; exit 12;
}
cp -p "$SOURCE" "$DATA_DIR/source_50k_lhe.gz"
[[ "$(sha256sum "$DATA_DIR/source_50k_lhe.gz" | awk '{print $1}')" == "$SHA" ]] || {
  echo "ERROR: compressed LHE copy checksum mismatch" >&2; exit 12;
}
printf '%s  %s\n' "$SHA" "$DATA_DIR/source_50k_lhe.gz" > "$DATA_DIR/source_50k_lhe.sha256"
stage VERIFIED_COMPRESSED_LHE_ON_DATA

cd "$WORK"
stage ATLAS_SETUP
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
# Source in the parent shell with errexit/nounset disabled.
set +e
set +u
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" > "$WORK/atlas_setup.log" 2>&1
al_rc=$?
if (( al_rc == 0 )); then
  asetup AthGeneration,23.6.63 >> "$WORK/atlas_setup.log" 2>&1
  ath_rc=$?
else
  ath_rc=99
fi
set -u
set -e
if (( al_rc != 0 || ath_rc != 0 )); then
  echo "ERROR: ATLAS setup failed atlas=$al_rc asetup=$ath_rc" >&2
  tail -n 60 "$WORK/atlas_setup.log" >&2
  exit 13
fi
command -v Gen_tf.py >/dev/null || {
  echo "ERROR: Gen_tf.py missing after setup" >&2; exit 13;
}
stage ATLAS_READY
export AQP_FXFX_PR426_CASE="$CASE"
export OMP_NUM_THREADS=1
unset ATHENA_CORE_NUMBER
EVNT="wenu_pr426_${CASE}_accepted200.EVNT.pool.root"
stage START_GEN_TF
set +e
Gen_tf.py --ecmEnergy=13000 --maxEvents=200 --firstEvent=1 \
  --randomSeed=13311 --jobConfig="$WORK/100007" \
  --inputGeneratorFile=input.events --outputEVNTFile="$EVNT" \
  --outputFileValidation=False > "$WORK/Gen_tf_shower.log" 2>&1
rc=$?
set -e
if (( rc != 0 )); then
  tail -n 75 "$WORK/Gen_tf_shower.log" >&2
  exit "$rc"
fi
[[ -s "$EVNT" && -s "$WORK/log.generate" ]] || {
  echo "ERROR: missing EVNT/log.generate" >&2; exit 20;
}
for marker in "AQP_FXFX_PR426_SHOWER_CASE=$CASE" \
              "AQP_FXFX_PR426_SHOWER_MADGRAPH_NOT_INVOKED" \
              "AQP_FXFX_PR426_SHOWER_FXFX_NJETMAX=2_QCUT=20_A14" \
              "Adding user hook JetMatchingMadgraph"; do
  grep -Fq "$marker" "$WORK/log.generate" || {
    echo "ERROR: missing FxFx matching marker: $marker" >&2; exit 21;
  }
done
stage COPYING_EVNT_TO_DATA
cp -p "$EVNT" "$DATA_DIR/$EVNT"
cmp -s "$EVNT" "$DATA_DIR/$EVNT" || {
  echo "ERROR: EVNT copy mismatch; original remains on /home" >&2; exit 22;
}
sha256sum "$DATA_DIR/$EVNT" > "$DATA_DIR/evnt.sha256"
rm -- "$EVNT"
ln -s "$DATA_DIR/$EVNT" "$EVNT"
stage PASS
echo "AQP_PR426_SHOWER200_PASS"
echo "EVNT=$DATA_DIR/$EVNT"
