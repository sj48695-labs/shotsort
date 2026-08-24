# shotsort

데스크탑에 쌓인 **스크린샷을 프로젝트별로 자동 분류**하고, **지워도 되는 것들을 묶어 한 번에 정리**하는 도구. 데스크탑 앱(GUI)과 CLI 둘 다 제공합니다.

기존 도구(czkawka·fclones 등)는 "중복/유사 이미지"는 잘 찾지만 "스크린샷 **내용**을 읽고 프로젝트별로 묶기"는 못 해서 직접 만들었습니다.

- 🖼 **OCR로 내용을 읽어** 비슷한 것끼리 그룹화 (macOS Vision, 무료·오프라인)
- 🤖 필요하면 **Claude·OpenAI·Grok API**로 더 정교하게 분류 (없어도 로컬 모드 동작)
- 🗑 지울 것들을 **체크해서 한 번에 휴지통으로** (macOS 휴지통 → 복구 가능)
- 🔄 새 버전이 나오면 **앱이 알리고 원클릭 업데이트**

---

## 🚀 설치

### 방법 1 — 앱 다운로드 (비개발자, 권장)

1. **[최신 릴리스에서 `shotsort.dmg` 다운로드](https://github.com/sj48695-labs/shotsort/releases/latest)**
2. `.dmg` 를 열고 **shotsort 를 Applications 폴더로 드래그**
3. **첫 실행만** — 서명 안 된 빌드라 macOS가 "악성 코드 확인 불가" 경고를 띄웁니다:
   - 경고창은 **완료**로 닫고 → **시스템 설정 → 개인정보 보호 및 보안** → 아래 *"'shotsort'…차단됨"* 옆 **"그래도 열기"** 클릭 → 다시 **"열기"**
   - 또는 터미널 한 줄: `xattr -dr com.apple.quarantine /Applications/shotsort.app`
   - 이후엔 그냥 더블클릭으로 실행됩니다.

API 키 없이 바로 동작합니다(무료 로컬 모드). 터미널·파이썬 설치 불필요.

> 완전 무경고 실행(일반 앱처럼)은 Apple Developer 서명·공증이 필요합니다 — [docs/SIGNING.md](docs/SIGNING.md) 참고.

### 방법 2 — 소스로 실행 (개발자)

**필요한 것**: macOS, `python3`, `git` (없으면 `brew install python git`)

```bash
git clone https://github.com/sj48695-labs/shotsort.git
cd shotsort && ./run.sh            # 앱 (최초 1회 의존성 자동 설치)
./run.sh --browser                # 앱을 브라우저로
./run.sh cli scan ~/Desktop       # CLI
./run.sh cli groups
```

> 💡 `export ANTHROPIC_API_KEY=sk-...` 후 실행하면 Claude가 더 정확히 묶어줍니다.
> 소스(git) 설치는 git 기반 자동 업데이트도 동작합니다.

### 처음 사용

데스크탑 앱 창이 뜨면:
1. **스캔** 버튼 (기본 경로 `~/Desktop`) → 스크린샷이 그룹별로 묶입니다
2. 지울 것들을 체크 → **선택 항목 휴지통으로** (복구 가능)

---

## 사용법

### 데스크탑 앱

`./run.sh` (또는 `python app.py`) 로 독립 창이 뜹니다.

- **경로 지정 → 스캔**: 실시간 진행률 표시, 결과는 그룹별 썸네일 격자로
- **자주 쓰는 프로젝트**: 프로젝트명과 별칭을 한 번 저장하면 이후 스캔에 자동 적용
- **그룹**: 기본 접힘(삭제후보·큰 그룹만 펼침), 크기순 정렬. 헤더의 `이 그룹 휴지통으로` 로 그룹 통째 정리
- **선택 삭제**: 카드 체크 → `선택 항목 휴지통으로` (확인 후 복구 가능한 휴지통으로)
- **분류 방식**: 로컬(외부 전송 없음) 또는 Claude·OpenAI·Grok API 선택
- **이미지 내용도 AI로 분석**: 끄면 OCR 텍스트만, 켜면 축소 이미지도 선택한 API로 전송

### CLI

```bash
./run.sh cli scan                      # ~/Desktop 분석 (캐시된 건 스킵)
./run.sh cli scan ~/Pictures --with-image
./run.sh cli scan --provider openai --model <모델명> --with-image
./run.sh cli scan --provider xai --model <모델명> --with-image
./run.sh cli groups                    # 프로젝트별 그룹
./run.sh cli projects add act-server --aliases "act server,github.com/acme/act-server"
./run.sh cli projects list             # 저장 프로젝트 확인
./run.sh cli groups --deletable        # 삭제 후보만
./run.sh cli trash --group "영수증"     # 그룹 통째 휴지통(확인 후)
./run.sh cli trash --deletable          # 삭제 후보 전부 휴지통
./run.sh cli open --group "act-server"  # Finder 에서 그룹 위치 보기
./run.sh cli stats                      # 통계
```

(`shotsort.py` 는 `cli.py` 의 하위호환 shim 이라 `python shotsort.py scan ...` 도 동일하게 동작합니다.)

---

## 동작 방식

1. **로컬 OCR** — macOS Vision 으로 이미지에서 텍스트 추출 (무료·오프라인, 한글/영문). 안 되면 tesseract → 그것도 없으면 건너뜀.
2. **분류** — 추출 텍스트(+선택적 축소 이미지)로 `project / kind / 요약 / 삭제가능` 태그 부여
   - **AI API**: Claude, OpenAI API, xAI Grok 중 선택. 모델명과 해당 API 키 필요
   - **로컬 모드**: 규칙 기반 종류 분류 + OCR 토큰 + 색상·밝기·화면 배치 유사도
3. **그룹 정규화** — 비슷한 것끼리 묶고 그룹명을 정리

분석 결과는 `~/.shotsort/cache.db` (SQLite)에 캐시 → 한 번 본 이미지는 재분석하지 않습니다(파일 해시 기준). `--force` 로 전체 재분석.

### 중복·유사 이미지 탐지 API

`engine.find_duplicate_groups(paths)`는 OCR·Claude 분류와 독립적으로 중복 후보만 **비파괴로 탐지**합니다. 파일을 이동·수정·삭제하지 않으며, UI와 CLI도 현재 이 API를 호출하지 않습니다.

- `exact` 그룹은 파일 전체 SHA-256이 같은 이미지입니다.
- `near` 그룹은 EXIF 방향을 정규화한 perceptual hash의 Hamming 거리가 임계값 이내이고, 그룹의 모든 구성원끼리도 이를 만족하는 이미지입니다.
- 반환된 각 그룹은 `kind`, 경로와 지문이 든 `members`, 그리고 하나의 `keeper`를 제공합니다. 보존 후보는 픽셀 면적이 큰 파일, 파일 크기가 큰 파일, 경로 사전순 순서로 결정되고 나머지는 `duplicate_candidates`입니다.
- `member_similarities`는 `members`와 같은 경로순의 `MemberSimilarity(member, distance, similarity_percent)` 튜플입니다. 모든 수치는 `keeper` 기준이며, `exact`는 모든 구성원이 거리 `0`·`100.0%`입니다. `near`는 같은 비트 폭의 pHash Hamming 거리를 백분율로 환산해 소수 둘째 자리로 반올림합니다. pHash는 시각적으로 비슷한 이미지를 찾는 휴리스틱이므로 오탐·미탐이 있을 수 있습니다.
- 반환값은 리스트처럼 그룹을 순회할 수 있는 `DuplicateDetectionResult`이며, 손상 파일·미지원 형식·읽기 실패는 검사 중단 없이 `errors`의 `SimilarityError(path, message)`로 개별 확인할 수 있습니다.

### 로컬 모드의 그룹핑 (API 키 없을 때)

OCR 휴리스틱만으로는 1장당 1그룹이 되기 쉬워, 그룹이 폭증하지 않도록 압축합니다:

- **신뢰 클러스터만** 프로젝트 그룹으로 유지 — 3장 이상 묶이고 이름이 깨끗할 때
- OCR 관계가 약하면 같은 종류와 유사한 화면 배치를 보조 신호로 사용
- 색상이 같다는 이유만으로는 합치지 않으며, 나머지는 **종류 버킷**으로 흡수
- 거의 빈 캡처는 `정리(삭제후보)` 그룹으로 모음

> 무료·오프라인이지만 정확도는 Claude 모드보다 낮습니다. 키를 설정하고 다시 스캔하면 자동으로 Claude 분류로 업그레이드됩니다. 키가 있어도 `--local` 로 로컬 강제 가능.

### 자주 쓰는 프로젝트와 그룹 우선순위

앱의 **프로젝트 관리**에서 `act-server`, `hitc`처럼 반복해서 분류하는 프로젝트를
저장할 수 있습니다. 별칭은 OCR 텍스트·요약·파일명에서 찾을 표현을 쉼표로
구분합니다. `주황색 대화방 형태` 같은 화면 특징도 함께 기록할 수 있으며,
Claude 모드에서 **썸네일도 전송**을 켰을 때 시각 분류 힌트로 사용됩니다.
활성 프로젝트 규칙은 현재 스캔한 파일에만 적용됩니다.

그룹은 **수동 이동/이름 변경 → 저장 프로젝트 → 자동 그룹화 → 종류 버킷** 순서로
결정됩니다. 한 번 직접 옮긴 이미지는 다음 스캔에서 자동 분류가 덮어쓰지 않습니다.

```bash
./run.sh cli projects add hitc --aliases "hitc,hitc-client"
./run.sh cli projects add act --characteristics "주황색 대화방 형태"
./run.sh cli projects disable hitc
./run.sh cli projects enable hitc
./run.sh cli projects remove hitc
```

---

## 자동 업데이트

**소스(git) 설치**: 앱을 열면 백그라운드로 원격과 비교해 새 버전이 있으면 **상단 배너**로 알리고, `업데이트` 버튼으로 `git pull` + 자동 재시작합니다.

**`.app` 설치**: 앱이 GitHub 릴리스의 최신 버전과 비교해 새 버전이 있으면 **상단 배너로 알리고**, `다운로드` 버튼으로 릴리스 페이지를 엽니다. 거기서 새 `.dmg` 를 받아 교체하면 됩니다. (앱 자체 교체는 무서명 제약상 다운로드 안내 방식)

---

## API 비용과 개인정보

로컬 모드는 외부 전송과 API 비용이 없습니다. AI API를 선택하면 기본적으로 OCR
텍스트가 해당 공급자에 전송되고, **이미지 내용도 AI로 분석**을 켠 경우에만 축소
이미지가 함께 전송됩니다. 모델별 비용·지원 기능은 각 공급자의 현재 문서를 확인하세요.
shotsort는 OpenAI·Grok 모델명을 임의로 고정하지 않으며 사용자가 직접 입력합니다.

---

## 안전장치

- 삭제는 전부 **macOS 휴지통**으로 이동(`Finder delete`) → 복구 가능, put-back 메타 유지
- 분석은 **읽기 전용** — 파일을 옮기거나 바꾸지 않음
- CLI `trash` 는 목록을 보여주고 **y/N 확인** (자동화는 `-y`), 앱도 확인 다이얼로그

---

## 프로젝트 구조

```
engine.py    # 핵심 로직 (OCR·분류·통합·캐시·휴지통·업데이트). print 없음
cli.py       # 커맨드라인 (argparse)
app.py       # 데스크탑 앱 (NiceGUI native 창)
shotsort.py  # 하위호환 shim (== cli.py)
run.sh       # 부트스트랩 실행기 (venv·의존성 자동 설치)
```

### 개발 모드

```bash
SHOTSORT_DEV=1 python app.py    # 파일 변경 시 자동 리로드 (브라우저로 실행)
```

---

## 한계 / TODO

- 중복/유사 이미지 제거는 범위 밖 — czkawka/fclones 와 함께 쓰면 좋음
- 로컬 모드는 OCR 품질에 좌우됨 — 정확한 프로젝트 그룹핑은 Claude 모드 권장
- (백로그) 종류 필터·검색, 잘못 묶인 항목 수동 재분류, 대량 가상 스크롤
