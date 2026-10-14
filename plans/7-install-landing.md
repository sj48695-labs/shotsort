# #7 서명·공증된 설치 경로와 공개 제품 랜딩으로 첫 사용자 획득 준비

- 플랜식별자: `066DF350`
- 출처: GitHub issue #7 본문·댓글 (2026-09-18), PM 지침
- 재검토: 기존 plan 전체를 최신 reopen 댓글과 대조해 재작성

## 재검토 결과

- 완료 보존: `[P1]` 랜딩/릴리스 카피 정직성은 `54575dd`, `[P2]` 실제 앱 데모 착지는 `b0457f9` 및 PR #12 병합 커밋 `9f4d100`에 있다. `docs/landing/assets/shotsort-demo.png`도 현재 기본 브랜치에 있으므로 재구현하지 않는다.
- 범위 정정: 최신 이슈 본문은 Pages가 200으로 동작한다고 명시하며, 최신 댓글은 P1·P2만 병합됐다고 확인한다. 이전 plan의 Pages 404 복구, PR #10/#12 정리, 데모 재생성, 별도 P4/P5는 stale이므로 제거한다.
- 남은 범위: Apple Developer ID secrets 연결 후 새 `v*` 태그에서 signed → notarized → stapled DMG, checksum, clean-install smoke를 실제로 성공시킨다. secrets가 없거나 실패하면 코드로 초록을 만들지 않는다.
- 회의록: 지정된 `/tmp/pm-meeting-KRZpbC`는 현재 환경에 없어 읽을 수 없었다. 이 plan은 최신 issue 본문·댓글과 사용자 제공 PM 지침을 근거로 한다.

## 현재 구조와 선례

| 관심사 | 현재 파일·심볼 | 현재 상태 |
| --- | --- | --- |
| 릴리스 진입점 | `.github/workflows/release.yml`의 `release` job | `v*` push에서 secrets preflight → 임시 keychain → build → checksum → smoke → release asset publish 순서가 구현됨 |
| 서명·공증 | `build_app.sh`의 `SIGN_IDENTITY`, `NOTARY_PROFILE`, notarization block | Developer ID hardened-runtime sign, `notarytool submit`, `stapler staple/validate`, DMG `spctl` 검증이 구현됨 |
| clean install | `scripts/release/smoke_install.sh`의 `DMG_PATH`, `WORK_DIR` | 임시 mount/Applications 경로에서 stapled DMG, copied app codesign·spctl을 검증함 |
| checksum | `scripts/release/verify_dmg.sh`의 `CHECKSUM_PATH` | `dist/shotsort.dmg.sha256`를 생성함 |
| 공개 약속 | `docs/landing/index.html`, `README.md`, `docs/SIGNING.md` | 공증 전에는 준비 중/소스 실행만 안내하고 우회 명령을 안내하지 않음 |
| 회귀 계약 | `tests/test_build_app_contract.py`, `tests/test_landing_contract.py` | macOS 도구·실제 secrets 없이 command order와 공개 카피 경계를 검증함 |

## 범위와 비범위

- #4, #11, #1의 앱 기능, Pages 설정, 랜딩 데모, 기존 카피를 변경하지 않는다.
- 인증서 값, private key, Apple ID, app-specific password, token은 저장소·plan·로그에 기록하지 않는다.
- 새 tag 생성, secrets 등록, GitHub Release 공개, clean macOS 사용자 확인은 운영 권한이 필요하다. 현재 `/plan` 단계에서는 실행하지 않는다.
- Draft 상태를 유지한다. MR/PR Ready 전환, merge/auto-merge, worktree/브랜치 전환·삭제·정리는 하지 않는다.

## Phase별 구현 계획

### P1 (완료) — 랜딩·릴리스 카피 정직성

완료 커밋: `54575dd`.

- `docs/landing/index.html`, `tests/test_landing_contract.py`에서 `무료로 다운로드`, 내부 측정 은어, 공증 전 checksum 약속, Gatekeeper 우회 안내를 제거했다.
- 현재 공증 전 상태를 `공증 릴리스 준비 중`으로 표시하고 release CTA는 실제 latest release로 연결한다.

### P2 (완료) — 실제 앱 데모를 랜딩에 착지

완료 커밋: `b0457f9`, 병합 증거: `9f4d100`.

- `docs/landing/assets/shotsort-demo.png`, `docs/landing/index.html`, `docs/landing/styles.css`, `tests/test_landing_contract.py`에 실제 앱의 분류·그룹·휴지통 흐름과 접근 가능한 설명을 추가했다.
- 이 asset과 landing 변경을 새 브랜치나 새 캡처로 다시 만들지 않는다.

### P3 — Apple secrets 연결 후 공증 release를 운영 검증하고 공개 상태를 동기화

선행 조건: 운영자가 GitHub Actions secrets `SIGN_IDENTITY`, `APPLE_CERTIFICATE_P12_BASE64`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_SPECIFIC_PASSWORD`를 등록한다. 선택 `KEYCHAIN_PASSWORD`는 임시 keychain 비밀번호용이다.

변경 파일(실패한 step이 코드 결함일 때만, 최대 5개):

- `.github/workflows/release.yml`의 `Check signing secrets`, `Configure signing keychain and notary profile`, asset publish 단계 — 실패한 첫 step이 workflow 순서·임시 keychain 처리 문제일 때만 수정한다. 선례: 현재 `Remove temporary signing credentials`의 `always()` cleanup.
- `build_app.sh`의 signing/notarization block — hardened runtime, `notarytool`, staple, `spctl` 순서가 실제 실패 원인일 때만 수정한다. 선례: `tests/test_build_app_contract.py::test_signed_release_follows_sign_dmg_notarize_staple_verify_order`.
- `scripts/release/smoke_install.sh`의 `DMG_PATH`/`WORK_DIR` 흐름 — clean install 실패 원인일 때만 수정한다. 선례: `test_smoke_validates_the_stapled_dmg_before_copying_the_app`.
- `tests/test_build_app_contract.py` — 위 변경의 command order 또는 credential isolation 계약만 갱신한다.
- `docs/landing/index.html`, `README.md`, `docs/SIGNING.md`, `tests/test_landing_contract.py` — 성공한 공개 release의 version, `shotsort.dmg`/`shotsort.dmg.sha256`, Gatekeeper 무우회 설치와 불일치할 때만 함께 갱신한다. 현행 공증 전 카피는 성공 증거 전까지 유지한다.

운영 검증:

1. secrets 등록 뒤 새 `v*` tag로 workflow를 실행한다. 첫 실패 step을 확인하고, 누락·권한 실패면 workflow를 바꾸지 않고 secret/Apple 권한 문제로 기록한다.
2. 성공 run에서 `build_app.sh`의 sign → notarize → staple → `spctl`, `verify_dmg.sh` checksum, `smoke_install.sh` 임시 mount/Applications 검증이 모두 통과했는지 확인한다.
3. 공개 GitHub Release에 같은 build의 `shotsort.dmg`와 `shotsort.dmg.sha256`가 있는지 확인하고 checksum 검증을 수행한다.
4. 깨끗한 macOS 사용자에서 DMG 다운로드 → Applications 복사 → 첫 실행 → Gatekeeper 검증을 우회 명령 없이 확인한다.
5. 위 공개 증거가 모두 있을 때만 landing/README/release notes의 준비 중 문구를 실제 release 상태로 동기화하고, `python -m unittest tests.test_landing_contract -v` 및 `python -m unittest discover -s tests -v`를 통과시킨다. 문서 변경이 있으면 별도 커밋 `docs: [P3] #7 검증된 공증 설치 상태 공개`으로 남긴다.

완료 증거: 성공한 release run URL, 공개 release URL과 두 asset, checksum 결과, clean-user smoke 결과, 그리고 그 version과 일치하는 landing·README·release notes. 어느 하나라도 없으면 #7은 완료 처리하지 않고 현재 공증 전 카피를 유지한다.

## 테스트 계획

1. 코드 수정이 생긴 경우 `python -m unittest tests.test_build_app_contract -v`로 signing/keychain/smoke command 계약을 확인한다.
2. 공개 카피 수정이 생긴 경우 `python -m unittest tests.test_landing_contract -v`로 CTA·준비 상태·데모·feedback 계약을 확인한다.
3. 문서 또는 workflow 변경 후 `python -m unittest discover -s tests -v`를 실행한다.
4. 실제 release에서는 workflow의 codesign, notarization, staple, checksum, smoke 성공 및 clean-user 설치를 증거로 확인한다.

## 최종 완료 판정

1. 새 `v*` release에 Developer ID signed/notarized/stapled `shotsort.dmg`와 `shotsort.dmg.sha256`가 있다.
2. CI와 깨끗한 macOS 사용자 모두 Gatekeeper 우회 없이 설치·첫 실행을 통과한다.
3. 공개 landing, README, release notes가 성공한 asset/version과 일치한다.
4. P1·P2의 로컬/AI 처리 경계, 실제 앱 데모, feedback 신호는 회귀하지 않는다.
