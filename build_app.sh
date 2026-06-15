#!/usr/bin/env bash
# shotsort .app + .dmg 빌드 (비개발자 배포용, 무서명)
# 사용:  ./build_app.sh   →  dist/shotsort.app, dist/shotsort.dmg
set -euo pipefail
cd "$(dirname "$0")"

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

echo "▶ .dmg 패키징"
rm -rf dist/dmg && mkdir -p dist/dmg
cp -R dist/shotsort.app dist/dmg/
ln -s /Applications dist/dmg/Applications
rm -f dist/shotsort.dmg
hdiutil create -volname "shotsort" -srcfolder dist/dmg -ov -format UDZO dist/shotsort.dmg >/dev/null
rm -rf dist/dmg

echo "✅ 완료: dist/shotsort.app, dist/shotsort.dmg"
