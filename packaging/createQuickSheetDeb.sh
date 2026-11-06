#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "ERROR: DEB build failed (line $LINENO)" >&2' ERR
REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# Reuse the established Ubuntu 26.04 builder when available.
IMAGE="${QUICK_SHEET_DEB_IMAGE:-localhost/nex-editg-ubuntu-builder:26.04}"
if ! podman image exists "$IMAGE"; then
    IMAGE=localhost/quick-sheet-ubuntu-builder:26.04
    if ! podman image exists "$IMAGE"; then
        podman build -t "$IMAGE" -f "$REPO/packaging/Containerfile.ubuntu" "$REPO/packaging"
    fi
fi
exec podman run --rm --userns=keep-id --user "$(id -u):$(id -g)" \
    --platform linux/amd64 -v "$REPO:/work:Z" -w /work "$IMAGE" \
    python3 packaging/build.py deb
