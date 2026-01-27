#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ts="$(date +%Y%m%d_%H%M%S)"
outdir="out/context_bundles"
mkdir -p "$outdir"
bundle="${outdir}/climb-agent_context_bundle_${ts}.zip"

# Collect only relevant repo files; ignore missing paths gracefully.
declare -a ITEMS=()

add_if_exists () {
  local p="$1"
  if compgen -G "$p" > /dev/null; then
    # expand globs into ITEMS
    for f in $p; do
      [[ -e "$f" ]] && ITEMS+=("$f")
    done
  fi
}

# Core docs + code
add_if_exists "README.md"
add_if_exists "docs/*.md"
add_if_exists "scripts/*.py"
add_if_exists "scripts/*.sh"

# Engine + catalogs
add_if_exists "catalog/engine/*.py"
add_if_exists "catalog/exercises/v1/*.json"
add_if_exists "catalog/templates/v1/*.json"
add_if_exists "catalog/sessions/v1/*.json"

# Tests + schemas + state/logs
add_if_exists "tests/test_*.py"
add_if_exists "data/schemas/*.json"
add_if_exists "data/user_state.json"
add_if_exists "data/logs/*.jsonl"

# Helpful outputs (if present)
add_if_exists "out/manual_sanity/*.json"
add_if_exists "out/tmp_sessions/*.json"
add_if_exists "out/log_templates/*.json"

if [[ ${#ITEMS[@]} -eq 0 ]]; then
  echo "ERROR: nothing to bundle (no matching files found)." >&2
  exit 2
fi

# Create zip (exclude noise)
zip -r "$bundle" "${ITEMS[@]}" \
  -x ".git/*" -x "**/__pycache__/*" -x "**/*.pyc" \
  -x "out/context_bundles/*" \
  >/dev/null

echo "OK: created bundle -> $bundle"
