#!/usr/bin/env bash
# Create an immutable-source, corrected COPY of the recovered Wenu Delta441
# NLO gridpack. Execute only on HTCondor worker-local scratch.
set -Eeuo pipefail
BASE=/data/aalida/AQP/Wjets/WENU
SOURCE="$BASE/gridpacks/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441_backup.MG3511.GRID.tar.gz"
DEST="$BASE/gridpacks/mc_13TeV.aMCPy8EG_Wenu_FxFx_2jets_HT2bias_delta441_cleaned_v1.MG3511.GRID.tar.gz"
OUT="$BASE/smoke_tests/delta441_backup/clean_gridpack_v1"
SCRATCH="${_CONDOR_SCRATCH_DIR:-}"
if [[ -z "$SCRATCH" || ! -d "$SCRATCH" ]]; then
  echo "ERROR: must run in HTCondor worker-local scratch" >&2; exit 2
fi
SCRATCH="$(realpath "$SCRATCH")"
case "$SCRATCH/" in /data/*|/home/*) echo "ERROR: refusing shared scratch" >&2; exit 2;; esac
if [[ -e "$DEST" || -e "$OUT" ]]; then
  echo "ERROR: output gridpack or report directory already exists; refusing overwrite" >&2; exit 3
fi
if [[ ! -r "$SOURCE" ]]; then echo "ERROR: source archive missing" >&2; exit 4; fi
mkdir -p "$OUT"
TMP_DEST="$DEST.partial.$(date +%s).$$"
LOCAL_PACK="$SCRATCH/delta441_cleaned_v1.GRID.tar.gz"
on_exit() {
  rc=$?
  trap - EXIT
  set +e
  printf '%s\n' "$rc" > "$OUT/prepare_exit_code"
  if [[ "$rc" -ne 0 ]]; then rm -f "$TMP_DEST"; fi
  if [[ -f "$OUT/packaging.stdout" ]]; then tail -n 80 "$OUT/packaging.stdout" > "$OUT/packaging.tail"; fi
  echo "AQP_CLEAN_GRIDPACK_PREP_EXIT=$rc"; exit "$rc"
}
trap on_exit EXIT
trap 'exit 143' TERM
cd "$SCRATCH"
exec > >(tee -a "$OUT/packaging.stdout") 2> >(tee -a "$OUT/packaging.stderr" >&2)
date -u
echo "AQP_CLEAN_SOURCE=$SOURCE"
echo "AQP_CLEAN_OUTPUT=$DEST"
echo "AQP_CLEAN_SCRATCH=$SCRATCH"
sha256sum "$SOURCE" | tee "$OUT/source.sha256"
echo "Extracting original recovered archive; this does not execute MG."
tar -xzf "$SOURCE" -C "$SCRATCH"
for f in \
  madevent/SubProcesses/job_status.pkl \
  madevent/SubProcesses/orderstags_glob.dat \
  madevent/SubProcesses/randinit \
  madevent/Cards/run_card.dat \
  madevent/Source/make_opts; do
  if [[ ! -s "$f" ]]; then echo "ERROR: missing extracted $f" >&2; exit 11; fi
done
find madevent/SubProcesses -type f -name res_1.dat | wc -l | tee "$OUT/integration_res1_count.txt"
sha256sum madevent/SubProcesses/job_status.pkl | tee "$OUT/checkpoint_before.sha256"

# Remove ONLY top-level stale debug logs from the new archive.
# The originals remain in SOURCE and copies are retained in OUT.
mkdir -p "$OUT/archived_debug_logs"
n_debug=0
while IFS= read -r -d '' f; do
  cp -p "$f" "$OUT/archived_debug_logs/$(basename "$f")"
  rm -f -- "$f"
  n_debug=$((n_debug+1))
done < <(find madevent -maxdepth 1 -type f -name '*_debug.log' -print0)
echo "AQP_CLEAN_REMOVED_STALE_DEBUG_LOGS=$n_debug"

# Repair the compiler runtime library ONLY if the source options need it.
# Keep the prepatch make_opts OUTSIDE the repackaged madevent tree.
if grep -Fq -- '-lc++' madevent/Source/make_opts; then
  cp -p madevent/Source/make_opts "$OUT/make_opts.before_libstdcxx_fix"
  sed -i 's/-lc++/-lstdc++/g' madevent/Source/make_opts
  echo 'AQP_CLEAN_LIBSTDCXX_PATCH=applied'
else
  echo 'AQP_CLEAN_LIBSTDCXX_PATCH=not_required'
fi
if grep -Fq -- '-lc++' madevent/Source/make_opts; then
  echo 'ERROR: unresolved libc++ token in Source/make_opts' >&2; exit 12
fi

# The release-specific system libraries are provided by AthGeneration 23.6.63.
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
set +e; set +u
source "$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh" > "$OUT/atlas_setup.log" 2>&1
setup_a=$?
if [[ "$setup_a" -eq 0 ]]; then
  asetup AthGeneration,23.6.63 >> "$OUT/atlas_setup.log" 2>&1
  setup_b=$?
else
  setup_b=99
fi
set -e; set -u
if [[ "$setup_a" -ne 0 || "$setup_b" -ne 0 ]]; then
  echo "ERROR: AthGeneration setup failed"; tail -n 40 "$OUT/atlas_setup.log"; exit 13
fi
LIBSTDCXX="$(gfortran -print-file-name=libstdc++.so)"
if [[ "$LIBSTDCXX" == "libstdc++.so" || ! -f "$LIBSTDCXX" ]]; then
  echo "ERROR: libstdc++.so unavailable"; exit 14
fi
make -C madevent/SubProcesses collect_events LDFLAGS=-lstdc++ \
  > "$OUT/collect_events_link_preflight.log" 2>&1 || {
    tail -n 60 "$OUT/collect_events_link_preflight.log"; exit 15;
  }
test -x madevent/SubProcesses/collect_events
sha256sum madevent/SubProcesses/job_status.pkl | tee "$OUT/checkpoint_after.sha256"
cmp "$OUT/checkpoint_before.sha256" "$OUT/checkpoint_after.sha256"

# A cleaned archive retains the same recovered integration checkpoint.
# Write to worker scratch first, verify, then atomically publish under /data.
echo 'AQP_CLEAN_REPACK_START'
date -u
tar -I 'gzip -3' -cf "$LOCAL_PACK" madevent
tar -tzf "$LOCAL_PACK" | grep -E '(^madevent/SubProcesses/job_status.pkl$|^madevent/Cards/run_card.dat$)' \
  > "$OUT/repack_required_members.txt" || true
grep -qx 'madevent/SubProcesses/job_status.pkl' "$OUT/repack_required_members.txt"
grep -qx 'madevent/Cards/run_card.dat' "$OUT/repack_required_members.txt"
tar -tzf "$LOCAL_PACK" | grep -q 'madevent/run_01_tag_1_debug.log' && {
  echo 'ERROR: stale debug log survived packaging'; exit 16;
} || true
gzip -t "$LOCAL_PACK"
cp "$LOCAL_PACK" "$TMP_DEST"
mv "$TMP_DEST" "$DEST"
sha256sum "$DEST" | tee "$OUT/cleaned_gridpack.sha256"
ls -lh "$SOURCE" "$DEST"
echo 'AQP_CLEAN_GRIDPACK_PACKAGED_PASS'
date -u
