# #2 유사 이미지 탐지 API 계획

## 조사 결과

- 핵심 로직은 `engine.py`에 있으며, OCR/LLM 분류는 `scan_images()`에서 수행하고 SQLite 캐시는 `db()`의 `images` 테이블을 사용한다.
- 현재 `file_sha()`는 앞 2 MB와 파일 크기만 해시하므로, 요구사항의 파일 전체 스트리밍 SHA-256으로 교체해야 한다.
- Pillow는 이미 `requirements.txt`에 있으나 perceptual hash 라이브러리와 유사도 테스트는 없다.
- GitHub API 접근이 현재 실행 환경에서 차단되어 #2의 원문 댓글 및 동시 배치 이슈(#1, #3, #4)는 조회하지 못했다. 아래는 전달된 PM 구현 지침을 구현 계약으로 삼는다.

## API 경계

- OCR 분류 흐름과 별개로 `engine.py`에 공개 탐지 API를 둔다. `scan_images()`·`consolidate_all()`·UI/CLI의 현 동작은 호출하거나 변경하지 않는다.
- API는 경로 목록(또는 스캔 루트에서 얻은 이미지)을 입력으로 받아, 검증을 통과한 중복 그룹과 그룹별 보존 후보를 반환한다.
- 정확 중복은 전체 SHA-256 일치가 우선이며, perceptual hash는 이미지가 정상적으로 열리는 경우에만 근접 중복 후보를 만든다.

## Phase 1 (완료) — 지문 계산과 SQLite 버전 캐시 기반 마련

변경 파일: `engine.py`, `requirements.txt`, `tests/test_similarity.py`

선례: `engine.py:db`, `engine.py:file_sha`, `engine.py:find_images`, `engine.py:scan_images`

1. `requirements.txt`에 `ImageHash`를 추가하고, `engine.py`에 유사도 지문용 스키마 버전 상수를 둔다.
2. `db()`의 마이그레이션 안전한 `CREATE TABLE IF NOT EXISTS`/컬럼 추가 흐름으로 파일 경로, mtime, size, 알고리즘 버전, 전체 SHA-256, perceptual hash를 저장하는 전용 캐시를 만든다. 기존 OCR `images` 행과 캐시 키를 섞지 않는다.
3. `file_sha()`를 고정 크기 청크로 끝까지 읽는 스트리밍 SHA-256으로 바꾸고, 크기를 별도로 덧붙이지 않는다.
4. Pillow의 `ImageOps.exif_transpose()`로 EXIF 방향을 정규화한 뒤 `imagehash.phash()`를 계산하는 내부 지문 함수를 추가한다. 읽기/디코드 실패는 개별 파일 오류로 격리한다.
5. 파일의 mtime·size·알고리즘 버전이 같을 때만 캐시를 재사용하고, 하나라도 다르면 재계산·upsert하도록 한다. DB 연결은 임시 DB를 주입할 수 있게 하여 전역 사용자 캐시를 테스트에서 건드리지 않는다.
6. `tests/test_similarity.py`에서 임시 SQLite DB와 생성 이미지로 전체 SHA-256(2 MB 이후 변경 포함), 캐시 적중/무효화, EXIF 방향 정규화를 검증한다.

완료 기준: 해시 계산은 파일 전체를 스트리밍하며, 동일 메타데이터+버전에는 재계산하지 않고, 테스트가 실제 사용자 `~/.shotsort/cache.db`를 사용하지 않는다.

## Phase 2 — 독립적인 exact/near 탐지와 complete-link 검증

변경 파일: `engine.py`, `tests/test_similarity.py`

선례: `engine.py:find_images`, `engine.py:ScanResult`, `engine.py:scan_images`

1. 지문을 수집하는 공개 API와 중복 그룹 결과용 dataclass를 `engine.py`에 추가한다. 이 API는 OCR, Claude 클라이언트, `images` 분류 테이블에 의존하지 않는다.
2. 전체 SHA-256이 같은 파일을 먼저 exact 그룹으로 만든다. exact 그룹 구성원은 perceptual hash 거리와 무관하게 한 그룹이다.
3. 아직 exact 그룹에 속하지 않은 이미지에 대해 perceptual hash Hamming 거리 임계값으로 근접 후보를 만든다.
4. 체인 오탐을 막기 위해 complete-link를 적용한다. 새 항목은 그룹의 모든 구성원(또는 문서화된 대표 기준 선택 시 대표와 모든 검증 조건)과 임계값 이내일 때만 합류시킨다. 입력 순서가 결과를 바꾸지 않도록 안정적인 경로 정렬을 사용한다.
5. 테스트에 exact 우선, 유사한 2개 결합, `A~B`, `B~C`지만 `A!~C`인 체인 분리, 손상/비이미지 입력의 안전한 제외를 추가한다.

완료 기준: 결과는 같은 입력에서 안정적이고, exact가 near보다 우선하며, transitive near-match가 검증 없이 한 그룹으로 이어지지 않는다.

## Phase 3 — 보존 후보 선택과 호출자 친화 결과 계약

변경 파일: `engine.py`, `tests/test_similarity.py`, `README.md`

선례: `engine.py:list_groups`의 정렬 규칙, `engine.py:human_mb`, `README.md`의 분석 동작 설명

1. 각 중복 그룹에서 보존 후보를 결정하는 순수 내부 정렬 키를 추가한다: 픽셀 면적(큰 것) → 파일 크기(큰 것) → 경로(사전순). 그 외 구성원은 중복 후보로 표시한다.
2. 공개 결과에 그룹 종류(exact/near), 구성원 지문/경로, 보존 후보를 담아 OCR 분류와 무관하게 UI·CLI가 나중에 소비할 수 있도록 문서화한다. 이번 이슈에서는 기존 CLI/UI 화면을 변경하지 않는다.
3. `README.md`에 탐지 API의 비파괴성, exact/near 기준, 보존 후보 tie-break 순서를 간단히 추가한다.
4. 테스트에 면적 우선, 동일 면적에서 바이트 크기 우선, 완전히 동률일 때 경로 사전순을 추가하고 전체 테스트를 실행한다.

완료 기준: 모든 그룹은 하나의 결정적 보존 후보를 가지며, API는 파일 이동·삭제·OCR 호출 없이 탐지만 수행한다.

## 검증 명령

```bash
python -m unittest tests/test_similarity.py
python -m py_compile engine.py
```

각 phase는 위 검증을 통과한 뒤 각각 `[P1]`, `[P2]`, `[P3]` 커밋으로 보존한다.
