#!/usr/bin/env bash
# Download balanced Zee/Wenu log.generate pilots via Rucio, THEN print all metrics.
# Excludes aborted delta441 v2 tasks. Does not download EVNT.root files.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="\${1:-\${AQP_LOG_DIR:-$PWD/aqp_log_comparison}}"
mkdir -p "$ROOT"
ROOT="$(cd "$ROOT" && pwd)"

if ! command -v rucio >/dev/null 2>&1; then
  echo 'ERROR: rucio is not in PATH. Run lsetup rucio (or use your site setup).' >&2
  exit 1
fi
if ! rucio whoami >/dev/null 2>&1; then
  echo 'ERROR: Rucio authentication failed; check your proxy/credentials.' >&2
  exit 1
fi

printf 'process\tconfig\tversion\trequested_logs\tevents_per_job\n' > "$ROOT/sampling_plan.tsv"
printf 'process\tconfig\tversion\trequested_logs\trucio_did\n' > "$ROOT/rucio_requests.tsv"
printf 'process\tconfig\tversion\treason\n' > "$ROOT/download_warnings.tsv"
errors=0
for process in Zee Wenu; do
  for config in standard111 delta111 delta221 delta441; do
    version=v2 count=10 expected=5000
    if [[ "$config" == 'delta441' ]]; then version=v3 count=50 expected=1000; fi
    printf '%s\t%s\t%s\t%s\t%s\n' "$process" "$config" "$version" "$count" "$expected" >> "$ROOT/sampling_plan.tsv"
    dir="$ROOT/$process/$config/$version"
    mkdir -p "$dir"
    did="user.aalida:user.aalida.AQP.\${process}.\${config}.FxFx2M.\${version}_log.generate/"
    printf '%s\t%s\t%s\t%s\t%s\n' "$process" "$config" "$version" "$count" "$did" >> "$ROOT/rucio_requests.tsv"
    echo "========== $process / $config / $version : $count logs =========="
    echo "DID: $did"
    if ! rucio list-content "$did" > "$dir/container_contents.txt" 2> "$dir/rucio_list_error.txt"; then
      printf '%s\t%s\t%s\tcontainer_not_found\n' "$process" "$config" "$version" >> "$ROOT/download_warnings.tsv"
      echo "WARNING: Could not list $did; inspect $dir/rucio_list_error.txt" >&2
      errors=$((errors+1))
      continue
    fi
    # --nrandom is applied to this container, not each of its 4 subdatasets.
    rucio download --nrandom "$count" --no-subdir --dir "$dir" "$did" \
      2>&1 | tee "$dir/rucio_download.txt"
    status="\${PIPESTATUS[0]}"
    if [[ "$status" -ne 0 ]]; then
      printf '%s\t%s\t%s\trucio_download_failed\n' "$process" "$config" "$version" >> "$ROOT/download_warnings.tsv"
      errors=$((errors+1))
    fi
    find "$dir" -type f \
      \( -name '*log.generate.txt' -o -name '*log.generate.txt.gz' -o -name '*.log.tgz' -o -name '*.log.tar.gz' \) \
      -printf '%P\n' | LC_ALL=C sort > "$dir/downloaded_files.txt"
    actual="$(wc -l < "$dir/downloaded_files.txt")"
    echo "Log files found: $actual (requested: $count)"
    if [[ "$actual" -ne "$count" ]]; then
      echo "WARNING: expected $count, found $actual logs. The report will show the actual counts." >&2
      printf '%s\t%s\t%s\tlog_count_mismatch_%s_vs_%s\n' "$process" "$config" "$version" "$actual" "$count" >> "$ROOT/download_warnings.tsv"
      errors=$((errors+1))
    fi
  done
done

echo '========== FINAL AQP COMPARISON =========='
python3 "$SCRIPT_DIR/compare_aqp_logs.py" "$ROOT"
analysis_status=$?

# Keep raw logs, manifests, and result files for reproducibility/sharing.
archive="$ROOT/aqp_50k_log_pilot.tar.gz"
if [[ -d "$ROOT/Zee" && -d "$ROOT/Wenu" ]]; then
  tar -czf "$archive" -C "$ROOT" Zee Wenu sampling_plan.tsv rucio_requests.tsv \
    download_warnings.tsv aqp_per_log.csv aqp_summary.csv aqp_results.txt
  echo "Shareable archive: $archive"
fi
if [[ "$errors" -gt 0 || "$analysis_status" -ne 0 ]]; then
  echo "Completed with $errors download/count warning(s); check downloaded_files.txt and coverage table." >&2
  exit 1
fi
