# #2 유사 이미지 탐지 엔진 마무리 계획

## 현재 상태와 범위

- Draft PR #5 (`2-sqlite` → `main`)를 계속 사용한다. 작업트리·브랜치 정리나 교체는 하지 않는다.
- `origin/main`의 최신 7개 커밋(`82ef4e3`…`390321c`)은 현재 HEAD의 조상이다. 따라서 별도 merge/rebase 없이 이미 반영되어 있으며, 구현 전후에 이 관계를 다시 확인한다.
- P1~P3은 각각 `afa59d3`, `7b1d24a`, `1daebba`로 완료되어 있다. `engine.py`에는 전체 스트리밍 SHA-256, EXIF 방향 정규화 pHash, SQLite 버전 캐시, exact 우선 complete-link 그룹화, 결정적 `keeper`/`duplicate_candidates` 계약이 이미 있다.
- 남은 #2 범위는 #3 CLI와 #4 GUI가 공통으로 표시할 **구성원별 유사도 점수**를 결과 계약에 추가하고, 기존 유사 이미지 회귀 범위를 완성하는 것이다. CLI/UI 및 파일 삭제는 이 이슈에서 바꾸지 않는다.

## 현재 구조와 선례

- `engine.py:ImageFingerprint`는 경로·SHA-256·pHash를, `engine.py:DuplicateGroup`은 그룹 종류·구성원·보존 후보를 공개한다.
- `engine.py:find_duplicate_groups()`는 확장자 필터 → `image_fingerprint()` 캐시 수집 → SHA exact 우선 → 경로순 complete-link near 그룹화를 수행한다.
- `engine.py:_phash_distance()`와 `_with_keeper()`가 점수 계산 및 결과 조립의 인접한 선례다.
- `tests/test_similarity.py`는 인메모리 SQLite와 생성 파일/이미지, `patch.object(engine, "image_fingerprint", ...)`로 그룹 계약을 격리 검증한다.
- `README.md:중복·유사 이미지 탐지 API`가 후속 호출자가 보는 공개 계약 설명 위치다.

## 점수 결과 계약

- 그룹은 각 `member`에 대해 `keeper`를 기준으로 한 유사도 정보를 노출한다. exact 그룹의 모든 구성원은 100%이며, near 그룹은 동일 비트 수의 pHash Hamming 거리로 결정한 0~100% 점수다. 점수가 클수록 더 유사하다.
- API는 점수의 기준 구성원(보존 후보), 거리/점수의 단위와 exact의 100% 규칙을 명확히 문서화한다. 후속 #3·#4가 입력 순서나 화면별 재계산 없이 구성원별 수치를 표시할 수 있어야 한다.
- keeper 자신도 100%를 가진다. pHash가 없거나 유효한 거리를 만들 수 없는 파일은 near 그룹에 속지 않으며, exact 우선/complete-link/보존 후보 정책은 바꾸지 않는다.

## Phase 4 (완료): 구성원별 유사도 점수 결과 계약

변경 파일: `engine.py`, `tests/test_similarity.py`, `README.md`

선례: `engine.py:ImageFingerprint`, `engine.py:DuplicateGroup`, `engine.py:_phash_distance`, `engine.py:_with_keeper`, `tests/test_similarity.py:test_near_duplicates_are_grouped_within_hamming_threshold`, `README.md:중복·유사 이미지 탐지 API`

1. `engine.py`에 그룹 구성원과 keeper 기준 pHash 거리·백분율 유사도를 표현하는 불변 결과 타입(또는 동등하게 명시적이고 안정적인 그룹 필드)을 추가한다. 기존 `members`, `keeper`, `duplicate_candidates` 소비 계약은 유지한다.
2. `_with_keeper()`가 keeper를 먼저 결정한 뒤 exact에는 100%, near에는 keeper와의 Hamming 거리 및 pHash 비트 폭으로 계산한 결정적 점수를 함께 조립하게 한다. 반올림 방식과 정렬을 고정하여 같은 입력에서 같은 결과가 나온다.
3. `find_duplicate_groups()`의 exact 우선과 complete-link 검증은 그대로 둔다. 점수 계산 실패가 전체 탐지를 중단시키지 않도록 정상적으로 형성된 near 그룹만 점수화한다.
4. `tests/test_similarity.py`에 exact 구성원 전체 100%, near의 keeper/비-keeper 점수와 거리, 입력 순서 안정성, 임계값 경계 및 기존 complete-link 체인 분리를 추가한다. 실제 생성 이미지로 동일 파일, 재압축·리사이즈·포맷 변환의 near 탐지와 명확히 비유사한 이미지의 제외도 보강한다. 모든 테스트는 현재처럼 임시 SQLite만 사용한다.
5. `README.md`에 구성원별 점수의 기준(keeper), exact/near 계산 방식, pHash 기반 점수의 오탐·미탐 한계를 기록한다. #3/#4가 그대로 표시할 수 있는 공개 필드명을 명시한다.

완료 기준: 모든 반환 그룹이 구성원별 결정적 점수를 제공하고, exact는 100%, near는 keeper 기준으로 재현 가능하며, 기존 보존 후보·그룹화·비파괴성 계약이 깨지지 않는다.

예정 커밋: `feat: [P4] #2 구성원별 유사도 점수 계약 추가`

## 검증

Phase 4 완료 뒤 아래를 실행한다. `requirements.txt` 환경에서 실행하며, 테스트가 사용자 `~/.shotsort/cache.db`에 쓰지 않는 것을 유지한다.

```bash
python -m unittest tests/test_similarity.py
python -m unittest discover -s tests
python -m py_compile engine.py
git merge-base --is-ancestor origin/main HEAD
```

전체 회귀가 실패하면 #2 변경과 무관한 기존 실패인지 먼저 분리하고, #2가 원인인 실패는 같은 phase에서 고친 뒤 위 검증을 다시 통과시킨다.
