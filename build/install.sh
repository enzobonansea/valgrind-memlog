#!/bin/bash
set -e

# Image name and tar
IMAGE_NAME="memlog"
IMAGE_TAG="latest"
TAR_PATH="$HOME/${IMAGE_NAME}.tar"

# Get commit information for placeholders
echo "[1/4] Getting commit information..."
MAIN_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Update menu.sh with commit information
echo "Updating menu.sh with commit information..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MENU_SH="$REPO_ROOT/runtime/menu.sh"
if [ -f "$MENU_SH" ]; then
    cp "$MENU_SH" "$MENU_SH.bak"
    sed -i "s/MAIN_COMMIT_PLACEHOLDER/$MAIN_COMMIT/g" "$MENU_SH"
    echo "Updated menu.sh with commit: $MAIN_COMMIT"
fi

echo "[2/4] Building Docker image..."
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} "$REPO_ROOT"

echo "[3/4] Saving image to $TAR_PATH ..."
docker save -o "$TAR_PATH" ${IMAGE_NAME}:${IMAGE_TAG}

echo "[4/4] Loading image back from $TAR_PATH ..."
docker load -i "$TAR_PATH"

# Restore original menu.sh if backup exists
if [ -f "$MENU_SH.bak" ]; then
    mv "$MENU_SH.bak" "$MENU_SH"
    echo "Restored original menu.sh"
fi

echo "Done. Image '${IMAGE_NAME}:${IMAGE_TAG}' is available. Run with: docker run -it --rm memlog:latest"
