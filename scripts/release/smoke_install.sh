#!/usr/bin/env bash
# Validate the exact DMG installation path without touching /Applications.
set -euo pipefail

DMG_PATH="${1:-dist/shotsort.dmg}"
WORK_DIR="$(mktemp -d)"
MOUNT_POINT="$WORK_DIR/mount"
APPLICATIONS_DIR="$WORK_DIR/Applications"

cleanup() {
  if mount | grep -Fq "on $MOUNT_POINT "; then
    hdiutil detach "$MOUNT_POINT" -quiet || true
  fi
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

mkdir -p "$MOUNT_POINT" "$APPLICATIONS_DIR"
hdiutil attach "$DMG_PATH" -nobrowse -readonly -mountpoint "$MOUNT_POINT" -quiet
xcrun stapler validate "$DMG_PATH"

APP_PATH="$MOUNT_POINT/shotsort.app"
[ -d "$APP_PATH" ] || { echo "DMG에 shotsort.app이 없습니다." >&2; exit 1; }
cp -R "$APP_PATH" "$APPLICATIONS_DIR/"

INSTALLED_APP="$APPLICATIONS_DIR/shotsort.app"
codesign --verify --deep --strict --verbose=2 "$INSTALLED_APP"
spctl -a -vvv -t install "$INSTALLED_APP"
echo "✅ clean macOS 설치 smoke 통과"
