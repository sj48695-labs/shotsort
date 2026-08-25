# #11 AI 분석 모델 선택과 CLI 우선 실행·API fallback

- 플랜식별자: `EEA656FF`
- 출처: [이슈 #11](https://github.com/sj48695-labs/shotsort/issues/11), [2026-11-13 PM 댓글](https://github.com/sj48695-labs/shotsort/issues/11#issuecomment-6845476497), 사용자 PM 지침.
- 재검토 완료. 구현 상태: **P1~P5 완료 보존 / P6~P9 완료**.
- 판단: 기존 `[P1]`~`[P5]` 커밋과 최신 댓글이 일치하므로 기능을 다시 만들지 않고, 실행 계약·동의 경계·재실행 복원·통합 증거의 누락만 보완한다.
- 기존 `11-ai-analysis-cli-fallback` worktree/브랜치와 Draft [PR #13](https://github.com/sj48695-labs/shotsort/pull/13)을 계속 사용한다. 조사 기준 HEAD는 `4541913`.
- 실행 기록은 [옆 기록 파일](11-ai-analysis-cli-fallback.log.md)에 분리한다. `/code`의 기본 입력은 이 plan이다.

## 범위와 제품 정책

비개발자가 모델명을 몰라도 분석 방식을 선택하고, 외부 전송 범위를 확인한 뒤 스캔하는 것이 주 흐름이다. 한국어 UI와 기존 `app.py`, `model_settings.py`, `docs/landing/styles.css`, `docs/landing/index.html`의 톤을 유지한다 (`ui-design`: match mode).

- 분석 방식은 기존 `auto`, `local`, `cli`, `api`, `direct`를 유지한다.
- 자동 선택 순서는 검증된 Codex CLI → 검증된 Claude CLI(OCR 텍스트만) → 선택한 공급자의 동의된 API → 로컬이다. 이미지 분석을 켜면 Claude CLI는 제외하고 이유를 알린다. Claude 이미지 첨부 지원을 새로 만들거나 지원된다고 표시하지 않는다.
- CLI 사용도 외부 서비스 전송이다. API는 공급자 + 이미지 포함 여부 범위의 명시 동의를 요구한다. GUI는 저장 동의를 쓰고 CLI는 매 실행 `--allow-api-transfer`를 요구한다.
- 실행 중 CLI/API 요청 실패는 로컬로 복구한다. 다른 유료 API로 자동 재시도하지 않는다. CLI를 처음부터 사용할 수 없을 때만 동의된 API를 후보로 선택한다.
- 모델 목록 캐시는 공급자 + 실행 방식 단위로 마지막 정상 목록·시각·출처를 저장하고, 24시간이 지나면 갱신을 시도한다. 실패하면 마지막 목록을 유지한다. 사라진 저장 모델은 확인 전 덮어쓰지 않는다.
- 비밀값은 DB·로그·오류·화면에 노출하지 않는다. 직접 설정의 키 입력은 현재 화면 메모리에만 유지한다. 현 코드는 Keychain 저장/조회 구현이 없고 `keychain_status()`도 환경변수만 확인하므로 Keychain을 구현 완료로 설명하지 않는다. 보안 저장소는 가능하면 사용한다는 이슈 조건이므로 이번에 새 저장소를 만들지 않고 문구를 구현에 맞춘다.
- CLI 설치/로그인 자동화, 키 발급, 요금 계산, 새 공급자, 결과 자동 확정, 어댑터 통합 리팩터링은 제외한다. 형제 이슈 #7/#4/#1의 기능을 다시 구현하지 않는다.
- 브랜치/worktree 전환·삭제·정리, rebase, Ready 전환·merge·auto-merge는 이 계획의 실행 작업이 아니다. 후속 파이프라인은 최종 SHA 검증 후 별도 단계에서 처리하며 현재 Draft를 유지한다.

## 현재 구조와 확인할 간극

| 관심사 | 현재 심볼 / 경로 | 기존 선례와 남은 확인 |
| --- | --- | --- |
| 자동 CLI 감지/선택 | `providers.py`: `probe_codex_cli`, `probe_claude_cli`, `resolve_execution` | `tests/test_providers.py`가 설치/로그인/이미지 제외/순서를 검사. probe 실패 조합은 보강 필요 |
| 자동 CLI 실행 | `providers.py`: `CodexCliProvider.generate_json`, `ClaudeCliProvider.generate_json` | Codex는 stdout 전체 JSON, Claude는 `result` 문자열만 풀어 읽음. 아래 별도 경로와 출력 계약이 다르므로 실제 비대화식 출력 형태를 대조할 것 |
| 직접 설정의 PC 계정 | `cli_provider.py`: `CLIProvider`, `check_cli_login`, `cli_executable`, `cli_environment` | `tests/test_cli_provider.py`는 Codex 최종 출력 파일, Claude `structured_output`, stdin/임시 cwd/키 환경 제거를 검사. 검증된 처리 선례만 재사용하며 두 어댑터를 재작성하지 않음 |
| 엔진 동의/복구 | `engine.py`: `scan_images`, `classify_provider_error`, `ScanResult` | `legacy_remote_request`는 `provider` 또는 `use_llm` 지정만으로 동의를 True로 간주. 새 `analysis_mode` 호출에도 적용될 여지가 있으므로 명시 동의 경계 검사 필요 |
| 설정/캐시 | `engine.py`: `db`, `save_ai_settings`, `load_ai_settings`, `set_api_consent`, `has_api_consent`, `refresh_model_catalog` | `tests/test_ai_runtime.py`는 같은 메모리 DB에서 round trip만 검사. 파일 DB를 닫고 다시 연 복원 증거 없음 |
| GUI 설정 복원 | `app.py`: `index`, `selected_config`, `selected_model`, `selected_with_image`, `do_scan`; `model_settings.py`: `ModelSettings`, `model_settings_controls` | 일반 mode/provider/model만 저장, 이미지 switch는 False로 초기화, 직접 설정은 화면마다 local로 초기화. 승인된 비밀 제외 설정과 복원 후 동의 범위를 대조할 것 |
| GUI 동의/상태 | `app.py`: `refresh_mode`, `request_api_consent`, `do_scan` | `tests/test_app_ai_contract.py`는 대부분 소스 문자열 검사이므로 취소/승인/실제 스캔 흐름 증거를 대체하지 못함 |
| CLI 상태 | `cli.py`: `cmd_scan`, `_print_execution_status` | 시작 전에는 requested_mode만 출력, 실제 provider/model/method는 종료 후만 출력. 이슈의 실행 전 안내 조건과 간극 |

공통 헬퍼 추출 P0는 만들지 않는다. 기존 경계를 유지하고 순차 phase에서 같은 파일을 보완하는 것으로 충분하다. 아래 파일 목록은 수정 범위이며 선례 파일은 읽기용이다.

## Phase별 계획

### Phase 1 (완료) — 실행 정책·Codex CLI 어댑터

- 보존 커밋: `64145d5` (`[P1]`).
- 파일/심볼: `providers.py`의 `AnalysisMode`, `ExecutionMethod`, `ProviderCapability`, `ExecutionPlan`, 오류 타입, `resolve_execution`, `CodexCliProvider`; `tests/test_providers.py`.
- 기존 API adapter 경계를 유지한 structured result, CLI capability, timeout·마스킹 정책을 재사용한다.

### Phase 2 (완료) — 엔진 fallback·설정·모델 캐시

- 보존 커밋: `17647ec` (`[P2]`).
- 파일/심볼: `engine.py`의 `ScanResult`, `scan_images`, 설정/동의/캐시 저장 함수; `tests/test_ai_runtime.py`.
- 외부 호출 실패의 로컬 복구와 SQLite 저장 구조를 재사용한다. Keychain은 구현 완료 항목에 포함하지 않는다.

### Phase 3 (완료) — 분석 방식·동의 UI

- 보존 커밋: `fc5871f` (`[P3]`).
- 파일: `app.py`, `tests/test_app_ai_contract.py`, `README.md`.
- 다섯 mode, 모델 목록/직접 입력, 저장 모델 경고, 공급자별 동의 dialog와 실제 결과 표시를 재사용한다.

### Phase 4 (완료) — CLI mode·전송 동의·결과 표시

- 보존 커밋: `cc99029` (`[P4]`).
- 파일/심볼: `cli.py`의 `cmd_scan`, `build_parser`, `_print_execution_status`; `tests/test_cli_ai_contract.py`, `README.md`.
- 기존 vendor shorthand와 `--allow-api-transfer` 계약을 보존한다.

### Phase 5 (완료) — Claude CLI·PC 계정 실행 상태 보완

- 보존 커밋: `0ba63f0`, `4541913` (둘 다 `[P5]`). 기존 완료 범위를 재개하지 않는다.
- 파일/심볼: `providers.py`의 `ClaudeCliProvider`, `probe_claude_cli`, `resolve_execution`; `engine.py`, `app.py`, `cli.py`와 관련 AI contract 테스트.
- 자동 모드의 Claude 텍스트 fallback 및 직접 설정 `claude_cli`/`codex_cli` 실행 방식 보존을 재사용한다. 응답 계약 잔여 검증은 P6에서 수행한다.

### Phase 6 (완료) — CLI 비대화식 응답 계약·timeout 검증

- 변경 파일 (3개 이내): `providers.py`, `tests/test_providers.py`, `tests/test_ai_runtime.py`.
- 대상: `CodexCliProvider.generate_json`, `ClaudeCliProvider.generate_json`, `probe_codex_cli`, `probe_claude_cli`.
- 선례: `cli_provider.py:CLIProvider.generate_json`와 `tests/test_cli_provider.py:test_codex_uses_stdin_schema_readonly_and_final_output`, `test_claude_structured_response_and_no_tools`, `test_scan_through_cli_process_stores_classification`.
- 설치본의 help와 인증 상태 명령만으로 지원 flag를 확인한다. 인증 원문/계정 정보를 기록하지 않는다. 실제 분류 요청 없이 subprocess fixture로 명령/응답 계약을 고정한다.
- Codex의 진행 출력과 최종 JSON을 분리해 읽어야 하는지 확인하고, 필요하면 기존 출력 파일 패턴을 최소 적용한다. Claude의 `structured_output` envelope와 기존 `result` JSON 문자열을 모두 검증하며 결과 schema의 필수 키가 없으면 안전한 오류로 처리한다.
- 설치 없음/미로그인/help·auth timeout/실행 timeout/비정상 종료/잘못된 JSON을 fake runner로 검사한다. Codex 이미지 임시 파일 내용과 정리, Claude 이미지 거부도 검사한다. 두 경로의 중복 코드를 통합하거나 이미지 지원을 확대하지 않는다.
- 테스트: provider contract와 엔진을 함께 사용해 Codex 이미지, Claude 텍스트, timeout→로컬을 검사한다. 다른 API adapter 호출 0회, 오류의 비밀 마스킹, 실제 method/model 보존을 단언한다.
- 명령: `python -m unittest discover -s tests -p 'test_providers.py' -v`, `python -m unittest discover -s tests -p 'test_ai_runtime.py' -v`.
- 완료: 지원 CLI의 정확한 응답을 엔진 분류 결과로 저장하며 실패는 로컬로 복구된다.
- 커밋: `fix: [P6] #11 CLI 비대화식 응답과 timeout 검증`.

### Phase 7 (완료) — API 동의 경계 회귀

- 의존: P6.
- 변경 파일 (3개 이내): `engine.py`, `tests/test_ai_runtime.py`, `tests/test_saved_projects.py` (기존 API fixture 조정이 필요한 경우만).
- 대상: `scan_images`의 `legacy_remote_request`/`consent` 결정과 `classify_provider_error`.
- 선례: `providers.py:resolve_execution`, `tests/test_providers.py:ExecutionPolicyTest`, `tests/test_ai_runtime.py:test_consented_api_failure_only_retries_local`.
- `provider`/`use_llm` 지정만으로 API 동의를 암묵적으로 생성하지 않게 한다. mode 지정 여부와 무관하게 `api_consent=None`이면 정확한 공급자·이미지 범위 저장 동의만 읽고, False는 저장 True보다 우선한다. 기존 API 호출 fixture가 공급자 지정만으로 실행을 기대하면 명시 `api_consent=True`로 갱신한다. 함수 인자와 local-only 동작은 유지하며, GUI/CLI 호출자는 반드시 동의 bool을 전달한다.
- 공급자 변경·텍스트 동의 후 이미지 켜기·저장 동의 없음/취소 시 SDK 요청 0회, 로컬 결과 저장을 검증한다. 현재 `scan_with`처럼 `resolve_execution` 전체를 mock한 테스트만으로 보장하지 않는다.
- API 인증/한도/네트워크/timeout와 2차 그룹 정규화 실패에 대해 실제 resolver+엔진으로 로컬 복구, 유료 공급자 추가 요청 0회, 마스킹된 상태를 검사한다. 이미지 전송 여부는 최종 로컬 여부와 별개로 이미 시도한 전송을 숨기지 않는다.
- 명령: `python -m unittest discover -s tests -p 'test_ai_runtime.py' -v`, `python -m unittest discover -s tests -p 'test_saved_projects.py' -v`.
- 완료: 모든 엔진 API 진입점은 명시 또는 범위가 일치하는 저장 동의가 필요하며, 기존 local/동의된 API 호출은 유지된다.
- 커밋: `fix: [P7] #11 API 전송 동의 경계 회귀 보강`.

### Phase 8 (완료) — 비밀 제외 설정·캐시의 재실행 복원

- 의존: P7.
- 변경 파일 (5개 이내): `app.py`, `model_settings.py`, `tests/test_ai_runtime.py`, `tests/test_app_ai_contract.py`, `README.md`.
- 대상: `index`의 `ai_settings` 초기값과 `do_scan` 저장, `ModelSettings`, `model_settings_controls` 초기화/승인 취소 경계.
- 선례: `tests/test_saved_projects.py:SavedProjectsTest.setUp`의 임시 `DB_PATH`, `tests/test_ai_runtime.py:test_stale_catalog_is_refreshed_and_failure_keeps_cached_models`, `tests/test_app_ai_contract.py:test_direct_mode_uses_only_approved_settings`.
- 파일 SQLite에 mode/provider/model/이미지 범위와 동의를 저장하고 연결을 닫은 뒤 새 연결(필요 시 subprocess)에서 동일 값·모델 목록·조회 시각·stale 상태가 복원됨을 검사한다. 24시간 내 재조회 없음, 만료 후 조회 실패 시 마지막 목록/시각 유지, 공급자·실행 방식별 격리도 검사한다.
- 일반 설정과 승인된 직접 설정의 비밀 제외 선택을 복원한다. 직접 입력 API 키는 저장하지 않으며 재실행 후 환경변수 키가 없으면 키 재입력 안내/로컬 복귀한다. 승인하지 않은 초안과 취소는 저장·적용되지 않는다. 저장 이미지 범위와 API 동의 범위를 함께 복원해 권한이 확대되지 않게 한다.
- 저장 모델이 사라진 경우 입력 유지→명시 확인 후 자동 추천 전환을 검사한다. 현재의 문자열 존재 검사 외에 제어 함수/실제 이벤트 검증을 보강한다.
- README의 Keychain 저장/조회 주장과 실제 환경변수·화면 메모리 키 정책을 맞춘다. 새 보안 저장소 기능은 추가하지 않는다.
- 명령: `python -m unittest discover -s tests -p 'test_ai_runtime.py' -v`, `python -m unittest discover -s tests -p 'test_app_ai_contract.py' -v`.
- 완료: 재실행 후 비밀 제외 선택과 캐시가 정확히 복원되고, 화면·DB·기록에 키 값이 남지 않는다.
- 커밋: `fix: [P8] #11 분석 설정과 모델 캐시 재실행 복원`.

### Phase 9 (완료) — GUI/CLI 실행 전 안내와 종단 검증

- 의존: P6~P8.
- 변경 파일 (5개 이내): `engine.py`, `cli.py`, `app.py`, `tests/test_cli_ai_contract.py`, `tests/test_app_ai_contract.py`.
- 대상: `scan_images`, `cmd_scan`, `_print_execution_status`, `refresh_mode`, `request_api_consent`, `do_scan`.
- 선례: `engine.py:ItemCallback`처럼 출력 대신 콜백으로 전달하는 구조, `cli.py:_print_execution_status`, `app.py:refresh_mode`의 선택 예정 경로.
- CLI의 실제 provider/model/method·전송·fallback 사유를 첫 원격 분류 요청 전에 표시한다. 필요하면 엔진에서 resolve 후 상태 콜백을 최소 추가해 동일 결정을 사용하고, CLI에서 별도 resolver를 재실행해 다른 경로를 표시하지 않는다. GUI도 동의 후/스캔 직전 선택이 바뀌면 실제 예정 경로를 표시한다. 종료 시에는 실제 결과를 표시한다.
- CLI integration은 `cmd_scan`→실제 engine/resolver→fake subprocess/SDK→임시 DB까지 연결한다. 기존 `scan_images` 전체 mock 선례만으로 완료하지 않는다. auto Codex 성공/Claude 텍스트 대체/이미지 Claude 제외/미동의·거부/동의 API 실패/local-only를 검사한다. 출력 순서(전송 안내가 요청보다 앞섬), 결과 DB, 유료 재시도 없음, key와 인증 원문 비노출을 단언한다.
- GUI는 fake capability/adapter와 임시 상태 DB로 시작하고 브라우저에서 primary flow와 빈/로딩/오류 상태를 확인한다. `ui-design` match mode, 데스크톱과 390px, 키보드 이동·보이는 포커스·한국어 긴 문구·구체적 복구 안내를 검사한다. 동의 승인/취소, 이미지 범위 변경, 직접 설정 취소, 재실행 복원을 실제 이벤트로 확인하고 증거를 log에 남긴다.
- 명령: `python -m unittest discover -s tests -p 'test_cli_ai_contract.py' -v`, `python -m unittest discover -s tests -p 'test_app_ai_contract.py' -v`, `python cli.py scan --help`, 최종 `python -m unittest discover -s tests -v`와 `.github/workflows/ci.yml`의 compile 검사.
- 완료: GUI/CLI가 같은 동의·fallback 정책과 실제 경로를 보여 주고, 브라우저 증거와 전체 회귀 검증이 현재 구현 SHA에 연결된다.
- 커밋: `test: [P9] #11 GUI CLI 분석 통합 검증` (코드 fixup 포함 가능).

## 최종 완료 조건과 후속 경계

1. P1~P5 커밋과 기존 구현은 유지하고 P6~P9를 각각 작은 `[PN]` 커밋으로 마친다. 실패가 확인된 방법은 원인을 기록하고 다른 검증 경로를 택한다.
2. 설치·인증·비대화식 실행·이미지 지원·구조화 출력·timeout의 지원/제외 근거가 있다. Claude 이미지를 지원한다고 주장하지 않는다.
3. 자동 추천, 모델 캐시 실패/복원, 저장 모델 폐기 확인, 실제 공급자/모델/방식 표시가 GUI와 CLI에서 확인된다. CLI 기본 모델명을 알 수 없으면 추측하지 않고 CLI 기본 모델로 표시한다.
4. 동의 없는 API 전송과 다른 유료 API 자동 재시도가 없다. API 불가/실패에도 로컬 스캔·저장 프로젝트·정규화가 동작한다. CLI도 외부 전송임을 요청 전에 알린다.
5. 설정 재실행 복원과 키 비저장·비노출, 기존 local-only·vendor shorthand 회귀를 검사한다. 실제 계정/유료 요청을 하지 않은 한계는 명시한다.
6. 브라우저 검증과 전체 테스트를 최종 코드 SHA 기준으로 기록한다. 현재 통과한 테스트만으로 미완료 phase를 완료 처리하지 않는다.
7. phase 완료 마커는 plan에, 실행·실패·재개 증거는 옆 `.log.md`에 쓴다. 기록 때문에 새 필수 조건이 생기면 plan도 수정하며 **두 파일을 `git add -f`로 함께 보존**한다.
8. 후속 파이프라인이 local/origin/PR head와 CI SHA를 대조한다. 현재 `/plan`은 문서 커밋까지만 수행하며 Draft PR을 유지한다.
