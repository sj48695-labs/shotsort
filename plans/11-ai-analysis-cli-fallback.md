# #11 AI 분석 모델 선택과 CLI 우선 실행·API fallback 계획

## 조사 결과

- 기준 worktree/브랜치는 `11-ai-analysis-cli-fallback`이며, 기준 커밋은 `cebb920`이다. 작업 시작 시 추적/미추적 변경은 없다.
- 이슈 #11에는 댓글·라벨이 없으며, 현재 구현은 `providers.ProviderConfig`와 `StructuredProvider`로 Anthropic/OpenAI/xAI **API** 호출만 어댑트한다. `resolve_config()`는 원격 모델명을 필수로 하고, `codex` 별칭을 API OpenAI로 바꾼다.
- `engine.scan_images()`는 공급자를 생성한 뒤 이미지별 분류와 2차 그룹 정규화에 같은 adapter를 쓰며, 오류는 각 이미지의 오류로만 남긴다. 실행한 방식·외부 전송·fallback 사유를 반환하거나 저장하지 않는다.
- GUI [`app.py`](../app.py)는 local/API 4개 선택과 자유 모델명 입력만 제공하며, CLI [`cli.py`](../cli.py)는 API key가 있으면 Anthropic을 기본 선택한다. 어느 쪽도 사용자 동의나 모델 목록/캐시를 갖지 않는다.
- 현재 설치본에서 `codex exec --help`는 `--image`, `--output-schema`, `--sandbox`, `--ephemeral`을 제공하고 `codex login status`도 제공한다. 따라서 첫 CLI 어댑터는 Codex CLI로 한정한다. `claude -p`는 JSON schema와 인증 상태 명령은 확인됐지만, 로컬 이미지를 비대화식으로 첨부하는 안정된 인터페이스를 이 조사에서 확인하지 못했다. Claude CLI는 이름만 지원 대상으로 표시하지 않고, 추후 검증된 이미지 입력 계약이 생긴 뒤 별도 adapter로 추가한다.
- 회의록 경로 `/tmp/pm-meeting-JqcUf3`는 현재 존재하지 않아 읽을 수 없었다. 이 계획은 이슈 본문과 현 코드로 확정한다.

## 현재 구조와 선례

| 관심사 | 현재 파일/심볼 | 따를 선례 |
| --- | --- | --- |
| API 공급자 | [`providers.py`](../providers.py): `ProviderConfig`, `StructuredProvider`, `create_provider` | API별 request 차이를 `generate_json()`으로 숨기는 기존 adapter 경계 |
| 스캔 실행 | [`engine.py`](../engine.py): `scan_images`, `classify_with_provider`, `consolidate_with_provider`, `ScanResult` | UI/CLI 공통 함수는 출력 없이 콜백과 결과 객체로 상태를 전달 |
| 앱 설정 UI | [`app.py`](../app.py): `index()`, `refresh_mode`, `do_scan` | NiceGUI control 값으로 입력을 받고 `run.io_bound(engine.scan_images, ...)` 호출 |
| CLI | [`cli.py`](../cli.py): `cmd_scan`, `build_parser` | `--local` 강제, stderr 오류 및 argparse choices |
| 지속 상태 | [`engine.py`](../engine.py): `db()` | 기존 `~/.shotsort/cache.db` migration (`PRAGMA table_info` 후 `ALTER`)과 SQLite JSON 저장 |
| 공급자 회귀 | [`tests/test_providers.py`](../tests/test_providers.py) | SDK를 호출하지 않고 fake client로 요청/구조를 검사 |

## 확정할 제품 정책

- 분석 방식은 `auto`, `local`, `cli`, `api`, `direct` 다섯 개의 명시 값으로 둔다. `direct`는 기존 공급자/API base URL/모델을 사용자가 고르는 고급 설정이며, API Key 자체는 선택한 API 방식과 동일한 동의 규칙을 따른다.
- `auto`는 **검증된 Codex CLI → 동의가 이미 저장된 API Key → local** 순서다. CLI 사용도 OCR 텍스트와 선택된 이미지가 OpenAI 서비스로 전송될 수 있으므로 외부 전송으로 표시하되, CLI에는 별도의 API fallback 동의를 요구하지 않는다. API는 공급자별 저장 동의가 없으면 후보로만 보이고 실행하지 않는다.
- API 동의는 `provider + image 포함 여부` 단위로 앱 설정에 저장한다. 이미지 여부가 바뀌면 다시 동의한다. CLI/API 실패 뒤에는 다른 유료 API를 자동 호출하지 않고 local로만 fallback한다.
- API Key는 값이 아니라 상태만 저장/표시한다. 사용자가 입력한 키는 macOS Keychain에만 보관하고, Keychain을 쓸 수 없는 환경에서는 환경변수만 읽는 상태로 제한한다. 예외/상태/CLI 출력에서 `sk-…`, Bearer 값, 환경변수 값은 마스킹한다.
- 모델 목록은 `provider + execution mode` 키로 마지막 성공 목록, 조회 시각, 원본(조회/검증 기본값)을 SQLite에 저장하고 앱 시작 시 및 마지막 성공 후 24시간이 지났을 때 갱신한다. Codex CLI처럼 지원 목록 API가 없는 경우 검증된 기본 모델과 직접 입력을 함께 제공한다. 저장 모델이 목록에서 사라지면 자동 추천으로 되돌리기 전 UI에서 경고하고 사용자의 확인을 받는다.

## 범위와 비범위

- #4, #1은 같은 배치의 형제 이슈이므로 이 계획에서 해당 UI/기능을 수정하지 않는다.
- CLI 설치/로그인 자동화, API Key 자동 발급, 요금 계산, AI 결과 자동 확정은 구현하지 않는다.
- Codex CLI가 유일한 첫 지원 CLI다. Claude CLI adapter, 임의 CLI 탐색, 모델명을 추측해 지원 처리하는 작업은 하지 않는다.
- worktree/branch 삭제·전환·정리와 후속 완료 절차는 수행하지 않는다.

## 구현 phases

### P1 (완료) — 실행 정책·공급자 adapter·안전한 상태 모델 도입

변경 파일(최대 3개):

- [`providers.py`](../providers.py): 기존 API `ProviderConfig`를 호환 유지하면서 `AnalysisMode`, `ExecutionMethod`, `ProviderCapability`, `ExecutionPlan/ExecutionStatus` 및 분류된 오류 타입을 추가한다. `resolve_execution()`에서 `auto → codex CLI → 동의된 API → local`을 단일 정책으로 결정하고, API adapter와 local adapter가 같은 structured-result 경계를 구현하게 한다. `CodexCliProvider`는 `codex login status`와 `codex exec --sandbox read-only --ephemeral --image … --output-schema …`의 제한 시간 실행/JSON 파싱을 구현한다. command 존재, 인증, 이미지, structured output, timeout/error를 capability로 보고하고 모든 사용자 노출 문자열은 `mask_secret()`을 거친다.
- [`tests/test_providers.py`](../tests/test_providers.py): subprocess/환경을 fake로 주입하여 Codex CLI 설치·로그인·성공·timeout·잘못된 JSON과 API key 상태를 검증한다. auto 우선순위, API 동의 없을 때 local, API 실패가 다른 유료 provider로 넘어가지 않는 정책, key/Authorization/CLI stderr 마스킹을 테스트한다.

구현/검증:

1. `python -m unittest tests.test_providers -v`를 실행한다.
2. `python -m unittest discover -s tests -v`를 실행한다.
3. 실제 로그인·유료 호출은 하지 않는다. capability probe는 fake subprocess로 계약을 고정하며, 실제 환경에서 발견된 CLI 정보는 상태 표시용 읽기 전용 probe만 사용한다.

커밋: `feat: [P1] #11 AI 실행 정책과 Codex CLI 어댑터`

### P2 (완료) — 엔진 실행 결과·fallback·설정/모델 캐시 영속화

변경 파일(최대 3개):

- [`engine.py`](../engine.py): `db()`에 `ai_settings`, `model_catalog_cache` migration을 추가하고 설정/동의/Keychain 상태/모델 catalog read-write 함수를 둔다. `scan_images()`는 P1 `ExecutionPlan`을 한 번 해석해 adapter를 만들고 `ScanResult`에 실제 provider, mode, model, external-transfer 여부, catalog-cache 여부, fallback reason을 담는다. 개별/통합 호출의 CLI/API 오류를 분류하여 local 재시도로 전환하되, API 요청 실패 후 다른 API에는 절대 재시도하지 않는다. 기존 `provider=local|anthropic|openai|xai`, `use_llm`, DB 이미지 캐시 호출은 계속 호환한다.
- [`tests/test_ai_runtime.py`](../tests/test_ai_runtime.py): 임시 SQLite와 fake adapter/Keychain/subprocess로 CLI→local, 동의 API→local, 미동의 API→local, timeout/auth/network/rate-limit 분류, 이미지 전송 플래그, 이미지 캐시 스킵과 2차 정규화까지 실제 실행 결과가 보존되는지를 검증한다.
- [`tests/test_saved_projects.py`](../tests/test_saved_projects.py): 기존 `scan_images` 호출의 provider API/local 및 저장 프로젝트 규칙 동작이 새 execution result 뒤에도 유지되는 regression을 필요한 최소 범위에서 추가한다.

구현/검증:

1. `python -m unittest tests.test_ai_runtime tests.test_saved_projects -v`를 실행한다.
2. `python -m unittest discover -s tests -v`를 실행한다.
3. Keychain이 없는 CI에서는 저장 실패가 키 평문 저장으로 바뀌지 않고 “환경변수만 사용 가능” 상태로 내려가는 테스트를 통과시킨다.

커밋: `feat: [P2] #11 분석 fallback 상태와 모델 캐시`

### P3 (완료) — 앱의 방식 선택·동의·모델 상태 화면

변경 파일(최대 3개):

- [`app.py`](../app.py): 현재 `provider_in`/`model_in` 행을 다섯 분석 방식 선택, provider/모델 자동 추천 select+직접 입력, API Key 상태/Keychain 저장 입력, 이미지 전송 switch로 교체한다. `refresh_mode()`는 감지된 CLI별 불가 사유, 실제 선택될 provider/method/model, 마지막 catalog 갱신 시각과 캐시 여부, CLI/API의 외부 전송을 명확히 보인다. API 실행 전에는 provider+image 범위 동의 dialog를 띄우며, `do_scan()` 완료/실패 알림에는 `ScanResult`의 실제 방식과 fallback 이유를 표시한다. 저장 모델이 사라졌을 때는 자동 추천으로 바꾸기 전 confirm dialog를 띄운다.
- [`tests/test_app_ai_contract.py`](../tests/test_app_ai_contract.py): NiceGUI 서버를 실행하지 않고 source/작은 helper를 대상으로 다섯 mode, 자동 추천, 외부 전송·CLI 경고, 동의 dialog, 실제 실행 상태/fallback 표시가 유지되는 계약을 검사한다.
- [`README.md`](../README.md): 데스크탑 앱 사용법과 개인정보 절에 CLI/API/local 구분, Codex CLI도 외부 전송일 수 있음, API 동의/Keychain 경계, 캐시된 모델 목록과 직접 입력 fallback을 문서화한다. API key 예시는 값을 노출하지 않는 환경변수 이름만 둔다.

구현/검증:

1. `python -m unittest tests.test_app_ai_contract -v`와 전체 test discovery를 실행한다.
2. local-only 상태, 설치됐지만 로그인 안 된 Codex, 로그인된 Codex, API Key 있으나 미동의, CLI timeout의 다섯 상태를 fake capability로 UI에서 확인한다.
3. 실제 스크린샷·API Key·AI 호출을 사용하지 않고, 상태 문자열에 비밀 값이 없는지 검토한다.

커밋: `feat: [P3] #11 AI 분석 선택과 전송 동의 UI`

### P4 (완료) — CLI 인터페이스·운영 문서·종단 회귀 검증

변경 파일(최대 3개):

- [`cli.py`](../cli.py): `scan --provider`에 `auto`, `cli`, `api`, `direct`, `local`을 추가하고 기존 vendor shorthand를 `direct`의 provider 선택으로 호환한다. `--allow-api-transfer`는 명시적인 비대화식 API 동의로만 저장/사용하며, 없으면 API 후보를 표시하고 local fallback한다. 시작과 종료 출력은 실제 provider/method/model, 외부 전송, 모델 catalog cache, fallback reason만 출력하고 비밀은 절대 출력하지 않는다.
- [`tests/test_cli_ai_contract.py`](../tests/test_cli_ai_contract.py): parser 호환성, auto의 표시, `--allow-api-transfer` 없이 API가 호출되지 않는 것, CLI/API/local fallback 순서, 마스킹된 stderr/출력을 fake engine으로 검증한다.
- [`README.md`](../README.md): 새 CLI 예제(`--provider auto`, `--provider cli`, `--provider api --allow-api-transfer`, `--provider direct …`)와 자동 갱신 24시간/캐시/저장 모델 폐기 동작을 최종 반영한다.

구현/검증:

1. `python -m unittest tests.test_cli_ai_contract -v`와 `python -m unittest discover -s tests -v`를 실행한다.
2. `python cli.py scan --help`로 flags/동의 문구를 확인하고, fixture 이미지와 fake adapter에서 전체 auto 및 local-only 흐름을 smoke test한다.
3. `rg -n '(sk-|Bearer |OPENAI_API_KEY=|ANTHROPIC_API_KEY=|XAI_API_KEY=)' providers.py engine.py app.py cli.py tests`로 비밀값을 출력/fixture에 넣는 변경이 없는지 점검한다.

커밋: `feat: [P4] #11 AI 분석 CLI fallback 상태 표시`

## 최종 완료 판정

1. 사용자는 모델명을 몰라도 `자동 추천`으로 스캔을 시작할 수 있고, 사용한 provider/model/method와 전송 여부를 시작 전과 완료 후 확인할 수 있다.
2. Codex CLI는 설치·로그인·비대화식·이미지·구조화 출력 capability가 모두 확인된 경우에만 auto/CLI 후보가 된다. Claude 등 검증되지 않은 CLI는 지원됨처럼 표시되지 않는다.
3. CLI 실패 시 동의된 API만 후보가 되며, 미동의/실패 API에서 이미지가 외부로 전송되지 않고 local 분석이 계속된다. 실패 요청은 다른 유료 API로 이어지지 않는다.
4. API Key/인증 정보가 Keychain 또는 환경변수 경계 밖에 평문으로 저장·표시·로그되지 않고, 모든 노출 오류는 마스킹된다.
5. 모델 목록은 마지막 정상 값과 시각을 복원하고, 조회 실패 시 cache임을 보인다. 목록에서 사라진 저장 모델은 사용자 확인 없이 자동 추천으로 바뀌지 않는다.
6. 기존 local-only scan, API provider shorthand, OCR/저장 프로젝트/그룹 정규화 및 전체 단위 테스트가 유지된다.
