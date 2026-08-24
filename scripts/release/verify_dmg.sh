#!/usr/bin/env bash
# Create or verify the portable SHA-256 sidecar for a release DMG.
set -euo pipefail

DMG_PATH="${1:-dist/shotsort.dmg}"
CHECKSUM_PATH="${2:-${DMG_PATH}.sha256}"

if [ "${VERIFY_CHECKSUM:-0}" = "1" ]; then
  shasum -a 256 -c "$CHECKSUM_PATH"
else
  (cd "$(dirname "$DMG_PATH")" && shasum -a 256 "$(basename "$DMG_PATH")") > "$CHECKSUM_PATH"
  echo "✅ checksum 생성: $CHECKSUM_PATH"
fi
