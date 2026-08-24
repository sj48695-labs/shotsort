# #3 중복·유사 이미지 검사 CLI 계획

## 현재 상태와 범위

- 현재 브랜치 `3-cli`에는 #2의 `engine.find_duplicate_groups()`가 이미 머지되어 있다. 이 API는 `exact`/`near` 그룹, 결정적 `keeper`, keeper 기준 `member_similarities`, 그리고 개별 `errors`를 반환한다.
- `cli.py`는 `argparse` 하위 명령과 `cmd_*` 핸들러를 사용하는 얇은 래퍼다. 현재 `trash`는 그룹/삭제후보 전체를 대상으로 하므로, 이 이슈의 선택 삭제 흐름에 재사용하면 안 된다.
- `engine.find_images(root)`는 단일 이미지 또는 디렉터리 아래의 지원 이미지 경로를 반환한다. `engine.trash(paths)`는 휴지통 이동 뒤 DB 행을 정리하므로, CLI는 사용자가 명시적으로 선택해 변환한 경로만 이 함수에 넘긴다.
- 범위는 CLI, 문서, CLI 회귀 테스트다. #4의 GUI 중복 검토 화면이나 `engine.py`의 탐지·캐시 알고리즘은 변경하지 않는다. 작업트리·브랜치 정리도 수행하지 않는다.

## CLI 계약

`shotsort similarity [path] [--threshold N] [--delete GROUP:NUMBER]... [-y]`를 추가한다.

- `path`는 검사할 파일 또는 재귀 디렉터리이며, 기본값은 `DEFAULT_SCAN_DIR`이다. 존재하지 않으면 기존 `scan`과 같은 방식으로 종료한다.
- `--threshold`는 #2 API에 그대로 전달할 0 이상의 pHash Hamming 거리이며, 기본값은 `8`이다. 낮을수록 더 엄격하다.
- 출력 그룹은 안정적인 1부터 시작하는 그룹 번호를 갖는다. 각 그룹에는 exact/유사 구분, 보존 후보, 각 구성원의 선택 번호·keeper 기준 유사도·파일 크기·경로를 표시한다. `DuplicateDetectionResult.errors`는 검사 실패 경로와 원인을 별도로 출력한다.
- `--delete GROUP:NUMBER`는 반복 가능하며, 출력된 그룹 번호와 그 그룹 안의 구성원 번호를 함께 명시해야 한다. 파싱 오류, 존재하지 않는 그룹/번호, keeper 번호, 중복 선택은 삭제 대상에서 제외하거나 명확히 오류로 종료한다. 그룹만 또는 번호만으로는 어떤 파일도 삭제하지 않는다.
- 삭제 요청이 없으면 검사는 읽기 전용이다. 유효한 비-keeper 선택이 있을 때만 대상 전체 경로를 먼저 출력하고 기존 y/N 확인(`-y`는 생략)을 거친 뒤 `engine.trash()`를 한 번 호출한다. 취소·선택 없음·검사 결과 없음·유효하지 않은 선택에서는 `engine.trash()`를 호출하지 않는다.

## 현재 구조와 선례

- `cli.py:cmd_trash`의 대상 미리보기, y/N 확인, `RuntimeError`의 stderr 처리와 `cli.py:build_parser`의 하위 명령 등록을 따른다.
- `engine.py:find_images`, `engine.py:find_duplicate_groups`, `engine.py:DuplicateGroup.keeper`, `engine.py:DuplicateGroup.member_similarities`, `engine.py:human_mb`, `engine.py:trash`를 호출 경계로 사용한다. CLI에서 pHash, keeper 우선순위, 유사도 점수를 재계산하지 않는다.
- `tests/test_similarity.py`의 `ImageFingerprint`/`DuplicateGroup` 픽스처와 `unittest.mock.patch.object` 방식이 엔진 API를 고정한 CLI 테스트의 선례다.
- `README.md:CLI`은 명령 예시 위치이고, `README.md:중복·유사 이미지 탐지 API`의 “UI와 CLI도 현재 이 API를 호출하지 않습니다”는 #3 완료 시 갱신할 문장이다.

## Phase 1 (완료): 검사 출력과 명시적 선택 삭제

변경 파일: `cli.py`, `tests/test_cli_similarity.py`

선례: `cli.py:cmd_trash`, `cli.py:build_parser`, `engine.py:find_images`, `engine.py:find_duplicate_groups`, `engine.py:trash`, `tests/test_similarity.py:test_near_group_scores_members_against_keeper_deterministically`

1. `cli.py`에 유사도 검사 결과를 일관된 번호·크기·점수 형식으로 렌더링하고 `GROUP:NUMBER` 선택값을 검증·경로로 변환하는 작은 보조 함수를 추가한다. keeper는 보존 후보로 표기하며 삭제 대상 후보에서 제외한다.
2. `cmd_similarity(args)`를 추가해 경로 존재 여부 확인 → `engine.find_images()` → `engine.find_duplicate_groups(..., hamming_threshold=args.threshold)` → 그룹/오류 출력 순서로 수행한다. 선택이 없으면 여기서 종료해 탐지의 비파괴성을 보장한다.
3. 유효한 `--delete` 선택만 수집해 대상 경로와 개수를 출력하고, `cmd_trash`와 같은 y/N 확인 및 오류 처리를 적용한다. 확인된 선택 경로만 하나의 `engine.trash(paths)` 호출에 전달하고 결과 개수를 출력한다.
4. `build_parser()`에 기본 경로, 0 이상 정수 임계값, 반복 가능한 `--delete`, `-y/--yes`를 갖는 `similarity` 하위 명령과 한국어 help를 등록한다. `--help`가 임계값 의미와 명시 선택 삭제를 설명하게 한다.
5. 새 `tests/test_cli_similarity.py`에서 임시 경로와 패치된 엔진 API로 다음을 검증한다: argparse 기본값/사용자 임계값 전달, exact·near·keeper·점수·파일 크기·번호 출력, 오류 출력, `GROUP:NUMBER`에서 비-keeper 경로만 선택되는 변환, 확인 거절/선택 없음/잘못된 선택에서 `trash` 미호출, `-y` 승인 시 선택 경로만 단 한 번 전달, `RuntimeError` stderr 처리. 실제 macOS 휴지통이나 사용자 캐시에는 쓰지 않는다.

완료 기준: 검사 결과에서 사용자가 안전하게 각 그룹을 비교할 수 있고, 명시한 그룹·비-keeper 번호 이외의 경로는 어떤 경우에도 `engine.trash()`에 전달되지 않는다.

예정 커밋: `feat: [P1] #3 유사 이미지 검사와 선택 삭제 CLI 추가`

## Phase 2 (완료): CLI 사용법과 한계 문서화

변경 파일: `README.md`

선례: `README.md:CLI`, `README.md:중복·유사 이미지 탐지 API`

1. CLI 예시에 `similarity` 기본 검사, 사용자 경로, 엄격한 `--threshold`, 명시적 `--delete GROUP:NUMBER` 및 `-y` 실행 예를 추가한다.
2. 출력의 exact/유사, 보존 후보, 구성원 번호, keeper 기준 유사도와 파일 크기의 의미를 설명하고, 대표 후보와 미선택 파일은 자동 삭제되지 않으며 실제 삭제 전 y/N 확인이 있다는 안전 계약을 기록한다.
3. API 섹션의 “UI와 CLI도 현재 이 API를 호출하지 않습니다” 문구를 CLI는 호출한다고 갱신한다. pHash 임계값은 Hamming 거리라 낮을수록 엄격하고, 시각적 휴리스틱이라 오탐·미탐이 가능하다는 한계를 사용자 관점에서 다시 명시한다.

완료 기준: README와 `shotsort similarity --help`만으로 검사를 실행하고, 출력 번호를 이용해 의도한 파일만 선택 삭제하는 방법과 유사도 한계를 이해할 수 있다.

예정 커밋: `docs: [P2] #3 유사 이미지 CLI 사용법 추가`

## 검증

각 phase에서 해당 테스트와 구문 검사를 실행하고, Phase 2 뒤 전체 회귀를 실행한다.

```bash
python -m unittest tests/test_cli_similarity.py
python -m py_compile cli.py
python cli.py similarity --help
python -m unittest discover -s tests
```

테스트가 실패하면 먼저 기존 실패와 #3 회귀를 분리한다. #3 변경이 원인인 실패는 해당 phase에서 고친 뒤 다시 검증하며, 계획 단계에서는 구현 파일을 변경하지 않는다.
