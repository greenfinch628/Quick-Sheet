#!/usr/bin/env bash
# Fedora installation now uses the maintained RPM migration/update workflow.
set -Eeuo pipefail
exec "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/packaging/updateQuickSheetFromScopuli.sh" "$@"
