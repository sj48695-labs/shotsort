# #7 서명·공증 설치 경로와 공개 제품 랜딩 잔여 계획

- 플랜식별자: `2E2B3867`
- 출처: [이슈 #7](https://github.com/sj48695-labs/shotsort/issues/7), 2026-09-18 재오픈 및 2026-11-11/13 PM 댓글.
- 작업 대상: 기존 `7-install-landing` 브랜치·현재 worktree·[Draft PR #18](https://github.com/sj48695-labs/shotsort/pull/18). 기준 구현 SHA `ae9a9141c9f25e88c51319dc83c414408ba5bcba`.
- **plan 재작성 완료 / 이슈 미완료·공증 운영 차단.** P1/P2와 P4 코드 수정은 보존한다. P3/P6 검증은 완료했으며, 잔여는 실제 공증·sha256·새 사용자 설치 증거와 그에 따른 P5 공개 설치 안내 전환이다.
- 실행·검증·이전 plan 원문은 `plans/7-install-landing.log.md`에 분리했다. 기본 입력으로 읽지 않으며 특정 증적이 필요할 때만 해당 절을 읽는다.

## 최신 요구사항과 판정

- 이슈 본문의 PR #10/#12 통합은 이미 완료됐다(#12 병합, #10 닫힘). Pages 404 복구·데모 재제작·새 child 이슈는 필요 없다.
- 최신 PM 지침에 따라 키체인 전달·DMG 서명·Gatekeeper 검사·설치 smoke를 다시 수정하지 않는다. CI 성공은 공증 및 실제 첫 실행 성공을 뜻하지 않는다.
- repository secrets 목록은 비어 있다. 필수 Apple secrets 연결과 검증된 대상 SHA의 실제 release가 선행돼야 P4 운영을 완료할 수 있다. secret 값을 로그·문서·git에 남기지 않는다.
- latest `v0.1.1`에는 DMG만 있고 checksum 파일은 없다. 공증 완료로 홍보하지 않는다. 릴리스 노트의 “그래도 열기” 안내는 P6에서 제거했다. 무서명·미공증과 소스 실행 안내를 명시했으며 asset·tag·발행 시각은 유지했다.
- 공개 랜딩·데모는 HTTP 200이고 준비 중 안내가 있다. 브라우저 1280/390·키보드·CTA·피드백 이동은 P3에서 검증했다. 비로그인 상태이므로 피드백은 로그인 return_to의 초안 URL·값 보존까지 확인했다.

## 제품·디자인 기준

비개발자 Mac 사용자가 설치 전에 로컬/외부 AI 전송 차이를 이해하고, 실제 받을 수 있는 최신 산출물로 이동하는 것이 핵심 흐름이다.

- `ui-design` match mode: `docs/landing/styles.css`의 색·간격·포커스, `docs/landing/index.html`의 한국어 톤을 유지한다. 앱 UI 선례는 `app.py`; 이번 범위에서 수정하지 않는다.
- 카피에는 사용자가 할 일만 쓴다. 내부 신호 이름·Gatekeeper 우회 안내·검증되지 않은 설치 성공 약속을 노출하지 않는다.
- CTA, 개인정보, FAQ, 피드백, 실제 앱 캡처를 유지한다. UI 변경 시 1280px/390px·보이는 포커스·키보드·빈 피드백 상태·구체적 오류와 복구 경로를 브라우저로 확인한다. 결함이 확인된 범위만 고친다.
- 후속 tdd/서브에이전트 프롬프트에는 AGENTS.md의 디자인 스킬 절을 포함한다. 이번 plan은 직접 탐색했으며 Explore 하위 에이전트를 사용하지 않았다.

## 현재 구조와 수정 경계

| 경로·심볼 | 현재 역할·선례 | 잔여 작업 |
| --- | --- | --- |
| `.github/workflows/release.yml`의 `release` job | secrets 검사 → 임시 keychain → build → checksum → smoke → publish → cleanup | 기존 구현을 실행 증거와 대조; 반복 수정 금지 |
| `build_app.sh`의 `SIGN_IDENTITY`/`NOTARY_PROFILE` 분기 | hardened runtime 앱 서명, DMG 서명·공증·staple, DMG `spctl -t open` | 실제 공증 결과 확인 |
| `scripts/release/verify_dmg.sh`의 `VERIFY_CHECKSUM` 분기 | 휴대 가능한 checksum sidecar 생성/검증 | 공개 다운로드 파일 검증 |
| `scripts/release/smoke_install.sh`의 `INSTALLED_APP` | 임시 mount·Applications 복사, staple/codesign/`spctl -t execute` | CI 증거; 사용자 첫 실행은 별도 |
| `docs/SIGNING.md`의 최초 준비·smoke 절 | secret 이름·설치 검증 runbook | 동일 절차로 운영 증거 수집 |
| `.github/workflows/pages.yml`의 `deploy` job | `docs/landing`을 Pages에 배포 | 활성화 재구현 없이 배포 확인 |
| `docs/landing/index.html`의 `[data-download-cta]`, `.download`, `#faq` | latest 링크·공증 준비 상태·처리 경계 | 실제 release에 맞춘 안내 검증 |
| `docs/landing/app.js`의 `releaseUrl`, `#feedback-form` submit | `source=landing`, Issue prefill | 이동·값 보존 확인; 실제 이슈 제출 금지 |
| `tests/test_build_app_contract.py`의 `BuildAppContractTests` | 서명 순서·keychain·Gatekeeper 텍스트 계약 | 기존 코드 보존; 실제 macOS 증거 대체 불가 |
| `tests/test_landing_contract.py`의 `LandingContractTests` | CTA·준비 중·privacy·데모·feedback·Pages 계약 | P5 공개 상태 변경 시 계약도 갱신 |

변경 가능 제품 파일은 P5의 최대 4개뿐이다. 운영 증적과 phase 완료 표시는 plan 및 옆 log에 남긴다. 공통 추출/P0는 필요 없다. #11/#4/#1 기능 및 Hold PR #16은 범위 밖이다.

## Phase별 계획

기존 P 번호와 완료 마커는 보존한다. 이 문서의 P 번호는 이슈 본문의 Phase 번호와 다르다. P3/P6는 Apple 연결 없이 가능하고, P4는 외부 선행 조건이 있으며, P5는 P3/P4/P6 완료 후 진행한다. 각 phase는 약 45 turn 이내 한 관심사·한 커밋으로 제한한다.

### P1 (완료) — Pages enablement와 피드백 계약

- 보존 커밋: `b15e6d5`, `352f00f`, `e56242a`. 카피 정직성 보강 `54575dd`도 보존한다.
- 기존 파일: `.github/workflows/pages.yml`, `README.md`, `docs/landing/app.js`, `tests/test_landing_contract.py`.
- Pages/token fallback·미존재 feedback label 제거·공증 전 카피는 재구현하지 않는다. 기존 계약 테스트가 회귀 선례다.

### P2 (완료) — 실제 앱 데모 착지

- 보존 커밋: `2cbd376`, 병합 `9f4d100`(PR #12). PR #10은 닫혔다.
- 기존 파일: `docs/landing/assets/shotsort-demo.png`, `docs/landing/index.html`, `docs/landing/styles.css`, `tests/test_landing_contract.py`.
- 실제 샘플 앱 캡처를 유지한다. 새 캡처·브랜치·PR·통합 작업을 만들지 않는다.

### P3 (완료) — 공개 랜딩 흐름의 브라우저 검증

- 변경 파일: `plans/7-install-landing.log.md`, 본 plan의 완료 표시만(제품 코드 변경 없음).
- 선례: `docs/landing/index.html`의 CTA/FAQ/form, `docs/landing/app.js`의 `releaseUrl` 및 submit handler, `tests/test_landing_contract.py`.
- 1280px와 390px에서 공개 랜딩·실제 데모·privacy/FAQ·가로 넘침·키보드 순서·포커스를 확인한다. CTA 3개가 latest Release로 이동하며 준비 중 상태와 모순되지 않는지 검사한다.
- 빈 피드백과 예시 버전/설치 상태/한국어 내용을 각각 Issue 작성 화면으로 이동시켜 prefill 및 label 비강제를 확인하되 이슈를 제출하지 않는다. GitHub 로그인 요구가 있으면 그 한계와 생성 URL을 기록한다.
- 검증: URL·viewport·행동·관찰 결과·스크린샷 경로 기록. 브라우저 도구 장애는 검증 미완료이며 HTTP 200으로 대체하지 않는다. 기존 Playwright 모듈/Chrome 실패 경로를 맹목 반복하지 않고 사용 가능한 다른 브라우저 경로를 확인한다.
- 완료: 배포 성공·데모 200 외에 위 수동 흐름 증거가 있음. 발견한 제품 결함이 있으면 해당 파일·수용 조건을 plan에 먼저 구체화한다.
- 커밋: `docs: [P3] #7 공개 랜딩 흐름 검증 기록`.

### P4 — 실제 공증 DMG와 새 사용자 설치 증거 (운영 차단)

**코드 구현 완료, 운영 미완료.** 2026-11-13 `/code` 재조회에서도 repository secrets 0개, 최신 v0.1.1 asset은 DMG 1개뿐이다. P4 태그의 운영 차단 기록 커밋은 완료 증거가 아니며, 아래 실제 공증·설치 조건을 충족해야 재개 판정한다. `3aa6bef`의 keychain 전달과 `ae9a914`의 DMG 서명·Gatekeeper 검사 수정을 보존한다. 이 phase를 코드 수정 대상으로 되돌리지 않는다.

- 변경 파일: `plans/7-install-landing.log.md`, 본 plan의 완료 표시만. 실행 선례는 `docs/SIGNING.md`, 위 release/build/checksum/smoke 파일이다.
- 선행: 운영자가 `SIGN_IDENTITY`, `APPLE_CERTIFICATE_P12_BASE64`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_SPECIFIC_PASSWORD`를 연결한다. `KEYCHAIN_PASSWORD`는 선택이다. 권한·이름만 확인하며 값을 출력하지 않는다.
- 미연결이면 **운영 차단**으로 기록하고 멈춘다. unsigned publish·secret 검사 생략·YAML 반복 수정·성공 위장 금지.
- 연결 후 별도 권한이 확보된 후속 릴리스 단계에서 검증된 SHA의 새 `v*` 태그로 기존 workflow를 실행한다. 이번 `/plan`은 태그·릴리스·secret을 변경하지 않는다. Draft PR을 몰래 병합하지 않는다.
- run의 SHA·tag·공증 Accepted·DMG staple validate·앱 codesign·DMG open/앱 execute 평가·checksum·CI smoke 성공을 각각 확인한다. 다른 브랜치의 실패 run이나 일반 CI 성공으로 대체하지 않는다.
- 공개 Release에서 `shotsort.dmg`와 `shotsort.dmg.sha256`를 함께 받아 `shasum -a 256 -c shotsort.dmg.sha256`가 OK인지 확인한다. asset digest만으로 완료 처리하지 않는다.
- 새 macOS 사용자/깨끗한 기기에서 다운로드 → Applications 복사 → 첫 실행 → 업데이트 링크를 우회 없이 확인한다. 임시 Applications로 복사하는 CI smoke는 첫 실행을 검증하지 않으므로 두 증거를 구분한다.
- 완료: release/run URL·SHA·tag·파일명·checksum 결과·macOS 버전·새 사용자 여부·첫 실행 결과가 log에 있다. 개인정보·인증 정보는 제외한다.
- 커밋: `docs: [P4] #7 공증 릴리스와 clean-install 증거 기록`(성공 전 완료 마커 금지).

### P5 — 검증된 릴리스 상태를 공개 안내에 반영 (보류)

- 의존: P3/P4/P6 완료. 증거가 없으면 준비 중·소스 실행 안내를 유지한다.
- 변경 파일(최대 4개): `docs/landing/index.html`, `README.md`, `tests/test_landing_contract.py`, 필요 시 `docs/SIGNING.md`.
- `index.html`의 `.fine-print`/`.download`/FAQ 및 README 설치 절을 검증된 최신 릴리스·checksum과 일치시킨다. 스타일·이미지·`app.js`의 신호 계약은 재사용한다.
- `LandingContractTests.test_unsigned_release_is_not_presented_as_ready_for_installation`은 준비 중 문자열 고정을 검증된 일반 설치·checksum·우회 안내 금지 계약으로 바꾼다. 기존 CTA/privacy/demo/feedback 계약은 유지한다. 일반 설치 약속은 실제 P4 증거가 있을 때만 한다.
- 검증: `python3 -m unittest tests.test_landing_contract tests.test_build_app_contract -v`; 제품 파일 변경 후 CI 표준 unittest/compileall. Pages 배포 후 1280/390·포커스·CTA→두 asset·빈 피드백 이동을 재확인한다.
- 완료: 랜딩·README·latest Release가 실제 설치 가능 상태와 같고 P4의 증거로 추적 가능하다.
- 커밋: `docs: [P5] #7 검증된 공증 설치 상태 공개`.

### P6 (완료) — 기존 릴리스 노트의 우회 안내 제거

- 변경 대상: GitHub Release `v0.1.1`의 body 중 설치 절. 로컬 제품 파일 변경 없음; 실행 기록/완료 표시는 log/plan에 보존한다.
- 선례: `README.md`의 공증 전 소스 실행 안내, `docs/landing/index.html`의 준비 중 문구. P4를 기다릴 필요 없다.
- 후속 단계에서 Release 편집 권한이 확보되면 기존 body를 재조회·보관하고 “그래도 열기” 절차를 제거한다. 무서명 상태와 공증 전 소스 실행 안내는 분명하게 유지한다. 이 버전을 공증 완료로 바꾸거나 asset·tag·발행 시각을 바꾸지 않는다.
- 검증: 편집 전후 body 대조, 우회 명령/보안 예외 안내 없음, 기존 변경 내역 보존, asset·tag 불변, 랜딩 CTA에서 도착한 노트와 준비 중 상태가 일치함을 확인한다. 로그에 전후 증거를 남긴다.
- 이번 plan에서는 외부 편집을 실행하지 않는다. 후속 실행에서도 Apple secret 부재와 별개로 처리하되 공증 완료로 오인시키지 않는다.
- 커밋: `docs: [P6] #7 릴리스 설치 안내 정합성 증거 기록`.

## 검증·완료·권한 경계

1. 지금 `/plan`은 조사·plan/log 작성·문서 검증·커밋까지만 한다. rebase·worktree/브랜치 전환/삭제·새 child/PR 생성·push·Ready·merge·auto-merge는 실행하지 않는다. PR #18은 Draft 유지.
2. 운영 phase는 제품 코드 변경 없이 증적을 커밋한다. plan 완료 마커와 옆 log를 항상 `git add -f`로 함께 보존한다. 새 필수 조건은 log에만 두지 않고 plan에 반영한다.
3. 코드 계약 테스트는 실제 Apple 공증이나 브라우저 검증을 대신하지 않는다. plan 문서만 바꾸는 이번 실행은 테스트를 재실행하지 않는다.
4. 최종 이슈 완료는 공개 랜딩·실제 앱 데모·로컬/외부 AI 설명·정상 CTA/피드백, 최신 signed/notarized/stapled DMG와 checksum, 새 사용자 무경고 첫 실행, 공개 문구 정합성이 모두 증명될 때만 판정한다.
5. PR #18의 후속 통합과 릴리스는 별도 파이프라인 단계다. Apple 연결/설치 증거 부재를 성공으로 숨기거나 #7을 닫지 않는다.
