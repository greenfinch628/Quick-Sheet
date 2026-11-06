#!/usr/bin/env bash
set -Eeuo pipefail
REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
"$REPO/packaging/createQuickSheetRpm.sh"
"$REPO/packaging/createQuickSheetDeb.sh"
echo "Quick-Sheet $(cat "$REPO/VERSION"): packages ready."
# Source and release publishing is deliberate; builds never commit or push unrelated work.
