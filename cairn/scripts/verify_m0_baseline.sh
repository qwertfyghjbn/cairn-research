#!/usr/bin/env bash

set -euo pipefail

readonly EXPECTED_BASELINE_COMMIT="8e7e0ea67552383851dfcabfba0c4e9c8d007878"
readonly EXPECTED_LOCK_SHA256="90c5a3cc9405e27e47bc9ae5e5681ab86c63e2a23afb7768fcf1b7aa1dc80ffb"
readonly REPOSITORY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly PROJECT_ROOT="${REPOSITORY_ROOT}/cairn"

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/cairn-uv-cache}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-/tmp/cairn-uv-python}"

git -C "${REPOSITORY_ROOT}" cat-file -e "${EXPECTED_BASELINE_COMMIT}^{commit}"

if ! git -C "${REPOSITORY_ROOT}" merge-base --is-ancestor \
  "${EXPECTED_BASELINE_COMMIT}" HEAD; then
  echo "HEAD does not descend from the frozen Cairn baseline" >&2
  exit 1
fi

actual_lock_sha256="$(sha256sum "${PROJECT_ROOT}/uv.lock" | awk '{print $1}')"
if [[ "${actual_lock_sha256}" != "${EXPECTED_LOCK_SHA256}" ]]; then
  echo "cairn/uv.lock does not match the frozen M0 lock" >&2
  exit 1
fi

uv run --project "${PROJECT_ROOT}" --frozen --group dev pytest -q
uv run --project "${PROJECT_ROOT}" --frozen cairn --help >/dev/null

echo "M0 baseline verification passed"
