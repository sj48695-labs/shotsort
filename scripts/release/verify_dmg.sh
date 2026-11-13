#!/usr/bin/env bash
# 릴리스 DMG의 SHA-256 파일을 생성하거나 검증한다.
set -euo pipefail

DMG_PATH="${1:-dist/shotsort.dmg}"
CHECKSUM_PATH="${2:-${DMG_PATH}.sha256}"

if [ "${VERIFY_CHECKSUM:-0}" = "1" ]; then
  CHECKSUM_PATH="$(cd "$(dirname "$CHECKSUM_PATH")" && pwd)/$(basename "$CHECKSUM_PATH")"
  (cd "$(dirname "$DMG_PATH")" && shasum -a 256 -c "$CHECKSUM_PATH")
else
  (cd "$(dirname "$DMG_PATH")" && shasum -a 256 "$(basename "$DMG_PATH")") > "$CHECKSUM_PATH"
  echo "✅ checksum 생성: $CHECKSUM_PATH"
fi
