# #7 plan 실행·검증 기록

이 파일은 증적 보관용이다. `/plan`·`/code` 기본 입력은 옆 `7-install-landing.md`이며, 실패 원인 등 필요한 절만 명시적으로 읽는다.

## 2026-11-13 재계획 검증

- 현재 브랜치 `7-install-landing`, 작업 시작 HEAD 및 PR #18 head `ae9a9141c9f25e88c51319dc83c414408ba5bcba`. 작업 시작 시 clean.
- 이슈 본문·댓글 전체와 close/reopen timeline 조회. 2026-09-18 재오픈은 공증 DMG만 잔여라고 명시. 2026-11-11/13 댓글은 기존 공증 수정 재구현 금지, PR #18 재사용, 실제 공증·checksum·설치 증거 및 CTA/Release 정합성 확인을 요구.
- PR #18 OPEN/Draft, CI test SUCCESS: https://github.com/sj48695-labs/shotsort/actions/runs/41743214046/job/126289646881 . 이 성공은 실제 공증 증거가 아니다.
- PR #12 MERGED (`9f4d100f3f361ad13f42152d0230b9ac3c59588d`), PR #10 CLOSED. Pages `build_type=workflow`, 성공 run https://github.com/sj48695-labs/shotsort/actions/runs/35331224051 . 재활성화/중복 PR 통합 불필요.
- 공개 랜딩 HTTP 200(6640 bytes), 데모 PNG HTTP 200(89650 bytes). HTML에 준비 중·데모·source=landing·로컬 OCR·OCR 텍스트 설명 존재, install_success/feedback_submit 없음. 브라우저 1280/390·포커스·폼 이동은 이번 plan에서 실행하지 않았다.
- `gh secret list --json name` 결과 `[]`: repository-level Apple secrets 미연결. 조직/환경 secret 범위까지 확인했다는 뜻은 아니다. 실제 release 성공 증거도 없음.
- latest Release v0.1.1: https://github.com/sj48695-labs/shotsort/releases/tag/v0.1.1 . asset은 shotsort.dmg 하나, shotsort.dmg.sha256 없음. GitHub asset digest가 있어도 다운로드 가능한 checksum 파일 또는 공증 증거를 대체하지 않는다.
- Release 본문에는 xattr가 없지만 `시스템 설정 → 개인정보 보호 및 보안 → **"그래도 열기"**`가 남아 있다. 무서명임은 명시됨. 새 plan의 P6에 우회 안내 제거를 독립 작업으로 반영.
- 최근 release run https://github.com/sj48695-labs/shotsort/actions/runs/42892858163 : failure, jobs=[], 다른 브랜치 SHA 45419136c31d87f663d05b9d1913738c32590248. PR #18 수정 재실패나 Apple secret preflight 실행 결과로 해석하지 않는다.
- `/tmp/pm-meeting-ww5VhN` 파일 없음. 최신 이슈 댓글과 사용자 PM 지침으로 요구사항 확인.
- 자체 검토 2회: 완료 phase·커밋 보존, 운영/코드 완료 구분, P6 우회 안내 누락 보완, phase당 파일 5개 이하, 의존성·검증·권한 경계 확인.
- plan 재작성 완료. 제품 코드 변경·테스트 재실행·rebase·push·태그·Release 편집·Ready/merge·worktree 정리 없음. 문서 diff 검증 후 plan과 본 기록을 함께 커밋한다.

## 이관 원문 — 재작성 전 plan 전체 (과거 사실 포함)

아래 원문은 삭제 없이 보존한 과거 기록이다. PR #10 재개, Pages 404 등은 현재 지시가 아니며 최신 판단에는 사용하지 않는다.

# #7 서명·공증 설치 경로와 공개 제품 랜딩 운영 완료 계획

## 2026-09-18 fast-track

- 착지 대상은 rescue PR #12. 같은 파일의 PR #10은 병합 후 닫는다. 새 브랜치에서 데모 이미지를 다시 만들지 않는다.
- Pages는 이미 `https://sj48695-labs.github.io/shotsort/` 200. P3 운영 검증의 404 전제는 구식이다.
- 카피: 히어로 `무료로 다운로드` 제거, 피드백 은어 제거, sha256은 공증 릴리스에 있을 때만 안내.
- 공증 DMG(이슈 Phase 3)는 Apple secrets 없이 코드로 통과시키지 않는다. 이 PR은 #7을 close하지 않는다.

## 2026-11-04 code 재개 — P3 운영 증거

- 최신 이슈 댓글(2026-09-18): PR #12는 카피·데모만 병합했으며 Apple secrets 연결 전에는 공증 단계를 코드로 완료하지 않는다.
- PR #12는 2026-09-18 병합됐고 PR #10은 closed다. 아래 과거 재검토의 PR #10 재개·Pages 404 전제는 더 이상 적용하지 않는다. PR 통합·재배포를 중복 실행하지 않는다.
- Pages API `build_type=workflow`. 성공한 [Pages run 35331224051](https://github.com/sj48695-labs/shotsort/actions/runs/35331224051)은 병합 커밋 `9f4d100`을 배포했다.
- 공개 랜딩과 `assets/shotsort-demo.png` 모두 HTTP 200. 랜딩 계약 테스트 6개 통과.
- 브라우저에서 공개 랜딩 제목·CTA 3개·데모·privacy·FAQ·피드백 폼의 로딩을 확인했다. 추가 반응형·피드백 이동 검사는 CLI 패키지 로딩 오류(`Cannot find module .../playwright-core/browsers.json`)로 완료하지 못했다. 제품 UI는 변경하지 않았다. P3 헤딩은 수동 흐름 검증 완료 전까지 미완료로 유지한다.

## 이전 재검토 결과 (2026-08-26 당시 기록)

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

### P2 (완료) — 실제 앱 스크린샷을 설치 전 랜딩에 추가

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

완료 증거: 분리된 임시 홈 디렉터리에서 샘플 이미지 4장을 로컬 OCR로 스캔하고, 분류된 그룹·그룹 폴더 정리·선택 항목 휴지통 UI가 보이는 실제 앱 화면을 `docs/landing/assets/shotsort-demo.png`으로 캡처했다. 개인 파일, OCR 텍스트, API 키는 포함하지 않았다.

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

#### 2026-11-04 P4 코드 보강과 운영 차단

- [실패 run 39135901697](https://github.com/sj48695-labs/shotsort/actions/runs/39135901697)은 job 생성 전 workflow 검증에서 거부됐다. annotation: `(Line: 17, Col: 24): Unrecognized named-value: 'runner'` (`runner.temp`).
- 원인 한정 수정: `NOTARY_KEYCHAIN`을 job `env`에서 실제 사용하는 빌드 step `env`로 옮겼다. 임시 keychain 경로·secret preflight·cleanup·공증 후 publish 순서는 유지한다.
- 회귀 계약으로 job 환경의 잘못된 참조를 검출(수정 전 실패), 빌드 step의 경로 전달을 검증한다. 수정 후 서명 계약 테스트 8개, 전체 unittest 113개, CI 표준 compileall, actionlint v1.7.7의 release workflow 검사, `git diff --check` 통과. 별도 typecheck/lint 명령은 저장소에 없다.
- `gh secret list --json name`은 `[]`. 최신 공개 릴리스는 여전히 `v0.1.1`, asset은 `shotsort.dmg` 하나이며 checksum은 없다.
- 운영자 다음 작업: `docs/SIGNING.md`의 필수 Apple secret 6개 등록 → 검증 커밋의 새 `v*` 태그로 workflow 실행 → DMG/checksum 및 CI smoke 확인 → 새 macOS 사용자 설치·첫 실행 확인. 이번 실행에서는 태그·릴리스·secret을 변경하지 않는다.
- P4 운영 완료가 아니므로 P5는 선행 조건 미충족으로 보류한다. 공개 준비 중 문구와 fallback을 유지한다.

#### 2026-11-04 코드 리뷰 — Gatekeeper 검사 대상 수정

- 플랜·이슈에 `## Spec` 또는 S# 정의는 없다. 최신 이슈의 Phase별 완료 조건과 수용 조건을 기준으로 리뷰했다.
- [P1] `spctl -t install`은 설치 패키지 검사 유형인데 DMG와 `.app`에 사용돼, 자격증명을 연결해도 올바른 공증 설치 검증을 할 수 없었다. DMG 자체 서명도 빠져 있었다.
- `build_app.sh`에서 DMG를 Developer ID로 서명한 뒤 공증하고 `open` 유형으로 검사하도록 수정했다. `scripts/release/smoke_install.sh`는 복사한 앱을 `execute` 유형으로 검사한다. 근거: 로컬 `spctl(8)` 및 [Apple DMG 서명 안내](https://developer.apple.com/library/archive/technotes/tn2206/).
- 회귀 계약은 수정 전 실패를 확인했다. 수정 후 서명·랜딩 계약 테스트 15개, 변경 셸 스크립트의 구문 검사, release workflow의 actionlint, `git diff --check`를 통과했다. 전체 테스트는 변경 범위 밖이므로 실행하지 않았다.
- 운영 재확인: PR #12는 병합, #10은 닫힘. Apple secrets는 여전히 `[]`, 최신 공개 릴리스 `v0.1.1`에는 DMG만 있고 checksum은 없다. 릴리스 본문에 `xattr`는 없다. 공증 DMG·새 macOS 사용자 첫 실행·설치 가능한 최신 산출물 조건은 미충족이며 출시 통과로 판정하지 않는다.
- 공개 데모 이미지는 HTTP 200, Pages 설정은 `build_type=workflow`로 재확인했다. 브라우저 연결 도구는 모듈 가져오기 오류, 별도 Playwright는 임시 캐시로 옮긴 뒤에도 Chrome 실행 직후 `SIGABRT`로 종료됐다. 1280/390 화면·피드백 이동은 검증하지 못했다. 제품 UI 파일은 수정하지 않았다.

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


## 2026-11-13 /code #7 — P6 릴리스 안내 정합성

- 승인된 /code 실행으로 기존 v0.1.1 body의 설치 절만 편집했다. 외부 이슈 제출·tag·asset 변경 없음.
- URL: https://github.com/sj48695-labs/shotsort/releases/tag/v0.1.1
- 전후 body를 API로 조회하고 설치 절 앞 변경 내역과 뒤 개발자 안내의 동일성을 assert로 검증했다.
- release id/tag/target_commitish/published_at/assets/draft/prerelease 전체 동일성 assert PASS.
- 우회 명령 및 보안 예외 안내 부재 assert PASS.

### 편집 전 body

```markdown
## 변경
- 앱 내 **업데이트 알림** — 새 릴리스가 나오면 상단 배너로 알리고 다운로드 페이지로 안내
- 첫 실행(Gatekeeper) 안내 개선

## 설치 (비개발자)
1. **shotsort.dmg** 다운로드 → 열기 → **shotsort 를 Applications 로 드래그**
2. 첫 실행: 시스템 설정 → 개인정보 보호 및 보안 → **"그래도 열기"**

API 키 없이 무료 로컬 모드로 동작. 서명 안 된 빌드입니다. 공증 릴리스가 준비되기 전에는 Gatekeeper 우회 명령을 안내하지 않습니다.

## 개발자
`git clone` 후 `./run.sh` — README 참고.
```

### 편집 후 body

```markdown
## 변경
- 앱 내 **업데이트 알림** — 새 릴리스가 나오면 상단 배너로 알리고 다운로드 페이지로 안내
- 첫 실행(Gatekeeper) 안내 개선

## 설치 안내
이 버전의 `shotsort.dmg`는 서명·공증되지 않은 빌드입니다. 공증 릴리스 준비 중이며, 준비 전에는 아래 소스 실행 경로를 이용해 주세요.

API 키 없이 무료 로컬 모드로 동작합니다.

## 개발자
`git clone` 후 `./run.sh` — README 참고.
```


## 2026-11-13 /code #7 — P3 公開 랜딩 브라우저 검증 (완료)

- 대상: https://sj48695-labs.github.io/shotsort/ ; Chromium 1248, 1280×900 및 390×900.
- Pages 성공 run: https://github.com/sj48695-labs/shotsort/actions/runs/35331224051 ; SHA `9f4d100f3f361ad13f42152d0230b9ac3c59588d`.
- 기존 CSS/한국어 카피를 유지하는 ui-design match mode. 제품 파일 변경 없음.
- 각 폭에서 가로 넘침 없음(scrollWidth=viewport), 실제 데모 naturalWidth=1440. 스크린샷을 열어 데스크톱 포커스와 모바일 데모·FAQ를 시각 확인했다.
- Tab 순서: skip link → 홈 → (데스크톱 개인정보/FAQ) → 헤더 CTA → 히어로 CTA → 개인정보 링크 → 다운로드 CTA → FAQ summary 4개 → 버전 → 설치 상태 → 내용 → 피드백 버튼 → footer. 모바일은 가로 스크롤 가능한 pre도 브라우저 기본 포커스를 받음. 모든 링크/입력/summary/버튼의 파란 3px 포커스 확인.
- 개인정보 링크 클릭 및 FAQ 4개 펼침 성공. 로컬 OCR/외부 API OCR 텍스트·선택적 축소 이미지 전송 설명 유지.
- 각 폭에서 CTA 3개를 실제 클릭: `https://github.com/sj48695-labs/shotsort/releases/latest?source=landing` → `https://github.com/sj48695-labs/shotsort/releases/tag/v0.1.1`. 도착 페이지의 미서명·미공증 문구와 보안 예외 안내 부재 assert PASS.
- 각 폭에서 빈 피드백/한국어 예시를 submit해 Issue 작성 URL로 이동했다. label 강제 없음, 버전·설치 상태·한국어·&·줄바꿈 보존 assert PASS. GitHub 로그인 화면으로 이동하므로 로그인 이후 작성 화면은 미검증; 이슈 제출 없음. return_to에 원래 Issue 초안 URL이 보존됨.
- 빈 body: `installed-version: not-provided\ninstallation-status: installed\n\n(no additional feedback)`.
- 한국어 body: `installed-version: v0.1.1\ninstallation-status: issue\n\n설치 중 창이 열리지 않아요. 한글 & 줄바꿈\n다시 시도했습니다.`
- 관찰된 빈 초안 URL: https://github.com/sj48695-labs/shotsort/issues/new?title=Feedback%3A+shotsort+installation&body=installed-version%3A+not-provided%0Ainstallation-status%3A+installed%0A%0A%28no+additional+feedback%29
- 관찰된 한국어 초안 URL: https://github.com/sj48695-labs/shotsort/issues/new?title=Feedback%3A+shotsort+installation&body=installed-version%3A+v0.1.1%0Ainstallation-status%3A+issue%0A%0A%EC%84%A4%EC%B9%98+%EC%A4%91+%EC%B0%BD%EC%9D%B4+%EC%97%B4%EB%A6%AC%EC%A7%80+%EC%95%8A%EC%95%84%EC%9A%94.+%ED%95%9C%EA%B8%80+%26+%EC%A4%84%EB%B0%94%EA%BF%88%0A%EB%8B%A4%EC%8B%9C+%EC%8B%9C%EB%8F%84%ED%96%88%EC%8A%B5%EB%8B%88%EB%8B%A4.
- 스크린샷(로컬 증거): `/tmp/shotsort7-code-evidence/p3-{1280,390}-{focus,demo,privacy,faq,feedback-empty,feedback-korean}.png` (총 12개). Git에는 이 텍스트 증거를 보존한다.
- 브라우저 console: 기존 favicon.ico 404만 관찰(범위 밖 Skip). 제품 JS 오류 없음.
- 복구 이력: 내장 브라우저 bootstrap은 node:process import 제한, CLI 기본 cache 쓰기는 EPERM. 임시 daemon 경로로 전환했으나 샌드박스 Chromium은 SIGABRT. 자동 승인된 샌드박스 외 실행에서 성공. URL 파싱 검증 스크립트는 브라우저 문맥으로 수정 후 PASS.
- targeted: `python3 -m unittest discover -s tests -p test_landing_contract.py -v` — 6 tests PASS.

### 실제 레이아웃·키보드 관찰값

```json
[{"width":1280,"layout":{"viewport":1280,"scrollWidth":1280,"demoWidth":1440},"order":[{"tag":"A","id":"","text":"본문으로 건너뛰기","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"A","id":"","text":"shotsort","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"A","id":"","text":"개인정보","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"A","id":"","text":"FAQ","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"A","id":"","text":"최신 버전 받기","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"A","id":"","text":"GitHub Release 열기","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"A","id":"","text":"데이터 처리 방식 보기 ↓","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"A","id":"","text":"GitHub Release 열기","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"SUMMARY","id":"","text":"어떤 macOS를 지원하나요?","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"SUMMARY","id":"","text":"업데이트는 어떻게 하나요?","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"SUMMARY","id":"","text":"DMG가 바뀌지 않았는지 어떻게 확인하나요?","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"SUMMARY","id":"","text":"유사한 이미지도 찾나요?","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"INPUT","id":"installed-version","text":"","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"SELECT","id":"installation-status","text":"설치 완료아직 설치하지 않음설치 중 문제 발생","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"TEXTAREA","id":"feedback-text","text":"","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"BUTTON","id":"","text":"GitHub에서 피드백 작성","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"A","id":"","text":"GitHub","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"BODY","id":"","text":"본문으로 건너뛰기\n    \n      shot","outline":"rgb(23, 33, 29) none 3px"},{"tag":"A","id":"","text":"본문으로 건너뛰기","outline":"rgb(22, 102, 214) solid 3px"}]},{"width":390,"layout":{"viewport":390,"scrollWidth":390,"demoWidth":1440},"order":[{"tag":"A","id":"","text":"본문으로 건너뛰기","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"A","id":"","text":"shotsort","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"A","id":"","text":"최신 버전 받기","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"A","id":"","text":"GitHub Release 열기","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"A","id":"","text":"데이터 처리 방식 보기 ↓","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"PRE","id":"","text":"shasum -a 256 -c shotsort","outline":"rgb(0, 95, 204) auto 1px"},{"tag":"A","id":"","text":"GitHub Release 열기","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"SUMMARY","id":"","text":"어떤 macOS를 지원하나요?","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"SUMMARY","id":"","text":"업데이트는 어떻게 하나요?","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"SUMMARY","id":"","text":"DMG가 바뀌지 않았는지 어떻게 확인하나요?","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"SUMMARY","id":"","text":"유사한 이미지도 찾나요?","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"INPUT","id":"installed-version","text":"","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"SELECT","id":"installation-status","text":"설치 완료아직 설치하지 않음설치 중 문제 발생","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"TEXTAREA","id":"feedback-text","text":"","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"BUTTON","id":"","text":"GitHub에서 피드백 작성","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"A","id":"","text":"GitHub","outline":"rgb(22, 102, 214) solid 3px"},{"tag":"A","id":"","text":"본문으로 건너뛰기","outline":"rgb(22, 102, 214) solid 3px"}]}]
```


## 2026-11-13 /code #7 — P4 운영 차단 및 P5 보류

- `gh api repos/sj48695-labs/shotsort/actions/secrets`: `{"total_count":0,"secrets":[]}`. 이름·개수만 조회했고 값은 접근/출력하지 않았다.
- 필수 `SIGN_IDENTITY`, `APPLE_CERTIFICATE_P12_BASE64`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_SPECIFIC_PASSWORD` 미연결. 선택 `KEYCHAIN_PASSWORD`도 없음.
- 최신 공개 release: https://github.com/sj48695-labs/shotsort/releases/tag/v0.1.1 ; published_at `2026-06-15T11:04:04Z`. asset `shotsort.dmg` 하나(size 63072533 bytes, id 448095373), `shotsort.dmg.sha256` 없음. digest만으로 checksum 검증을 대체하지 않았다.
- SHA `ae9a9141c9f25e88c51319dc83c414408ba5bcba`의 CI 성공 https://github.com/sj48695-labs/shotsort/actions/runs/41743214046 은 실제 공증 성공 증거가 아니다.
- 공증 Accepted/staple/codesign/DMG open/앱 execute 평가/공개 sidecar checksum/clean-install 첫 실행·업데이트의 신규 운영 증거 없음. 새 사용자 계정/기기를 생성하거나 기존 사용자 환경에 설치하지 않았다.
- P4는 운영 차단 상태 유지. 기존 keychain·DMG 서명·Gatekeeper·smoke 코드는 변경하지 않았고 tag/workflow/release asset/secret도 변경하지 않았다. 이 [P4] 커밋은 차단 증적만 보존하며 운영 완료가 아니다.
- P5는 P4 실제 증거 의존으로 보류. 랜딩·README·계약 테스트의 공증 준비 중 상태를 유지한다.
- 재개 조건: 운영자가 필수 Apple secrets 연결 → 별도 권한의 릴리스 단계에서 검증 SHA의 새 v* release → 공증·staple·두 asset checksum·CI smoke 증거 및 새 사용자 첫 실행·업데이트 확인 → P5 공개 문구 전환.
- targeted: `python3 -m unittest discover -s tests -p test_build_app_contract.py -v` — 9 tests PASS.

## 2026-11-13 최종 표준 검증

- `python3 -m unittest discover -s tests -v`: 114 tests, OK (1.079s). 원본 로컬 로그 `/tmp/shotsort7-full-tests.log`.
- CI 표준 `python3 -m compileall -q app.py cli.py engine.py lazy_groups.py preview_layout.py providers.py shotsort.py`: PASS.
- `git diff --check`: PASS. 별도 typecheck/lint 명령은 저장소 CI에 정의되어 있지 않음.
- 브랜치/worktree 전환·삭제·rebase·push·PR Ready/merge·이슈 종료는 실행하지 않음. 후속 commit-mr/review 파이프라인에 맡긴다.
