# #11 계획 재검토 기록

## 2026-11-13 /plan 재검토 완료

- 범위: 조사·계획 재작성·plan 커밋만. 구현·push·PR 상태 변경·merge·worktree 정리 없음.
- 조사 기준 HEAD/local tracking/Draft PR #13 head: `45419136c31d87f663d05b9d1913738c32590248`.
- 최신 이슈: https://github.com/sj48695-labs/shotsort/issues/11
- 최신 지침: https://github.com/sj48695-labs/shotsort/issues/11#issuecomment-6845476497
- 이전 지침: 2026-11-04와 2026-11-11 댓글도 기존 구현 재사용과 누락 fixup을 요구한다.
- PR #13: OPEN, Draft. CI `test` SUCCESS (2026-11-10); PR 본문에 적힌 `d25ac05`는 현재 head가 아니므로 현재 검증 증거로 재사용하지 않는다.
- 현재 HEAD에서 `/Users/sujeong/personal/github/sj48695-labs/shotsort/.venv/bin/python -m unittest discover -s tests -v`: **157 tests, OK**, 1.330s. 원시 출력은 임시 `/tmp/shotsort-11-plan-tests.txt`; 보존할 결과는 이 문서에 요약했다.
- 테스트는 subprocess/SDK fake 기반이다. 실제 AI 요청, 실제 스크린샷 전송, 실계정 로그인 및 유료 API 요청은 하지 않았다. GUI 브라우저 검증도 하지 않았다.
- `/tmp/pm-meeting-ww5VhN`은 존재하지 않았다. 최신 이슈 본문과 세 댓글, 사용자 PM 지침을 입력으로 사용했다.
- 기존 plan을 최신 요구와 대조한 자체 검토 2회 완료: P1~P5 완료 이력 보존, P6~P9만 미완료, 각 phase 5개 이하 파일·단일 관심사, 동의 경계·복원·통합 검증 반영.
- 재개 입력은 옆 `.md`의 설계와 미완료 조건이다. 이 기록은 특정 증적이 필요할 때만 읽는다.

## 이전 plan에서 분리한 조사 기록 (원문)


- 기준 worktree/브랜치는 `11-ai-analysis-cli-fallback`이며, 기준 커밋은 `cebb920`이다. 작업 시작 시 추적/미추적 변경은 없다.
- 이슈 #11에는 댓글·라벨이 없으며, 현재 구현은 `providers.ProviderConfig`와 `StructuredProvider`로 Anthropic/OpenAI/xAI **API** 호출만 어댑트한다. `resolve_config()`는 원격 모델명을 필수로 하고, `codex` 별칭을 API OpenAI로 바꾼다.
- `engine.scan_images()`는 공급자를 생성한 뒤 이미지별 분류와 2차 그룹 정규화에 같은 adapter를 쓰며, 오류는 각 이미지의 오류로만 남긴다. 실행한 방식·외부 전송·fallback 사유를 반환하거나 저장하지 않는다.
- GUI [`app.py`](../app.py)는 local/API 4개 선택과 자유 모델명 입력만 제공하며, CLI [`cli.py`](../cli.py)는 API key가 있으면 Anthropic을 기본 선택한다. 어느 쪽도 사용자 동의나 모델 목록/캐시를 갖지 않는다.
- 현재 설치본에서 `codex exec --help`는 `--image`, `--output-schema`, `--sandbox`, `--ephemeral`을 제공하고 `codex login status`도 제공한다. 따라서 첫 CLI 어댑터는 Codex CLI로 한정한다. `claude -p`는 JSON schema와 인증 상태 명령은 확인됐지만, 로컬 이미지를 비대화식으로 첨부하는 안정된 인터페이스를 이 조사에서 확인하지 못했다. Claude CLI는 이름만 지원 대상으로 표시하지 않고, 추후 검증된 이미지 입력 계약이 생긴 뒤 별도 adapter로 추가한다.
- 회의록 경로 `/tmp/pm-meeting-JqcUf3`는 현재 존재하지 않아 읽을 수 없었다. 이 계획은 이슈 본문과 현 코드로 확정한다.


## 이전 완료 표시와 커밋 대조

| 완료 phase | 확인한 커밋 |
| --- | --- |
| P1 실행 정책/Codex | `64145d5` |
| P2 엔진 fallback/캐시 | `17647ec` |
| P3 UI | `fc5871f` |
| P4 CLI | `cc99029` |
| P5 Claude/PC 계정 실행 상태 | `0ba63f0`, `4541913` |

기존 phase의 `구현/검증` 목록은 실행 결과가 아닌 계획이었다. 실제 이번 실행 결과는 위 157개 테스트 통과만이며, 기존 완료 마커가 실제 CLI/브라우저 검증까지 증명하지는 않는다.

## P6 실행 검증 (2026-11-13)
- 설치 help: Codex --image/--output-schema/--output-last-message, Claude --print/--json-schema/--output-format/--tools 확인. auth status는 종료 코드 0만 기록, 인증 원문 미보존. 실제 분류 요청 없음.
- RED: 최종 출력 파일 flag 없음 및 Claude structured_output 미해제 2건 재현. GREEN: provider 28개, runtime 11개 통과. Codex 이미지 임시 파일 정리·stdin, Claude envelope/필수 키, probe 실패 조합, 실제 resolver→adapter→DB와 timeout 로컬 복구 검증.

## P7 실행 검증 (2026-11-13)
- RED: 공급자 변경/이미지 범위 확대/legacy 공급자 선택의 무동의 전송 3건과 TimeoutError 분류 누락 재현.
- GREEN: runtime 13개 및 saved_projects 회귀 통과. 실제 resolver로 저장 동의/명시 False 우선, 공급자·이미지 격리, 인증/한도/네트워크/timeout/2차 정규화 실패의 로컬 복구·추가 공급자 요청 없음 검증. 전송 시도는 fallback 이후에도 표시.

## P8 실행 검증 (2026-11-13)
- 일반 이미지 선택 및 승인된 직접 설정의 공급자/모델/이미지만 저장·복원. 화면 입력 키는 제외하고 환경변수만 재조회. 키가 없으면 재입력 안내와 resolver의 로컬 fallback 사용. 승인 취소는 기존 승인 후 대입/콜백 경계 유지.
- runtime 14개 / GUI contract 9개 통과. 파일 SQLite 연결을 닫고 새 연결에서 설정·공급자/이미지별 동의·공급자/실행별 캐시 복원 검사. 24시간 내 조회 없음, 만료 조회 실패 후 목록/시각/출처 보존 검사. README Keychain 주장을 실제 구현에 맞춤. 실제 GUI 이벤트 증거는 P9에 기록.

## P9 실행 검증 (2026-11-13)
- 엔진 resolve/adapter 초기화 후 동일 실행 결정을 on_execution으로 전달. CLI는 첫 요청 전 실제 provider/model/method/전송·fallback을 출력하고 GUI는 실행 예정/결과를 표시. 원격 시도가 없는 빈 스캔은 외부 전송 없음. 실패 후 이미 시도한 전송은 보존.
- CLI 통합: 실제 cmd_scan→engine/resolver→CLI subprocess fixture/API failure fixture→임시 파일 DB. auto Codex/Claude 텍스트, 이미지 Claude 제외, API 미동의, 동의 API 실패, local-only, 출력 순서·DB 저장·추가 공급자 요청 없음·비밀 마스킹 검사.
- GUI: Playwright + NiceGUI 3.x 임시 venv, 임시 DB `/tmp/shotsort-11-gui-state`, fake CLI capability/API adapter만 사용. 1280x900 및 390x844. URL http://127.0.0.1:8725/ (마지막 모델 확인 수정은 :8727/).
- 실제 이벤트: 빈 화면, API 동의 취소→로컬 저장, 승인, 이미지 켜기→재동의, 새 화면 이미지 복원, 직접 설정 승인 취소→초안 미적용, 승인→요약 갱신→새 화면 승인 선택 복원, 로딩 중 중복 실행 방지, timeout→로컬 복구+전송 시도 표시, 키보드 Tab 이동, 모바일 가로 overflow 없음. 초기 브라우저 스크립트의 캐시 상태 단언은 이전 상태를 읽을 수 있어 증거로 채택하지 않음. 후속 검증은 실행 예정/결과 상태 전이를 기다려 timeout·전송 표시를 재확인.
- 저장 모델 확인에서 기존 휴지통 버튼을 재사용하던 문구 발견. 확인 버튼에 작업 이름을 전달하도록 최소 수정. 최신 서버 :8727에서 missing-model 입력 유지→취소 유지→명시 승인 후 자동 추천 전환을 실제 이벤트로 검사. 추가 AST 이벤트 테스트로 승인/취소 분기 검증.
- 화면 증거: `output/playwright/11-consent-desktop.png`, `11-consent-mobile.png`, `11-direct-approved-mobile.png`, `11-loading-mobile.png`, `11-fallback-mobile.png`, `11-final-desktop.png`, `11-final-model-mobile.png`.
- 실패/대체 경로: 기본 Playwright 캐시 쓰기 EPERM→임시 daemon 경로 사용. Chrome SIGABRT→브라우저 실행 권한 확장으로 해결. 테스트 harness 업데이트 stub의 None 반환은 available=False fixture로 정정했고 제품 코드 변경 없음. password input form 관련 Chrome verbose 메시지는 오류 아님.
- 최종 검증: 기본 Python 전체 166개 통과; Pillow/ImageHash/NiceGUI 포함 임시 venv 전체 166개 통과. CI compileall 및 추가 model_settings/cli_provider compile, scan --help, git diff --check 통과. 저장소에 별도 typecheck/lint 명령은 없음. 신규 의존성 추가 없음.
- 한계: 실제 계정 분류/유료 API 요청 없음. macOS native 창은 미검증. 품질 검토/simplify와 PR 후속 작업은 요청대로 후속 파이프라인에 위임. 브랜치/worktree 정리·rebase·push·merge 수행하지 않음.
- 아래 소스 해시는 브라우저 최종 확인 및 전체 검증의 코드 식별자이며, 이 로그와 같은 P9 커밋에 보존한다.
- `app.py` SHA256 `e9a7f8c99e283d44e1a530c1b6a69d85b767ccf90b2466ef3a611a28c2e09f39`
- `cli.py` SHA256 `5d15ea6cc645fb99e329dd4f0d840ed6a85b1ea5bd63518c38b82fac84745979`
- `engine.py` SHA256 `9e530c305db4293e29e872495d7aa00d5354b0a8220421c8db1027dd46fdd48c`
- `providers.py` SHA256 `ed3eaf109d6b8d05b1b8d5bce838d23610d394e46e70a70bf8ba137ed8f925a0`
- `model_settings.py` SHA256 `7b4b357653259f3521ade51795fe83f72332a3771e4303daf7ae76146b7d939d`

- 마지막 모델 확인 스크립트는 배경 버튼과 대화상자 버튼의 동일 이름 때문에 strict locator 충돌. 트리거 first/승인 last로 범위를 나누고 취소 후 dialog hidden을 기다리는 방법으로 수정하여 성공. :8727 실제 이벤트 결과 `missing_model_cancel_and_confirm=passed`, 오류 요소 0.
