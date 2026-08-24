# #7 서명·공증 설치 경로와 공개 랜딩 완료 계획

## 조사 결과

- 기준 브랜치/커밋은 `7-install-landing`의 `cebb920`이며, 이미 Developer ID 서명, notarytool, DMG checksum/smoke, 랜딩의 기본 구조가 들어 있다.
- 이슈 #7은 열려 있다. 완료 기준은 Gatekeeper 경고 없는 최신 DMG, clean macOS 설치, 최신 릴리스로의 1-click 이동, 처리 경계 설명, 다운로드/피드백의 최소 신호다.
- `Deploy landing page` run `32788215746`은 `actions/configure-pages@v5`에서 Pages site 404로 실패했다. GitHub Pages가 아직 활성화되지 않은 것이 원인이다.
- release run `32788214828`도 실패로 기록되어 있고 최신 Release는 `v0.1.1`(2026-06-15)이다. 현재 `release.yml`의 tag 전용 공증 흐름은 필요한 Apple secrets가 없으면 asset 생성 전에 실패하도록 되어 있다.
- `docs/landing/index.html`은 아직 "공증 릴리스 준비 중"이라고 정확히 알리지만, 실제 앱 화면/데모 asset은 없다. `README.md`도 아직 공증 전 fallback을 안내한다.
- Apple Developer Program 가입은 승인됐다. 단, 인증서와 notarytool 자격증명 값은 이슈·문서·코드·로그에 쓰지 않고 GitHub Actions secrets와 runner 임시 keychain에서만 취급한다.

## 현재 구조와 선례

| 관심사 | 현재 파일 | 따를 선례 |
| --- | --- | --- |
| Pages 배포 | `.github/workflows/pages.yml` | `actions/configure-pages@v5` → artifact → `actions/deploy-pages@v4` 순서 |
| 서명·공증 release | `.github/workflows/release.yml`, `build_app.sh`, `scripts/release/*.sh` | 임시 `shotsort-signing.keychain-db`, sign → notarize → staple → checksum → clean smoke |
| 설치 약속 회귀 방지 | `tests/test_build_app_contract.py`, `tests/test_landing_contract.py` | 텍스트/워크플로 계약을 macOS 도구 호출 없이 검증 |
| 공개 랜딩 | `docs/landing/index.html`, `styles.css`, `app.js` | 모든 download CTA는 `releases/latest?source=landing`, feedback은 기존 Issue URL만 사용 |

## 범위와 비범위

- #4, #1의 앱 기능은 병렬 이슈이므로 변경하지 않는다. 이 계획은 그 기능을 실제로 조작하는 정적 데모만 다룬다.
- 새 feedback label을 만들거나, 존재하지 않는 label을 URL에 요구하지 않는다. 기존 URL의 `labels=feedback`은 제거하거나, GitHub에 이미 존재함을 운영 검증한 뒤에만 유지한다.
- worktree/branch 정리, 삭제, 전환은 수행하지 않는다.

## 구현 phases

### P1 (완료) — Pages 활성화가 가능한 배포 workflow 복구

변경 파일(최대 3개):

- `.github/workflows/pages.yml`: `actions/configure-pages@v5`가 Pages site 부재 시 GitHub Actions 기반 Pages를 활성화하도록 `enablement: true`를 명시한다. 현재 permissions, concurrency, artifact 경로 및 deployment environment는 유지한다.
- `tests/test_landing_contract.py`: 배포 workflow를 읽는 회귀 테스트를 추가해 Pages enablement, `docs/landing` artifact, deploy action과 필요한 permissions가 함께 유지되게 한다.
- 필요 시 `README.md`: 공개 landing URL을 유지하고, Pages workflow가 첫 배포에서 site를 활성화한다는 운영 메모만 최소 추가한다.

구현/검증:

1. 변경 후 `python -m unittest tests.test_landing_contract -v`와 전체 `python -m unittest discover -s tests -v`를 실행한다.
2. main 반영 뒤 Actions의 `Deploy landing page`를 재실행하거나 workflow dispatch로 실행한다.
3. run 성공, deployment URL, `https://sj48695-labs.github.io/shotsort/`의 HTTP 응답 및 주요 CTA/feedback form을 확인한다. repository Pages 설정이 조직 정책으로 막히면, admin이 GitHub Pages를 허용해야 한다는 정확한 API 오류를 기록하고 다음 단계는 진행하지 않는다.

커밋: `fix: [P1] #7 GitHub Pages 배포 활성화`

### P2 — 실제 앱 화면을 포함한 설치 전 랜딩 완성

변경 파일(최대 5개):

- `docs/landing/assets/shotsort-demo.png`(또는 실제 비율에 맞는 `.webp`): 로컬에서 실행한 shotsort의 실제 UI를 캡처한 정적 데모. 개인 경로·API key·사용자 스크린샷은 마스킹하고, 합성 mockup/imagegen asset은 사용하지 않는다.
- `docs/landing/index.html`: hero 다음에 `<figure>`/설명으로 데모를 추가한다. alt text에는 실제 화면에서 보이는 분류/그룹/휴지통의 의미를 쓴다. download CTA의 단일 release URL은 유지한다.
- `docs/landing/styles.css`: 데모의 반응형 크기, 잘림 방지, 키보드 focus 및 고대비 대비를 기존 랜딩 톤에 맞춘다.
- `tests/test_landing_contract.py`: asset 존재, `<img>` 참조, 의미 있는 alt text, 여전히 3개 이상의 동일 download CTA 및 개인정보/FAQ/feedback 계약을 검증한다.
- `README.md`(필요 시): 랜딩을 실제 제품 데모와 설치 전 개인정보 안내의 단일 진입점으로 링크한다.

구현/검증:

1. 실제 앱을 샘플 데이터로 열어 화면이 기능과 일치하는지 확인한 후 asset을 생성한다.
2. 로컬 정적 서버에서 macOS desktop/mobile 폭을 확인하고 이미지가 가로 스크롤·텍스트 겹침 없이 렌더링되는지 검토한다.
3. `python -m unittest tests.test_landing_contract -v` 및 전체 테스트를 통과시킨다.

커밋: `feat: [P2] #7 실제 앱 데모를 설치 랜딩에 추가`

### P3 — 공증 release 실행 계약과 비밀 격리 검증

변경 파일(최대 5개):

- `.github/workflows/release.yml`: tag release만 publish하고, 모든 required secret을 asset 생성 전에 검사하며, 인증서/프로필이 `$RUNNER_TEMP` keychain에만 존재하고 `always()` cleanup 되는 현재 경계를 유지·보강한다. 실제 재실행을 위해 수동 dispatch를 추가해야 한다면 tag/ref 입력을 명시적으로 검증하여 임의 commit release를 막는다.
- `build_app.sh`: `SIGN_IDENTITY`와 `NOTARY_PROFILE` 쌍, hardened runtime entitlements, sign → notarize → staple → Gatekeeper 순서를 유지한다. CI에서 확인된 실패 원인에 한해 수정한다.
- `scripts/release/smoke_install.sh`: DMG staple 검증 후 새 임시 mountpoint/Applications로 복사하고 codesign·`spctl`을 확인하는 clean-install 경로를 유지·보강한다.
- `tests/test_build_app_contract.py`: P3 변경의 secret 이름 미하드코딩, 임시 keychain, command ordering, smoke 경로 계약을 추가/갱신한다.
- `docs/SIGNING.md`: 실제 운영자가 필요한 secret **이름**, 등록 위치, release runbook과 실패 시 비밀을 출력하지 않는 진단 절차만 문서화한다.

구현/검증:

1. macOS 도구를 호출하지 않는 `python -m unittest tests.test_build_app_contract -v`와 전체 테스트를 먼저 통과시킨다.
2. 관리자 권한으로 GitHub repository secrets에 `SIGN_IDENTITY`, `APPLE_CERTIFICATE_P12_BASE64`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_SPECIFIC_PASSWORD` 및 선택 `KEYCHAIN_PASSWORD`를 UI 또는 안전한 stdin으로 등록한다. 값은 채팅, 파일, git config, workflow 출력에 기록하지 않는다.
3. 새 `v*` tag로 release를 실행한다. Actions에서 checksum과 smoke가 성공하고, Release에 `shotsort.dmg`와 `shotsort.dmg.sha256`가 모두 붙었는지 확인한다. 실패 시 Actions secret을 재확인하되 무서명 DMG를 업로드/대체하지 않는다.
4. 새 macOS 사용자 계정에서 Release DMG를 내려받아 checksum, drag-to-Applications, 첫 실행, `spctl`/Gatekeeper 무경고, 업데이트 링크를 확인한다.

커밋: `fix: [P3] #7 공증 release 운영 계약 보강`

### P4 — 검증된 공증 상태를 공개 문구와 운영 신호에 반영

선행 조건: P1의 Pages deployment와 P3의 실제 notarized release 및 clean-user smoke가 모두 성공했다는 증거가 있어야 한다. 하나라도 실패하면 현재의 "준비 중" 문구를 유지한다.

변경 파일(최대 4개):

- `docs/landing/index.html`: "공증 릴리스 준비 중"/조건부 설치 문구를 검증된 현재 version의 Gatekeeper 우회 불필요 설치 안내로 교체한다. checksum과 source fallback은 유지한다.
- `README.md`: 공증 전 fallback 문구를 같은 release 상태로 갱신하고, 현재 latest release/landing으로의 1-click 경로를 확인한다.
- `tests/test_landing_contract.py`: 준비 중 문구가 사라지고, 공증/일반 설치/checksum 약속이 동시에 존재하는지 검증한다.
- `docs/SIGNING.md`(필요 시): published version, timestamp, clean-user smoke 결과를 비밀 없이 release runbook의 완료 체크로 기록한다.

구현/검증:

1. landing/README 링크가 새 latest release로 이동하고 asset 두 개가 있는지 확인한다.
2. landing에서 download CTA, feedback Issue prefill(`installed-version`, `installation-status`)을 수동 확인한다. feedback URL은 허용된 기존 label만 포함하고, 새 label 생성은 하지 않는다.
3. landing contract 및 전체 unittest를 통과시키고 Pages deployment 후 공개 URL을 다시 점검한다.

커밋: `docs: [P4] #7 검증된 공증 설치 상태 공개`

## 최종 완료 판정

아래가 모두 충족될 때만 #7을 완료로 본다.

1. Pages workflow가 성공하고 공개 랜딩에서 실제 앱 데모, 개인정보 경계, FAQ, feedback CTA가 보인다.
2. 최신 GitHub Release에 Developer ID signed/notarized/stapled `shotsort.dmg`와 검증 가능한 `.sha256`가 있다.
3. 새 macOS 사용자에서 우회 명령 없이 설치·첫 실행·Gatekeeper 검증이 통과한다.
4. 랜딩과 README는 실제 release 상태와 일치하며, 공증 전 문구가 남아 있지 않다.
5. `download_click` 대체 신호(`source=landing`)와 feedback/install status prefill이 동작하고, 허용되지 않은 feedback label을 생성하거나 요구하지 않는다.
