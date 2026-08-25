# #7 서명·공증 설치 경로와 공개 제품 랜딩 운영 완료 계획

## 재검토 결과

이 계획은 기존 `plans/7-install-landing.md`와 2026-08-26의 최신 이슈 댓글을 대조해 다시 작성했다.

- 유지할 완료 구현: `[P1]` Pages enablement/초기 배포 토큰 계약은 `b15e6d5`, `352f00f`에 이미 있고, feedback URL의 존재하지 않는 `feedback` label 제거와 README·계약 테스트는 `e56242a`에 이미 있다. 이 파일들을 같은 목적으로 다시 구현하지 않는다.
- 정정: 이전 계획에 한때 `P2 (완료)`로 표시됐지만 실제 `docs/landing/assets/shotsort-demo.*`가 없고 랜딩에 실제 앱 화면도 없다. 따라서 P2는 미완료다.
- 새 운영 사실: Pages API와 공개 URL은 아직 404이며, 마지막 Pages run `32788215746`은 `configure-pages`에서 실패했다. `enablement: true`와 `PAGES_SETUP_TOKEN` fallback 코드는 존재하지만 repository Pages를 GitHub Actions source로 허용하는 외부 설정이 선행돼야 한다.
- 새 운영 사실: 공개 최신 Release는 여전히 `v0.1.1`(2026-06-15)의 `shotsort.dmg` 하나이며 checksum asset이 없다. 2026-08-26 댓글이 지목한 release run들 중 `32872470729`도 실패다. signed/notarized/stapled DMG와 clean-user smoke의 공개 증거가 아직 없다.
- 이슈 본문의 완료 조건(무경고 설치, clean-user runbook, 최신 release 1-click, 처리 경계, download/feedback 신호)은 변하지 않았다. 그러므로 현재의 “공증 릴리스 준비 중” 문구와 unsigned 설치 fallback은 실제 운영 검증 전까지 유지한다.
- PR #10은 `7-install-landing` → `main`의 닫힌 Draft PR이다. 이 이슈에서 새 브랜치나 새 PR을 만들지 않으며, 후속 통합은 기존 PR #10을 재개해 사용한다. 열린 rescue PR #12는 이 계획의 산출물이나 새 통합 경로로 취급하지 않는다.
- 회의록 경로 `/tmp/pm-meeting-JqcUf3`는 현재 worktree 환경에 존재하지 않아 읽을 수 없었다. 위 최신 이슈 본문·댓글과 PM 지침을 계획 근거로 사용했다.

## 현재 구조와 선례

| 관심사 | 현재 파일/상태 | 따를 선례 |
| --- | --- | --- |
| Pages 배포 | `.github/workflows/pages.yml`; `configure-pages@v5`, `enablement: true`, `PAGES_SETUP_TOKEN` fallback 구현 완료, 실제 Pages site는 미활성 | GitHub Actions source 활성화 → workflow dispatch → `upload-pages-artifact@v3` → `deploy-pages@v4` |
| 릴리스 공증 | `.github/workflows/release.yml`, `build_app.sh`, `scripts/release/verify_dmg.sh`, `scripts/release/smoke_install.sh`; 코드 계약은 있으나 실제 release 실패 | `$RUNNER_TEMP/shotsort-signing.keychain-db`에서 sign → notarize → staple → checksum → clean smoke → publish |
| 공개 문구/신호 | `docs/landing/index.html`, `app.js`, `README.md`; CTA는 `releases/latest?source=landing`, feedback은 label 없이 Issue prefill | 검증 전 “준비 중”, 검증 후에만 Gatekeeper 우회 불필요/asset 상태로 전환 |
| 계약 회귀 | `tests/test_landing_contract.py`, `tests/test_build_app_contract.py` | macOS 도구·비밀값 없이 workflow와 공개 약속을 텍스트 계약으로 검증 |

## 범위와 비범위

- #4, #11, #1의 앱 기능은 변경하지 않는다. P2의 캡처는 샘플 데이터로 실제 shotsort를 실행해 얻은 정적 증거만 사용하며, imagegen/mockup은 사용하지 않는다.
- 인증서 값, Apple ID, app-specific password, 토큰은 채팅·문서·git·workflow 로그에 기록하지 않는다. GitHub Actions secrets와 runner의 임시 keychain만 사용한다.
- Pages 설정, repository secrets 등록, 새 release tag 생성, 깨끗한 macOS 사용자에서의 수동 smoke는 운영자 권한이 필요한 검증 행동이다. 코드가 이를 대신했다고 주장하지 않는다.
- worktree/브랜치 정리·전환·삭제와 새 브랜치/PR 생성은 하지 않는다.

## 구현 phases

### P1 (완료) — Pages enablement와 피드백 URL 계약 복구

완료 커밋: `b15e6d5`, `352f00f`, `e56242a`.

- `.github/workflows/pages.yml`에 Pages enablement 및 첫 배포용 `PAGES_SETUP_TOKEN` fallback이 있다.
- `README.md`, `docs/landing/app.js`, `tests/test_landing_contract.py`에서 허용되지 않은 `feedback` label 요구를 제거했다.
- P1은 구현 완료일 뿐, 실제 Pages deployment 성공은 아래 P3의 운영 검증 전까지 완료로 판정하지 않는다.

### P2 — 실제 앱 스크린샷을 설치 전 랜딩에 추가

변경 파일(최대 4개):

- `docs/landing/assets/shotsort-demo.png`: 샘플 데이터로 실행한 실제 앱 UI 캡처. 개인 경로, API key, 사용자 이미지·OCR 텍스트는 마스킹한다.
- `docs/landing/index.html`: hero 뒤에 실제 화면임을 명시한 `<figure>`와 분류·그룹·휴지통을 설명하는 alt text를 추가한다. 기존 최신 release CTA와 처리 경계 문구는 유지한다.
- `docs/landing/styles.css`: 이미지의 desktop/mobile 반응형 폭, 테두리/그림자, focus·고대비에서의 가독성을 기존 랜딩 톤에 맞춘다.
- `tests/test_landing_contract.py`: asset 존재, `<img>` 참조, 의미 있는 alt text와 기존 CTA/privacy/FAQ/feedback 계약을 검증한다.

구현/검증:

1. 샘플 데이터에서 앱의 분류·그룹·휴지통 화면을 직접 확인하고, 위 민감 정보를 제거한 캡처를 만든다.
2. 로컬 정적 서버에서 macOS desktop 및 mobile 폭으로 가로 스크롤·텍스트 겹침 없이 보이는지 검토한다.
3. `python -m unittest tests.test_landing_contract -v`와 `python -m unittest discover -s tests -v`를 통과시킨다.

커밋: `feat: [P2] #7 실제 앱 데모를 설치 랜딩에 추가`

### P3 — 이미 구현된 Pages 경로의 실제 배포 검증

코드 변경 없음(운영 phase). 실패 원인이 `Pages site` 404인 동안 workflow/README/token 계약을 중복 수정하지 않는다.

운영 검증:

1. repository Settings → Pages에서 Pages를 활성화하고 source를 **GitHub Actions**로 설정한다. 첫 배포 권한이 기본 `GITHUB_TOKEN`으로 부족하면 `PAGES_SETUP_TOKEN`만 Actions secret으로 등록한다.
2. 기존 PR #10을 재개·통합한 뒤 `Deploy landing page`를 workflow dispatch로 실행한다. 새 PR은 만들지 않는다.
3. run 성공과 deployment URL을 확인한 뒤 `https://sj48695-labs.github.io/shotsort/`가 200으로 열리는지 확인한다. 실제 화면에서 release CTA의 `source=landing` 및 feedback form prefill을 점검한다.
4. 설정 후에도 실패하면 run URL·실패 단계·Pages API 상태만 이슈/PR 체크에 기록한다. 토큰 값이나 추측성 YAML 변경은 추가하지 않는다.

완료 증거: 성공한 Pages run URL, 공개 URL 200, CTA/feedback 수동 확인 기록.

### P4 — notarized DMG의 실패 원인 한정 보강과 실제 release 검증

변경 파일(문제 원인이 코드일 때만, 최대 5개):

- `.github/workflows/release.yml`: 실패 step이 보여 주는 원인에 한해 secret preflight, 임시 keychain, `always()` cleanup 또는 publish 순서를 수정한다.
- `build_app.sh`: Developer ID signing, hardened runtime, `notarytool` submit/staple/Gatekeeper 순서 문제일 때만 수정한다.
- `scripts/release/smoke_install.sh`: stapled DMG 검사 후 새 mountpoint와 임시 Applications 경로의 clean install 검사 문제일 때만 수정한다.
- `tests/test_build_app_contract.py`: 변경한 비밀 격리·명령 순서·smoke 계약만 갱신한다.
- `docs/SIGNING.md`: secret **이름**, 등록 위치, 비밀을 노출하지 않는 runbook만 보강한다.

운영 검증:

1. 실패 run의 첫 실패 step을 확인한다. 누락/권한 문제면 workflow를 다시 고치지 않고 운영자가 `SIGN_IDENTITY`, `APPLE_CERTIFICATE_P12_BASE64`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_SPECIFIC_PASSWORD` 및 선택 `KEYCHAIN_PASSWORD`를 Actions secrets로 등록한다.
2. 코드 변경 시 먼저 `python -m unittest tests.test_build_app_contract -v`와 전체 unittest를 통과시킨다.
3. 새 `v*` tag로 release를 실행한다. 무서명 DMG를 우회용으로 publish하거나 기존 release를 대체하지 않는다.
4. Release에 `shotsort.dmg`와 `shotsort.dmg.sha256`가 모두 존재하고, Actions의 codesign/notarize/staple/checksum/smoke가 모두 성공했는지 확인한다.
5. 새 macOS 사용자에서 Release DMG를 다운로드해 checksum, Applications 복사, 첫 실행, `spctl`/Gatekeeper 무경고를 확인한다.

커밋(코드 보강이 필요한 경우에만): `fix: [P4] #7 공증 release 운영 계약 보강`

### P5 — 검증된 운영 상태만 공개 문구에 반영

선행 조건: P2의 실제 캡처, P3의 공개 Pages deployment, P4의 성공한 notarized release와 clean-user smoke가 모두 증거로 확인돼야 한다. 하나라도 없으면 변경하지 않고 “공증 릴리스 준비 중” 및 현재 fallback을 유지한다.

변경 파일(최대 4개):

- `docs/landing/index.html`: 준비 중 문구를 실제 latest version의 Gatekeeper 우회 불필요 설치·checksum 안내로 교체한다.
- `README.md`: unsigned fallback을 같은 verified release 상태로 갱신하고 landing/latest release 진입점을 유지한다.
- `tests/test_landing_contract.py`: 준비 중 문구가 사라진 경우 notarization·일반 설치·checksum 약속을 모두 검증한다.
- `docs/SIGNING.md`(필요 시): 비밀 없이 release version, run URL, clean-user smoke 완료 체크를 기록한다.

구현/검증:

1. 공개 landing/README의 모든 download CTA가 최신 release로 가고 두 asset이 존재하는지 확인한다.
2. feedback prefill의 `installed-version`, `installation-status`와 `source=landing` 신호를 수동 확인한다.
3. landing 계약과 전체 unittest를 통과시키고, Pages 재배포 후 공개 URL을 다시 확인한다.

커밋: `docs: [P5] #7 검증된 공증 설치 상태 공개`

## 최종 완료 판정

1. Pages deployment가 성공했고 공개 랜딩이 200으로 열리며 실제 앱 데모, 처리 경계, FAQ, feedback CTA가 보인다.
2. 최신 GitHub Release에 Developer ID signed/notarized/stapled `shotsort.dmg`와 `shotsort.dmg.sha256`가 있다.
3. 새 macOS 사용자에서 우회 명령 없이 drag-to-Applications, 첫 실행 및 Gatekeeper 검증이 통과한다.
4. landing과 README가 위 최신 release 상태와 일치하고 “준비 중” 또는 unsigned fallback이 남아 있지 않다.
5. `source=landing` download 신호와 feedback/install-status prefill이 동작하며, 존재하지 않는 label을 요구하지 않는다.
