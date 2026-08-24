#!/usr/bin/env bash
# shotsort .app + .dmg 빌드. SIGN_IDENTITY/NOTARY_PROFILE 쌍을 주면 배포용 공증 DMG를 만든다.
# 사용: ./build_app.sh → dist/shotsort.app, dist/shotsort.dmg
set -euo pipefail
cd "$(dirname "$0")"

SIGN_IDENTITY="${SIGN_IDENTITY:-}"
NOTARY_PROFILE="${NOTARY_PROFILE:-}"

if [ -n "$SIGN_IDENTITY" ] && [ -z "$NOTARY_PROFILE" ] || [ -z "$SIGN_IDENTITY" ] && [ -n "$NOTARY_PROFILE" ]; then
  echo "SIGN_IDENTITY와 NOTARY_PROFILE은 함께 설정해야 합니다." >&2
  exit 2
fi

if [ -n "$SIGN_IDENTITY" ]; then
  echo "▶ Developer ID 서명 준비: $SIGN_IDENTITY (notary profile: $NOTARY_PROFILE)"
else
  echo "▶ 무서명 빌드: 로컬 확인용이며 배포 불가 상태입니다."
fi

[ -d .venv ] || { echo ".venv 가 없습니다. 먼저 ./run.sh 로 의존성을 설치하세요." >&2; exit 1; }

echo "▶ PyInstaller 준비"
.venv/bin/pip install -q pyinstaller

echo "▶ .app 빌드"
.venv/bin/python3 -m PyInstaller --name shotsort --clean --noconfirm --windowed \
  --collect-all nicegui \
  --collect-all pywebview \
  --hidden-import Vision --hidden-import Quartz --hidden-import Foundation \
  --hidden-import WebKit --hidden-import AppKit --hidden-import objc \
  app.py

if [ -n "$SIGN_IDENTITY" ]; then
  echo "▶ .app 서명 및 검증"
  codesign --force --deep --options runtime --timestamp \
    --entitlements packaging/entitlements.plist \
    --sign "$SIGN_IDENTITY" dist/shotsort.app
  codesign --verify --deep --strict --verbose=2 dist/shotsort.app
fi

echo "▶ .dmg 패키징"
rm -rf dist/dmg && mkdir -p dist/dmg
cp -R dist/shotsort.app dist/dmg/
ln -s /Applications dist/dmg/Applications
rm -f dist/shotsort.dmg
hdiutil create -volname "shotsort" -srcfolder dist/dmg -ov -format UDZO dist/shotsort.dmg >/dev/null
rm -rf dist/dmg

if [ -n "$SIGN_IDENTITY" ]; then
  echo "▶ DMG 공증 및 Gatekeeper 검증"
  NOTARY_ARGS=(--keychain-profile "$NOTARY_PROFILE")
  if [ -n "${NOTARY_KEYCHAIN:-}" ]; then
    NOTARY_ARGS+=(--keychain "$NOTARY_KEYCHAIN")
  fi
  xcrun notarytool submit dist/shotsort.dmg "${NOTARY_ARGS[@]}" --wait
  xcrun stapler staple dist/shotsort.dmg
  xcrun stapler validate dist/shotsort.dmg
  spctl -a -vvv -t install dist/shotsort.dmg
fi

echo "✅ 완료: dist/shotsort.app, dist/shotsort.dmg"
