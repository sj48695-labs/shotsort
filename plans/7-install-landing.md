# #7 서명·공증된 설치 경로와 공개 랜딩 계획

## 조사 결과와 범위

- 현재 `main`에는 `.github/workflows/ci.yml`의 Linux 단위 테스트만 있고, 태그 릴리스·DMG checksum·macOS 설치 검증·GitHub Pages 배포는 없다.
- `build_app.sh`는 PyInstaller로 `dist/shotsort.app`을 만든 뒤 DMG를 만들지만, 현재는 무서명이고 `rm -rf dist/dmg`/`rm -f dist/shotsort.dmg`로 이전 산출물을 교체한다. 서명은 **앱 패키징 전**, notarization/staple은 **DMG 패키징 후**에만 수행해야 한다.
- `docs/SIGNING.md`는 사람을 위한 초안이며, Developer ID Application 인증서, Team ID, app-specific password/키체인 notary profile이 필요하다고 명시한다. 저장소와 GitHub에는 이 비밀이나 Apple 계정 정보가 없다.
- `README.md`의 비개발자 설치는 현재 Gatekeeper 우회 및 `xattr`을 안내한다. `engine.py:check_update()`와 `app.py:do_update()`는 `.app` 설치에서 이미 GitHub 최신 릴리스 페이지를 열도록 되어 있어, 랜딩의 다운로드는 그 같은 `releases/latest` URL로 연결한다.
- 이슈 #7에는 댓글이나 생성된 child issue가 없고, 같은 배치의 #1/#4는 이미지 유사도 GUI 범위다. 따라서 #7은 그 UI를 수정하지 않고, 랜딩에는 현재 제공되는 유사 이미지 검사 기능을 과장 없이 소개한다.
- 회의록으로 지정된 `/tmp/pm-meeting-ifPeTC`는 계획 작성 시점에 존재하지 않았다. 아래 측정 구현은 별도 추적 SaaS를 전제하지 않는 GitHub 기반 대체 신호로 잡는다. 실제 외부 분석/폼 공급자를 쓰려면 그 계정·도메인·비밀은 후속 승인으로 추가한다.

## 사전 승인 게이트

릴리스에서 실제로 “Notarized Developer ID”를 만들려면 Apple Developer Program 가입과 다음 GitHub Actions secrets가 먼저 필요하다. 이 값이 없을 때도 Phase 1/2 코드는 비밀을 저장하거나 우회 설치를 권하지 않고, 서명 릴리스 job만 실행 불가로 명확히 실패해야 한다.

- `APPLE_CERTIFICATE_P12_BASE64`, `APPLE_CERTIFICATE_PASSWORD`: Developer ID Application 인증서와 private key
- `APPLE_TEAM_ID`, `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`: `notarytool` 제출용 자격증명
- (선택) `KEYCHAIN_PASSWORD`: CI 임시 키체인 암호. 없으면 workflow가 난수로 생성하고 job 종료 시 삭제한다.

이 게이트는 이슈 본문이 명시한 사용자 결정 사항이며, 인증서/비밀을 코드·문서 예시·로그에 커밋하지 않는다.

## 목표 계약

- `SIGN_IDENTITY`와 `NOTARY_PROFILE`을 제공한 macOS 빌드는 hardened runtime entitlements로 앱을 서명하고, DMG를 공증·staple한 뒤 검증한다. 둘 중 하나만 준 경우는 반쯤 배포 가능한 산출물을 만들지 않고 사용법 오류로 종료한다.
- 태그 릴리스는 `shotsort.dmg`와 SHA-256이 한 줄로 기록된 `shotsort.dmg.sha256`를 같은 GitHub Release에 첨부한다. smoke는 깨끗한 macOS runner에서 DMG mount → Applications로 복사 → signature/Gatekeeper/staple 검증 순으로 설치 경로를 확인한다.
- 공개 랜딩의 기본 다운로드 CTA는 GitHub `releases/latest`에 한 번에 도달하며, 최신 DMG와 checksum 검증 방법을 함께 안내한다. 서명 릴리스가 나오기 전에는 “서명·공증 대기 중” 상태와 소스 실행 경로만 보여 주고 Gatekeeper 우회 명령을 랜딩에 싣지 않는다.
- 랜딩은 설치 전에 로컬 OCR 처리, API 선택 시 OCR 텍스트 전송, 이미지 분석을 켠 경우에만 축소 이미지 전송, 휴지통 삭제/복구 가능성을 설명한다. FAQ에는 지원 macOS와 업데이트/DMG 검증을 포함한다.
- 별도 분석 SDK 없이 `download_click`은 다운로드 링크의 `?source=landing` 유입과 GitHub Release asset download count로 대체 측정한다. `install_success`는 앱 첫 실행 시 외부로 전송하지 않고, release asset download 대비 GitHub feedback issue template의 `installed-version` 제출 건수를 운영 대체 신호로 집계한다. `feedback_submit`은 동일 template로 실제 생성된 issue 수를 집계한다. 이들은 사용자 식별·분석 쿠키 없이 가능한 최소 신호이며, 정확한 전환율이 필요하면 이후 동의 기반 분석 도입을 별도 승인한다.

## 현재 구조와 선례

- `build_app.sh`의 PyInstaller hidden imports와 DMG Applications 심볼릭 링크를 보존한다. 서명/공증은 이 파일의 앱 생성과 `hdiutil create` 사이·뒤에 각각 넣는다.
- `docs/SIGNING.md`의 codesign, `notarytool`, `stapler`, `spctl` 명령과 환경변수 기반 비밀 관리 방향을 실행 가능한 runbook으로 갱신한다.
- `.github/workflows/ci.yml`의 checkout/setup-python/test 구성을 그대로 두고, release는 tag만 처리하는 독립 `.github/workflows/release.yml`로 둔다. 일반 PR CI가 Apple secrets나 macOS 비용에 의존하지 않는다.
- 정적 랜딩은 저장소 `docs/landing/`에 자체 HTML/CSS/소량 JavaScript로 둔다. 앱의 NiceGUI UI나 Python 런타임에 랜딩 코드를 섞지 않는다.

## Phase 1 — 재현 가능한 서명·공증 빌드 경계 (완료)

변경 파일: `build_app.sh`, `packaging/entitlements.plist`, `tests/test_build_app_contract.py`

선례: `build_app.sh`, `docs/SIGNING.md:1-4`, `.gitignore:빌드 산출물`

1. `packaging/entitlements.plist`에 PyInstaller 번들의 외부 dylib 로드에 필요한 최소 hardened-runtime entitlement(`allow-unsigned-executable-memory`, `disable-library-validation`)만 선언한다. 네트워크, 카메라, 파일 접근 entitlement는 추가하지 않는다.
2. `build_app.sh`에 `SIGN_IDENTITY`와 `NOTARY_PROFILE`의 쌍 검증을 추가한다. 둘 다 비어 있으면 현재의 로컬 무서명 빌드는 계속 가능하지만, 산출물 로그에 배포 불가 상태를 명시한다. 하나만 있으면 Apple 명령을 실행하기 전에 종료한다.
3. 쌍이 있으면 PyInstaller 산출물에 `codesign --force --deep --options runtime --timestamp --entitlements packaging/entitlements.plist`를 적용하고 `codesign --verify --deep --strict --verbose=2`를 통과시킨 뒤 DMG를 만든다. 이어 `notarytool submit --wait`, `stapler staple`, `stapler validate`, `spctl -a -vvv -t install` 순서로 실패를 전파한다. profile 이름·identity만 로그에 표시하고 비밀값은 출력하지 않는다.
4. `tests/test_build_app_contract.py`는 빌드 자체나 macOS 명령을 실행하지 않고 스크립트 텍스트/명령 순서를 고정한다: entitlement 경로, 쌍 변수 검증, sign→DMG→notarize→staple→검증, unsigned fallback 및 비밀 하드코딩 부재.

완료 기준: 로컬 개발자는 기존 무서명 빌드를 계속 만들 수 있고, 승인된 Developer ID/notary profile을 제공한 릴리스 빌드는 잘못된 순서나 부분 설정 없이 검증 가능한 stapled DMG를 만든다.

예정 커밋: `feat: [P1] #7 서명·공증 가능한 DMG 빌드 추가`

## Phase 2 — 태그 릴리스 checksum과 clean-macOS smoke (완료)

변경 파일: `.github/workflows/release.yml`, `scripts/release/verify_dmg.sh`, `scripts/release/smoke_install.sh`, `docs/SIGNING.md`

선례: `.github/workflows/ci.yml`, `build_app.sh`, `docs/SIGNING.md:검증 체크리스트`

1. `scripts/release/verify_dmg.sh`에 DMG SHA-256 생성/검증을 둔다. macOS의 `shasum -a 256`으로 `shotsort.dmg.sha256`을 생성하며, checksum 파일은 asset 파일명과 digest만 가져 재현 가능한 다운로드 검증 명령이 된다.
2. `scripts/release/smoke_install.sh`는 새 임시 mountpoint와 임시 Applications 디렉터리를 생성하고 DMG attach → `.app` 존재 확인 → 복사 → detach cleanup을 trap으로 보장한다. 복사본을 대상으로 `codesign --verify --deep --strict`, `spctl -a -vvv -t install`, `stapler validate`를 실행해 clean macOS 설치 계약을 자동 검증한다. 앱을 실제로 띄우거나 사용자 홈/실제 `/Applications`를 수정하지 않는다.
3. `.github/workflows/release.yml`은 `v*` tag push에서만 macOS runner로 실행한다. Actions secrets를 임시 keychain에 import하고, `SIGN_IDENTITY`/notary profile을 준비해 `build_app.sh` → checksum → smoke 순으로 실행하며, `shotsort.dmg`와 `.sha256`만 GitHub Release에 업로드한다. secret 누락은 unsigned asset을 발행하지 않고 사전 검증 단계에서 실패하게 한다.
4. `docs/SIGNING.md`를 계획형 설명에서 실제 운영 runbook으로 바꾼다: 처음 한 번의 인증서/profile 준비, 필요한 secrets 이름, tag 릴리스 절차, checksum 검증, smoke가 확인하는 범위와 수동 새 사용자 계정 최종 점검 절차를 기록한다.

완료 기준: 서명 권한이 설정된 tag 하나가 checksum을 포함한 공증 DMG release를 만들고, CI의 깨끗한 macOS 환경에서 설치 복사본이 Gatekeeper 검증을 통과한다. 권한이 없는 경우에는 배포하지 않고 필요한 secret을 알려 준다.

예정 커밋: `ci: [P2] #7 notarized DMG 릴리스와 설치 smoke 추가`

## Phase 3 — 개인정보·다운로드·FAQ 중심 공개 랜딩 (완료)

변경 파일: `docs/landing/index.html`, `docs/landing/styles.css`, `docs/landing/app.js`, `.github/workflows/pages.yml`, `README.md`

선례: `README.md:소개·설치·API 비용과 개인정보·안전장치`, `engine.py:REPO_SLUG`, `app.py:do_update`

1. `docs/landing/index.html`에 비개발자용 가치 제안, 실제 앱 화면 스크린샷 자리(릴리스 전 검증된 캡처 파일만 사용), 로컬/외부 AI 전송 비교, 복구 가능한 휴지통 삭제, 지원 macOS, 다운로드, checksum, FAQ, feedback CTA를 구성한다. 첫 CTA와 header CTA는 모두 `https://github.com/sj48695-labs/shotsort/releases/latest?source=landing`을 향하게 하며 release 링크가 한 클릭임을 테스트 가능한 DOM 계약으로 둔다.
2. `docs/landing/styles.css`는 macOS 데스크톱/모바일에서 읽을 수 있는 반응형 레이아웃, 충분한 명암 대비와 키보드 focus 상태를 제공한다. 추적 배너/쿠키는 넣지 않는다.
3. `docs/landing/app.js`는 다운로드 클릭에 `source=landing`을 보존하고, feedback CTA에서 GitHub issue template URL에 제품 버전/설치 여부/동의한 피드백 내용을 명시해 보낼 수 있게 한다. 성공 알림을 위장하지 않으며 issue 생성이 `feedback_submit`, 설치됨으로 제출된 issue가 `install_success` 대체 신호임을 CTA 근처에 설명한다.
4. `.github/workflows/pages.yml`은 `main`의 `docs/landing/**` 변경에만 GitHub Pages artifact를 배포한다. Pages 설정은 repository settings에서 GitHub Actions source를 한 번 활성화해야 하며, workflow는 release secrets와 분리한다.
5. `README.md`의 비개발자 설치를 서명·공증 release 기준으로 갱신하고 기존 Gatekeeper 우회 안내를 제거한다. 랜딩 URL, DMG checksum, 소스 실행 대안과 privacy/feedback 섹션 링크를 추가해 GitHub README에서도 같은 약속을 유지한다.

완료 기준: Pages를 활성화한 뒤 공개 URL에서 1회 클릭으로 최신 release에 도달하고, 설치 전 데이터 전송 경계·복구 정책·지원 macOS·checksum·FAQ·피드백 방법을 이해할 수 있다. GitHub Release asset download, `source=landing` 유입, feedback issue/template 필드로 세 가지 최소 대체 신호를 운영자가 집계할 수 있다.

예정 커밋: `feat: [P3] #7 공개 설치 랜딩과 피드백 퍼널 추가`

## 검증

각 phase는 다음 범위에서 검증하고, 마지막 phase 후 전체 Python 회귀도 실행한다.

```bash
# Phase 1
python -m unittest tests/test_build_app_contract.py -v
bash -n build_app.sh

# Phase 2 (macOS 및 Apple secrets가 준비된 CI)
bash -n scripts/release/verify_dmg.sh scripts/release/smoke_install.sh
# tag push workflow에서 build → checksum → smoke → release asset 확인

# Phase 3
# GitHub Pages deployment 이후 Chromium/Playwright로 모바일·데스크톱 렌더,
# 최신 release CTA, FAQ 앵커, keyboard focus, feedback template URL 확인
python -m unittest discover -s tests -v
```

계획 단계에서는 구현 파일을 변경하지 않는다. 이 계획 파일만 커밋하며, worktree·브랜치 정리와 릴리스 tag 생성은 수행하지 않는다.
