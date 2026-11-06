#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "ERROR: RPM build failed (line $LINENO)" >&2' ERR
REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$REPO/packaging/build.py" rpm
