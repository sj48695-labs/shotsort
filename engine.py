#!/usr/bin/env python3
"""shotsort 엔진 — OCR·분류·통합·캐시·휴지통 로직 (UI/CLI 공통).

출력(print)은 포함하지 않는다. 진행 상황은 콜백으로, 결과는 반환값으로 넘긴다.
이렇게 분리해 두면 CLI(cli.py)와 GUI(app.py)가 같은 로직을 그대로 재사용한다.

하이브리드 분석:
  1) 로컬 OCR (macOS Vision, 무료/오프라인) 로 이미지에서 텍스트 추출
  2) Claude 가 그 텍스트(+선택적 썸네일)를 읽고 project/kind/요약/삭제가능 태그 부여
  3) 2차 통합 패스로 free-form 프로젝트 추정치를 정규화된 그룹으로 묶음
ANTHROPIC_API_KEY 가 없으면 2)·3)을 로컬 휴리스틱으로 대체(무료/오프라인).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re as _re
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import providers

HOME = Path.home()
STATE_DIR = HOME / ".shotsort"
DB_PATH = STATE_DIR / "cache.db"
DEFAULT_SCAN_DIR = HOME / "Desktop"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".heic", ".gif", ".webp", ".tiff", ".bmp"}

# 고용량 분류기 — 비용 민감하면 `--model claude-haiku-4-5` 권장.
DEFAULT_MODEL = "claude-opus-4-8"
CONSOLIDATE_MODEL = "claude-opus-4-8"

# 버전/배포 — 릴리스(.app) 자동 업데이트 비교용
VERSION = "0.1.1"
REPO_SLUG = "sj48695-labs/shotsort"

# 이미지 디코딩·정규화·해시 방식이 바뀌면 캐시를 안전하게 무효화한다.
FINGERPRINT_ALGORITHM_VERSION = 1


# ─────────────────────────────────────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────────────────────────────────────
def db(conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
    """OCR 캐시와 별도 지문 캐시 스키마를 준비한 연결을 반환한다.

    테스트나 호출자는 임시 SQLite 연결을 넘길 수 있어 사용자 캐시를 건드리지 않는다.
    """
    if conn is None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS images (
            path        TEXT PRIMARY KEY,
            sha         TEXT,
            mtime       REAL,
            size        INTEGER,
            ocr_text    TEXT,
            project     TEXT,   -- 1차 free-form 추정
            grp         TEXT,   -- 2차 정규화된 그룹명
            kind        TEXT,   -- code/ui/error/doc/chat/receipt/meme/photo/other
            summary     TEXT,
            deletable   INTEGER DEFAULT 0,
            confidence  REAL DEFAULT 0,
            analyzed_at REAL
        )
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(images)")}
    if "manual_group" not in columns:
        conn.execute("ALTER TABLE images ADD COLUMN manual_group INTEGER NOT NULL DEFAULT 0")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS saved_projects (
            name       TEXT PRIMARY KEY COLLATE NOCASE,
            aliases    TEXT NOT NULL DEFAULT '[]',
            characteristics TEXT NOT NULL DEFAULT '',
            enabled    INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    project_columns = {row[1] for row in conn.execute("PRAGMA table_info(saved_projects)")}
    if "characteristics" not in project_columns:
        conn.execute(
            "ALTER TABLE saved_projects ADD COLUMN characteristics TEXT NOT NULL DEFAULT ''"
        )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fingerprint_cache (
            path              TEXT PRIMARY KEY,
            mtime             INTEGER NOT NULL,
            size              INTEGER NOT NULL,
            algorithm_version INTEGER NOT NULL,
            sha256            TEXT NOT NULL,
            phash             TEXT
        )
        """
    )
    conn.commit()
    return conn


def _normalise_aliases(aliases: list[str] | str | None) -> list[str]:
    if isinstance(aliases, str):
        aliases = [aliases]
    seen: set[str] = set()
    result: list[str] = []
    for alias in aliases or []:
        value = alias.strip()
        folded = value.casefold()
        if value and folded not in seen:
            seen.add(folded)
            result.append(value)
    return result


def list_projects() -> list[dict]:
    """저장 프로젝트 목록. 이름 기준으로 안정적으로 정렬해 반환한다."""
    conn = db()
    rows = conn.execute(
        """SELECT name, aliases, characteristics, enabled
           FROM saved_projects ORDER BY name COLLATE NOCASE"""
    ).fetchall()
    return [
        {"name": row["name"], "aliases": json.loads(row["aliases"]),
         "characteristics": row["characteristics"],
         "enabled": bool(row["enabled"])}
        for row in rows
    ]


def save_project(
    name: str,
    aliases: list[str] | str | None,
    enabled: bool = True,
    characteristics: str = "",
) -> dict:
    """프로젝트 규칙을 추가하거나 같은 이름의 규칙을 갱신한다."""
    name = (name or "").strip()
    if not name:
        raise ValueError("프로젝트 이름은 비워 둘 수 없습니다")
    clean_aliases = _normalise_aliases(aliases)
    characteristics = (characteristics or "").strip()
    conn = db()
    conn.execute(
        """INSERT INTO saved_projects(name, aliases, characteristics, enabled) VALUES(?,?,?,?)
           ON CONFLICT(name) DO UPDATE SET aliases=excluded.aliases,
             characteristics=excluded.characteristics, enabled=excluded.enabled""",
        (name, json.dumps(clean_aliases, ensure_ascii=False), characteristics, int(enabled)),
    )
    conn.commit()
    return {"name": name, "aliases": clean_aliases,
            "characteristics": characteristics, "enabled": bool(enabled)}


def resolve_project_rules(
    conn: sqlite3.Connection | None = None, *, enabled_only: bool = True
) -> list[dict]:
    """분류기에 전달할 저장 프로젝트 규칙을 이름 순으로 반환한다."""
    conn = conn or db()
    where = "WHERE enabled=1" if enabled_only else ""
    rows = conn.execute(
        f"""SELECT name, aliases, characteristics, enabled FROM saved_projects
            {where} ORDER BY name COLLATE NOCASE"""
    ).fetchall()
    return [
        {"name": row["name"], "aliases": json.loads(row["aliases"]),
         "characteristics": row["characteristics"], "enabled": bool(row["enabled"])}
        for row in rows
    ]


def delete_project(name: str) -> int:
    conn = db()
    cur = conn.execute("DELETE FROM saved_projects WHERE name=?", ((name or "").strip(),))
    conn.commit()
    return cur.rowcount


def set_project_enabled(name: str, enabled: bool) -> int:
    conn = db()
    cur = conn.execute(
        "UPDATE saved_projects SET enabled=? WHERE name=?",
        (int(enabled), (name or "").strip()),
    )
    conn.commit()
    return cur.rowcount


def file_sha(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """파일 전체의 SHA-256을 고정 크기 청크로 계산한다."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class ImageFingerprint:
    """유사 이미지 탐지용, OCR과 독립된 파일 지문."""

    path: Path
    sha256: str
    phash: str | None


@dataclass(frozen=True)
class DuplicateGroup:
    """비파괴 중복 탐지 결과.

    ``kind``는 전체 SHA-256으로 검증한 ``"exact"`` 또는 perceptual hash로
    검증한 ``"near"``다. 구성원은 경로 기준으로 안정적으로 정렬된다.
    """

    kind: str
    members: tuple[ImageFingerprint, ...]


def _compute_image_fingerprint(path: Path) -> ImageFingerprint:
    """파일 SHA와 EXIF 방향 보정 perceptual hash를 새로 계산한다.

    손상 파일 등 Pillow 디코드 실패는 perceptual hash만 비워 두므로, 다른 파일의
    지문 수집을 중단시키지 않는다.
    """
    sha256 = file_sha(path)
    phash: str | None = None
    try:
        from PIL import Image, ImageOps
        import imagehash

        with Image.open(path) as image:
            normalized = ImageOps.exif_transpose(image)
            phash = str(imagehash.phash(normalized))
    except Exception:
        pass
    return ImageFingerprint(path=path, sha256=sha256, phash=phash)


def image_fingerprint(path: str | Path, *, conn: sqlite3.Connection | None = None) -> ImageFingerprint:
    """파일 지문을 반환하고, 동일한 메타데이터·알고리즘 버전에서는 캐시를 쓴다."""
    image_path = Path(path)
    st = image_path.stat()
    conn = db(conn)
    cache_key = str(image_path)
    row = conn.execute(
        "SELECT mtime, size, algorithm_version, sha256, phash FROM fingerprint_cache WHERE path=?",
        (cache_key,),
    ).fetchone()
    if (
        row
        and row["mtime"] == st.st_mtime_ns
        and row["size"] == st.st_size
        and row["algorithm_version"] == FINGERPRINT_ALGORITHM_VERSION
    ):
        return ImageFingerprint(image_path, row["sha256"], row["phash"])

    fingerprint = _compute_image_fingerprint(image_path)
    conn.execute(
        """INSERT INTO fingerprint_cache(path,mtime,size,algorithm_version,sha256,phash)
           VALUES(?,?,?,?,?,?)
           ON CONFLICT(path) DO UPDATE SET
             mtime=excluded.mtime, size=excluded.size,
             algorithm_version=excluded.algorithm_version, sha256=excluded.sha256,
             phash=excluded.phash""",
        (
            cache_key,
            st.st_mtime_ns,
            st.st_size,
            FINGERPRINT_ALGORITHM_VERSION,
            fingerprint.sha256,
            fingerprint.phash,
        ),
    )
    conn.commit()
    return fingerprint


def _phash_distance(first: str, second: str) -> int | None:
    """두 hexadecimal perceptual hash의 Hamming 거리를 안전하게 계산한다."""
    try:
        if len(first) != len(second):
            return None
        return (int(first, 16) ^ int(second, 16)).bit_count()
    except ValueError:
        return None


def find_duplicate_groups(
    paths: list[str | Path],
    *,
    hamming_threshold: int = 8,
    conn: sqlite3.Connection | None = None,
) -> list[DuplicateGroup]:
    """OCR·분류 DB와 독립적으로 exact/near 이미지 중복 그룹을 찾는다.

    정상적으로 perceptual hash를 계산하지 못한 파일과 이미지 확장자가 아닌 입력은
    안전하게 제외한다. Exact 그룹을 먼저 만들고, 나머지는 경로순 greedy
    complete-link로 묶는다. 따라서 near 그룹의 모든 두 구성원은 임계값 이내다.
    """
    if hamming_threshold < 0:
        raise ValueError("hamming_threshold must be non-negative")

    image_paths = sorted(
        {Path(path) for path in paths if Path(path).suffix.lower() in IMAGE_EXTS},
        key=lambda path: str(path),
    )
    fingerprints: list[ImageFingerprint] = []
    for path in image_paths:
        try:
            fingerprint = image_fingerprint(path, conn=conn)
        except OSError:
            continue
        # pHash가 없으면 Pillow가 파일을 이미지로 정상 디코드하지 못한 것이다.
        if fingerprint.phash is not None:
            fingerprints.append(fingerprint)

    by_sha: dict[str, list[ImageFingerprint]] = {}
    for fingerprint in fingerprints:
        by_sha.setdefault(fingerprint.sha256, []).append(fingerprint)

    exact_groups = [
        DuplicateGroup("exact", tuple(members))
        for _, members in sorted(by_sha.items())
        if len(members) > 1
    ]
    exact_paths = {member.path for group in exact_groups for member in group.members}
    near_candidates = [fingerprint for fingerprint in fingerprints if fingerprint.path not in exact_paths]

    near_clusters: list[list[ImageFingerprint]] = []
    for candidate in near_candidates:
        for cluster in near_clusters:
            distances = [_phash_distance(candidate.phash, member.phash) for member in cluster]
            if all(distance is not None and distance <= hamming_threshold for distance in distances):
                cluster.append(candidate)
                break
        else:
            near_clusters.append([candidate])

    near_groups = [
        DuplicateGroup("near", tuple(cluster))
        for cluster in near_clusters
        if len(cluster) > 1
    ]
    return exact_groups + near_groups


# ─────────────────────────────────────────────────────────────────────────────
# OCR  (macOS Vision → tesseract → 건너뜀)
# ─────────────────────────────────────────────────────────────────────────────
def ocr_macos_vision(path: Path) -> str | None:
    try:
        import Quartz
        import Vision
        from Foundation import NSURL
    except Exception:
        return None
    try:
        url = NSURL.fileURLWithPath_(str(path))
        src = Quartz.CGImageSourceCreateWithURL(url, None)
        if not src:
            return None
        img = Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)
        if not img:
            return None
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(1)  # 0=fast, 1=accurate
        req.setUsesLanguageCorrection_(True)
        try:
            req.setRecognitionLanguages_(["ko-KR", "en-US"])
        except Exception:
            pass
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
        ok = handler.performRequests_error_([req], None)
        if not ok:
            return None
        lines = []
        for r in req.results() or []:
            cand = r.topCandidates_(1)
            if cand and len(cand):
                lines.append(cand[0].string())
        return "\n".join(lines)
    except Exception:
        return None


def ocr_tesseract(path: Path) -> str | None:
    if not _which("tesseract"):
        return None
    try:
        out = subprocess.run(
            ["tesseract", str(path), "-", "-l", "kor+eng"],
            capture_output=True, text=True, timeout=60,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def ocr(path: Path) -> str:
    return (ocr_macos_vision(path) or ocr_tesseract(path) or "").strip()


def _which(cmd: str) -> str | None:
    from shutil import which
    return which(cmd)


# ─────────────────────────────────────────────────────────────────────────────
# Claude 분류
# ─────────────────────────────────────────────────────────────────────────────
PER_IMAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "project": {
            "type": "string",
            "description": "이 스크린샷이 속한 프로젝트/주제 추정 (예: 'act-server CI', '월세 영수증', 'React 디자인 참고'). 모르면 'unknown'.",
        },
        "kind": {
            "type": "string",
            "enum": ["code", "ui", "error", "doc", "chat", "receipt", "meme", "photo", "diagram", "other"],
        },
        "summary": {"type": "string", "description": "한 줄 요약 (한국어, 30자 내외)"},
        "deletable": {
            "type": "boolean",
            "description": "보관 가치가 낮아 지워도 될 가능성이 높으면 true (중복/일회성/흐릿함/맥락없는 캡처 등)",
        },
        "confidence": {"type": "number", "description": "0~1 분류 확신도"},
    },
    "required": ["project", "kind", "summary", "deletable", "confidence"],
    "additionalProperties": False,
}

PER_IMAGE_SYSTEM = (
    "너는 스크린샷 정리 도우미다. 주어진 OCR 텍스트(와 있으면 썸네일)를 보고 "
    "이 스크린샷이 어떤 프로젝트/주제에 속하는지, 어떤 종류인지, 보관 가치가 있는지 판단한다. "
    "project 는 나중에 비슷한 것끼리 묶을 수 있도록 구체적이되 일관된 이름으로 적어라."
)


def classify_image(
    client,
    model: str,
    ocr_text: str,
    image_path: Path,
    with_image: bool,
    project_rules: list[dict] | None = None,
) -> dict:
    content = []
    image_attached = False
    if with_image:
        img_b64, media = _downscaled_b64(image_path)
        if img_b64:
            content.append(
                {"type": "image", "source": {"type": "base64", "media_type": media, "data": img_b64}}
            )
            image_attached = True
    text = ocr_text.strip() or "(OCR 텍스트 없음 - 이미지/사진일 가능성)"
    prompt = f"파일명: {image_path.name}\n\nOCR 텍스트:\n{text[:6000]}"
    if project_rules:
        descriptions = []
        for rule in project_rules:
            aliases = ", ".join(rule.get("aliases") or []) or "없음"
            line = f'- {rule["name"]} (별칭: {aliases})'
            if image_attached and rule.get("characteristics"):
                line += f'; 이미지에서 확인할 특징: {rule["characteristics"]}'
            descriptions.append(line)
        prompt += ("\n\n저장된 프로젝트 후보입니다. 근거가 맞을 때 project를 정확한 "
                   "프로젝트명으로 반환하세요:\n" + "\n".join(descriptions))
    content.append({"type": "text", "text": prompt})

    resp = client.messages.create(
        model=model,
        max_tokens=600,
        system=PER_IMAGE_SYSTEM,
        messages=[{"role": "user", "content": content}],
        output_config={"format": {"type": "json_schema", "schema": PER_IMAGE_SCHEMA}},
    )
    out = next(b.text for b in resp.content if b.type == "text")
    return json.loads(out)


def classify_with_provider(
    adapter: providers.StructuredProvider,
    ocr_text: str,
    image_path: Path,
    with_image: bool,
    project_rules: list[dict] | None = None,
) -> dict:
    """공급자 공통 인터페이스로 한 이미지를 분류한다."""
    image_b64 = media = None
    if with_image:
        image_b64, media = _downscaled_b64(image_path)
    text = ocr_text.strip() or "(OCR 텍스트 없음 - 이미지/사진일 가능성)"
    prompt = f"파일명: {image_path.name}\n\nOCR 텍스트:\n{text[:6000]}"
    if project_rules:
        descriptions = []
        for rule in project_rules:
            aliases = ", ".join(rule.get("aliases") or []) or "없음"
            line = f'- {rule["name"]} (별칭: {aliases})'
            if image_b64 and rule.get("characteristics"):
                line += f'; 이미지에서 확인할 특징: {rule["characteristics"]}'
            descriptions.append(line)
        prompt += ("\n\n저장된 프로젝트 후보입니다. 근거가 맞을 때 project를 정확한 "
                   "프로젝트명으로 반환하세요:\n" + "\n".join(descriptions))
    return adapter.generate_json(
        system=PER_IMAGE_SYSTEM,
        prompt=prompt,
        schema=PER_IMAGE_SCHEMA,
        image_b64=image_b64,
        image_media_type=media or "image/jpeg",
        max_tokens=600,
    )


def _downscaled_b64(path: Path, max_edge: int = 1024):
    try:
        from PIL import Image
    except Exception:
        return None, None
    try:
        img = Image.open(path).convert("RGB")
        img.thumbnail((max_edge, max_edge))
        from io import BytesIO
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return base64.standard_b64encode(buf.getvalue()).decode(), "image/jpeg"
    except Exception:
        return None, None


_THUMB_CACHE: dict[str, tuple[float, str | None]] = {}


def thumbnail_uri(path: str | Path, max_edge: int = 320) -> str | None:
    """이미지 → data-URI 문자열(`data:image/jpeg;base64,...`). 파일 mtime 기준 캐시.

    GUI 가 매 렌더마다 호출하므로 같은(변경 안 된) 파일은 재인코딩하지 않는다.
    """
    p = Path(path)
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return None
    key = f"{p}|{max_edge}"
    hit = _THUMB_CACHE.get(key)
    if hit and hit[0] == mtime:
        return hit[1]
    b64, media = _downscaled_b64(p, max_edge=max_edge)
    uri = f"data:{media};base64,{b64}" if b64 else None
    _THUMB_CACHE[key] = (mtime, uri)
    return uri


CONSOLIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "group": {"type": "string", "description": "정규화된 그룹명"},
                },
                "required": ["id", "group"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["assignments"],
    "additionalProperties": False,
}


def consolidate_groups(
    client, items: list[dict], project_rules: list[dict] | None = None
) -> dict[int, str]:
    """free-form project 추정치들을 깔끔한 그룹명으로 정규화."""
    listing = "\n".join(
        f'{it["id"]}: project="{it["project"]}", kind={it["kind"]}, summary="{it["summary"]}"'
        for it in items
    )
    system = (
        "여러 스크린샷의 1차 분류 결과를 보고, 비슷한 것끼리 묶이도록 일관된 그룹명을 부여하라. "
        "거의 같은 주제는 같은 그룹명으로 통일하고, 지워도 될 잡다한 것들은 '정리(삭제후보)' 그룹으로 모아라. "
        "그룹 수는 너무 많지 않게(대략 4~12개) 의미 단위로 묶어라."
    )
    if project_rules:
        candidates = ", ".join(rule["name"] for rule in project_rules)
        system += f" 저장된 프로젝트 후보({candidates})와 일치하면 그 정확한 이름을 그룹명으로 사용하라."
    resp = client.messages.create(
        model=CONSOLIDATE_MODEL,
        max_tokens=4000,
        system=system,
        messages=[{"role": "user", "content": f"스크린샷 목록:\n{listing}"}],
        output_config={"format": {"type": "json_schema", "schema": CONSOLIDATE_SCHEMA}},
    )
    out = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(out)
    return {a["id"]: a["group"] for a in data["assignments"]}


def consolidate_with_provider(
    adapter: providers.StructuredProvider,
    items: list[dict],
    project_rules: list[dict] | None = None,
) -> dict[int, str]:
    listing = "\n".join(
        f'{it["id"]}: project="{it["project"]}", kind={it["kind"]}, summary="{it["summary"]}"'
        for it in items
    )
    system = (
        "여러 스크린샷의 1차 분류 결과를 보고 비슷한 것끼리 일관된 그룹명을 부여하라. "
        "잡다한 삭제 후보는 '정리(삭제후보)'로 모으고 그룹 수는 대략 4~12개로 유지하라."
    )
    if project_rules:
        system += " 저장된 프로젝트 후보와 맞으면 정확한 이름을 사용하라: " + ", ".join(
            rule["name"] for rule in project_rules
        )
    data = adapter.generate_json(
        system=system,
        prompt=f"스크린샷 목록:\n{listing}",
        schema=CONSOLIDATE_SCHEMA,
        max_tokens=4000,
    )
    return {a["id"]: a["group"] for a in data["assignments"]}


# ─────────────────────────────────────────────────────────────────────────────
# 로컬 폴백 (ANTHROPIC_API_KEY 없을 때) — OCR + 휴리스틱, Claude 미사용
#   무료·오프라인. 정확도는 LLM 모드보다 낮지만, OCR 텍스트 기반으로
#   종류 추정 + 토큰 겹침 클러스터링으로 "비슷한 것끼리" 묶어준다.
# ─────────────────────────────────────────────────────────────────────────────
_STOP = {
    "the", "and", "for", "you", "with", "this", "that", "from", "are", "was",
    "http", "https", "com", "www", "오전", "오후", "있습니다", "합니다", "그리고",
    "이미지", "screenshot", "스크린샷", "png", "jpg",
}

_KIND_RULES = [
    ("error",   _re.compile(r"\b(error|exception|traceback|stack ?trace|errno|failed|fatal)\b|에러|오류|실패|예외", _re.I)),
    ("receipt", _re.compile(r"영수증|결제|합계|부가세|invoice|receipt|total\s*[:：]|₩|\b\d[\d,]{2,}\s*원", _re.I)),
    ("code",    _re.compile(r"(def |function |import |const |class |=>|</[a-z]|};|public |private |#include|console\.)", _re.I)),
    ("chat",    _re.compile(r"kakaotalk|카카오톡|slack|discord|메시지|messages|보낸사람|받는사람|님\b", _re.I)),
    ("diagram", _re.compile(r"diagram|sequence|flowchart|아키텍처|architecture|mermaid", _re.I)),
]


def _tokens(text: str) -> set[str]:
    """클러스터링용 신호 토큰. 깨진 OCR 노이즈(짧은 라틴 조각·숫자)는 버린다."""
    ws = _re.findall(r"[a-z0-9가-힣]{2,}", (text or "").lower())
    out: set[str] = set()
    for w in ws:
        if w in _STOP or w.isdigit():
            continue
        if _re.search(r"[가-힣]", w):  # 한글 토큰은 2자 이상이면 신호로 인정
            out.add(w)
        elif len(w) >= 4 and sum(c.isalpha() for c in w) >= len(w) * 0.6:
            out.add(w)  # 라틴 토큰은 4자+ & 알파 비율 높을 때만(ef4·v7 같은 잡음 컷)
    return out


def _name_score(s: str) -> int:
    """그룹/프로젝트 이름 후보의 '깨끗함' 점수. 깨진 OCR 첫 줄을 피하려고 쓴다."""
    s = (s or "").strip()
    if not s:
        return -1
    letters = sum(1 for c in s if c.isalpha() or "가" <= c <= "힣")
    junk = sum(1 for c in s if not (c.isalnum() or c in " .-_/+:()"))
    return letters - junk * 2


def _looks_named(s: str) -> bool:
    """진짜 이름처럼 보이는가. 깨진 OCR(대문자 조각·자모깨짐)을 그룹명에서 거른다.

    실제 앱/창 제목엔 소문자 단어(devloop, hosting)나 한글 단어가 거의 있다.
    깨진 OCR 은 대문자 조각(AFAOFLI, EFAI)·단발 문자라 이 패턴이 없다.
    """
    return bool(_re.search(r"[a-z]{3,}", s or "") or _re.search(r"[가-힣]{2,}", s or ""))


def _visual_descriptor(path: str | Path) -> tuple[tuple[float, ...], float] | None:
    """작은 로컬 시각 특징: 3x3 밝기 배치와 주황색 픽셀 비율.

    얼굴/내용 인식이나 임베딩은 하지 않는다. Pillow가 없거나 파일을 읽지 못하면 OCR만
    사용하는 기존 동작으로 자연스럽게 폴백한다.
    """
    try:
        from PIL import Image, ImageStat
        image = Image.open(path).convert("RGB").resize((48, 48))
    except Exception:
        return None
    cells: list[float] = []
    for y in range(3):
        for x in range(3):
            box = (x * 16, y * 16, (x + 1) * 16, (y + 1) * 16)
            red, green, blue = ImageStat.Stat(image.crop(box)).mean
            cells.append((0.299 * red + 0.587 * green + 0.114 * blue) / 255)
    orange = 0
    get_pixels = getattr(image, "get_flattened_data", image.getdata)
    pixels = list(get_pixels())
    for red, green, blue in pixels:
        # 넓은 orange 범위. 갈색/회색은 채도와 채널 차이로 제외한다.
        if red >= 150 and 55 <= green <= 190 and blue <= 125 and red - blue >= 65:
            orange += 1
    return tuple(cells), orange / len(pixels)


def _visual_similarity(a: tuple[tuple[float, ...], float] | None,
                       b: tuple[tuple[float, ...], float] | None) -> float:
    """레이아웃 밝기 유사도. 색상 비율 자체는 그룹 병합 점수로 쓰지 않는다."""
    if not a or not b:
        return 0.0
    mean_error = sum(abs(x - y) for x, y in zip(a[0], b[0])) / len(a[0])
    return max(0.0, 1.0 - mean_error)


# 종류 → 싱글톤/미분류 흡수용 한국어 라벨
_KIND_LABEL = {
    "error": "에러", "receipt": "영수증", "code": "코드", "chat": "메시지",
    "diagram": "다이어그램", "doc": "문서", "ui": "화면", "photo": "사진", "other": "기타",
}
CLEANUP_GROUP = "정리(삭제후보)"
TEMPORAL_BOOST_SECONDS = 3 * 60
SESSION_GAP_SECONDS = 10 * 60
TEMPORAL_VISUAL_SIMILARITY = 0.88


def _capture_sessions(items: list[dict]) -> dict[int, float | None]:
    """mtime 순서에서 직전 캡처와 10분 초과로 벌어질 때 새 세션을 연다."""
    timed = sorted(
        (float(it["mtime"]), it["id"])
        for it in items if isinstance(it.get("mtime"), (int, float))
    )
    sessions: dict[int, float | None] = {it["id"]: None for it in items}
    start = previous = None
    for mtime, item_id in timed:
        if previous is None or mtime - previous > SESSION_GAP_SECONDS:
            start = mtime
        sessions[item_id] = start
        previous = mtime
    return sessions


def _trusted_group_name(name: str) -> bool:
    """URL, OCR 문장, 지나치게 긴/깨진 문자열을 프로젝트명에서 제외한다."""
    value = (name or "").strip()
    if not _looks_named(value) or len(value) > 30 or "\n" in value:
        return False
    if _re.search(r"(?:https?://|www\.|\.[a-z]{2,}/)", value, _re.I):
        return False
    # 자동 OCR 후보는 앱/프로젝트 식별자처럼 짧은 이름만 허용한다. 자연어 문장은
    # summary 신호로는 유용하지만 그룹 제목으로 쓰면 그룹 수가 급증한다.
    if len(value.split()) > 2:
        return False
    if "." in value:
        return False
    if sum(c.isdigit() for c in value) / len(value) > 0.2:
        return False
    letters = [c for c in value if c.isalpha()]
    if len(letters) >= 6 and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        return False
    useful = sum(c.isalnum() or c in " ._-/()" for c in value)
    return useful / len(value) >= 0.85


def classify_local(text: str, path: Path) -> dict:
    t = (text or "").strip()
    kind = "other"
    for name, rx in _KIND_RULES:
        if rx.search(t):
            kind = name
            break
    if kind == "other" and len(t) > 250:
        kind = "doc"
    elif kind == "other" and len(t) >= 5:
        kind = "ui"
    elif kind == "other":
        kind = "photo"

    # 프로젝트 추정: OCR 줄 중 가장 '깨끗한' 줄(앱/창 제목) → 없으면 대표 토큰
    project = "unknown"
    candidates = [ln.strip() for ln in t.splitlines() if len(ln.strip()) >= 3]
    best = max(candidates, key=_name_score, default="")
    if best and _name_score(best) > 0:
        project = best[:40]
    else:
        toks = list(_tokens(t))
        if toks:
            project = max(toks, key=len)

    deletable = len(t) < 5  # 거의 빈 캡처/오발사진은 삭제후보(보수적)
    summary = (t.replace("\n", " ")[:40] or path.stem)
    return {"project": project, "kind": kind, "summary": summary,
            "deletable": deletable, "confidence": 0.4}


def consolidate_local(items: list[dict]) -> dict[int, str]:
    """로컬 그룹핑.

    1) 삭제후보는 '정리(삭제후보)' 한 그룹으로.
    2) 나머지는 토큰 겹침(Jaccard) union-find 로 클러스터링. 3분 이내 연속
       캡처는 약한 텍스트 또는 화면 유사성이 있을 때만 병합을 보강한다.
    3) 2장+ 클러스터 → 대표 깨끗한 이름. 안 묶인 1장(싱글톤)은 '기타·{종류}' 버킷으로
       흡수 → 1장당 1그룹(미분류) 폭증을 막는다.
    """
    docs = []
    for it in items:
        blob = f"{it.get('project','')} {it.get('summary','')} {(it.get('ocr_text') or '')[:1500]}"
        docs.append((it["id"], _tokens(blob), it, _visual_descriptor(it.get("path", ""))))

    parent = {d[0]: d[0] for d in docs}
    sessions = _capture_sessions(items)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    deletables = {d[0] for d in docs if d[2].get("deletable")}

    n = len(docs)
    for i in range(n):
        if docs[i][0] in deletables or not docs[i][1]:
            continue
        ti = docs[i][1]
        for j in range(i + 1, n):
            if docs[j][0] in deletables or not docs[j][1]:
                continue
            tj = docs[j][1]
            left_session = sessions[docs[i][0]]
            right_session = sessions[docs[j][0]]
            # 시간이 있는 캡처는 세션 경계를 절대 넘겨 union하지 않는다. 시간이 없는
            # legacy 행끼리는 기존 텍스트/시각 그룹화를 그대로 유지한다.
            if left_session != right_session:
                continue
            inter = len(ti & tj)
            lexical = inter / len(ti | tj) if inter else 0.0
            # 시각 특징은 약한 텍스트 관계를 보강할 뿐이다. 공유 OCR 토큰이 없으면
            # 같은 주황색/밝기라는 이유만으로 합치지 않는다.
            visually_supported = (
                inter >= 1 and lexical >= 0.12
                and docs[i][2].get("kind") == docs[j][2].get("kind")
                and _visual_similarity(docs[i][3], docs[j][3]) >= 0.88
            )
            left_mtime = docs[i][2].get("mtime")
            right_mtime = docs[j][2].get("mtime")
            same_kind = docs[i][2].get("kind") == docs[j][2].get("kind")
            close_in_time = (
                isinstance(left_mtime, (int, float))
                and isinstance(right_mtime, (int, float))
                and abs(left_mtime - right_mtime) <= TEMPORAL_BOOST_SECONDS
            )
            weakly_related = inter >= 1 or (
                same_kind
                and _visual_similarity(docs[i][3], docs[j][3])
                >= TEMPORAL_VISUAL_SIMILARITY
            )
            temporally_supported = close_in_time and same_kind and weakly_related
            if lexical >= 0.3 or visually_supported or temporally_supported:
                parent[find(docs[i][0])] = find(docs[j][0])

    clusters: dict[int, list] = {}
    for did, toks, it, visual in docs:
        clusters.setdefault(find(did), []).append((did, toks, it, visual))

    def cluster_name(members: list) -> str:
        projects = [m[2].get("project", "") for m in members
                    if m[2].get("project") and m[2]["project"] != "unknown"]
        if projects:
            return (max(projects, key=_name_score)[:30]) or "기타"
        tok_counter: Counter = Counter()
        for _, toks, _it, _visual in members:
            tok_counter.update(toks)
        return tok_counter.most_common(1)[0][0] if tok_counter else "기타"

    # 신뢰 클러스터만 프로젝트 그룹으로 남긴다(3장+ & 이름이 깨끗할 때).
    # 그 외(작은/깨진 클러스터·싱글톤)는 모두 종류 버킷(문서/화면/에러…)으로 흡수해
    # 그룹 수가 폭증하지 않게 한다. 로컬 휴리스틱의 한계를 종류 분류로 보완.
    CONFIDENT_MIN = 3
    mapping: dict[int, str] = {}
    for members in clusters.values():
        ids = [m[0] for m in members]
        if all(i in deletables for i in ids):
            for i in ids:
                mapping[i] = CLEANUP_GROUP
            continue
        name = cluster_name(members)
        if len(members) >= CONFIDENT_MIN and _trusted_group_name(name):
            for i in ids:
                mapping[i] = name[:30]
        else:
            for did, _toks, it, _visual in members:
                mapping[did] = _KIND_LABEL.get(it.get("kind"), "기타")
    return mapping


# ─────────────────────────────────────────────────────────────────────────────
# 키/클라이언트
# ─────────────────────────────────────────────────────────────────────────────
def has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def resolve_mode(local: bool = False) -> bool:
    """분석 모드 결정의 단일 출처. True=Claude(LLM), False=로컬 휴리스틱.

    `local=True`(강제)거나 API 키가 없으면 로컬 모드. CLI·GUI 가 동일하게 이걸 쓴다.
    """
    return (not local) and has_api_key()


def human_mb(nbytes: int) -> str:
    return f"{nbytes / 1_048_576:.1f} MB"


def get_client():
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic SDK 가 필요합니다:  pip install -r requirements.txt")
    return anthropic.Anthropic()


def find_images(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in IMAGE_EXTS else []
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


# ─────────────────────────────────────────────────────────────────────────────
# 고수준 동작 (UI/CLI 공통) — print 없음, 콜백/반환값으로 소통
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class ScanResult:
    total: int = 0
    new: int = 0
    skipped: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)  # (filename, message)
    consolidate_error: str | None = None
    used_llm: bool = False


# on_item(i, total, path: Path, tag: dict | None, error: Exception | None)
ItemCallback = Callable[[int, int, Path, "dict | None", "Exception | None"], None]


def scan_images(
    root: Path,
    *,
    use_llm: bool | None = None,
    provider: str | None = None,
    model: str | None = None,
    with_image: bool = False,
    force: bool = False,
    consolidate: bool = True,
    project_hints: list[str] | None = None,
    on_item: ItemCallback | None = None,
) -> ScanResult:
    """이미지를 분석해 DB 에 저장하고(캐시되지 않은 것만), 2차 그룹 정규화까지 수행."""
    if provider is None:
        provider = "anthropic" if use_llm else "local"
    # 기존 Claude 호출은 모델 기본값을 유지하고, 다른 공급자는 명시 선택을 요구한다.
    selected_model = model or (DEFAULT_MODEL if provider in {"anthropic", "claude"} else None)
    config = providers.resolve_config(provider, selected_model)
    adapter = providers.create_provider(config)
    remote = adapter is not None
    res = ScanResult(used_llm=remote)
    imgs = find_images(root)
    res.total = len(imgs)
    if not imgs:
        return res

    conn = db()
    project_rules = resolve_project_rules(conn) if remote else []

    for i, path in enumerate(imgs, 1):
        sp = str(path)
        try:
            sha = file_sha(path)
        except OSError:
            continue
        row = conn.execute("SELECT sha FROM images WHERE path=?", (sp,)).fetchone()
        if row and row["sha"] == sha and not force:
            res.skipped += 1
            continue

        text = ocr(path)
        try:
            tag = (classify_with_provider(adapter, text, path, with_image, project_rules)
                   if adapter else classify_local(text, path))
        except Exception as e:
            res.errors.append((path.name, str(e)))
            if on_item:
                on_item(i, res.total, path, None, e)
            continue

        st = path.stat()
        conn.execute(
            """INSERT INTO images(path,sha,mtime,size,ocr_text,project,kind,summary,deletable,confidence,analyzed_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,strftime('%s','now'))
               ON CONFLICT(path) DO UPDATE SET
                 sha=excluded.sha, mtime=excluded.mtime, size=excluded.size, ocr_text=excluded.ocr_text,
                 project=excluded.project, kind=excluded.kind, summary=excluded.summary,
                 deletable=excluded.deletable, confidence=excluded.confidence, analyzed_at=excluded.analyzed_at""",
            (sp, sha, st.st_mtime, st.st_size, text, tag["project"], tag["kind"],
             tag["summary"], int(tag["deletable"]), float(tag["confidence"])),
        )
        conn.commit()
        res.new += 1
        if on_item:
            on_item(i, res.total, path, tag, None)

    if consolidate:
        try:
            consolidate_all(
                conn=conn, use_llm=remote, provider_adapter=adapter,
                project_hints=project_hints, paths=imgs
            )
        except Exception as e:
            res.consolidate_error = str(e)
    return res


def consolidate_all(
    conn: sqlite3.Connection | None = None,
    *,
    use_llm: bool,
    provider_adapter: providers.StructuredProvider | None = None,
    project_hints: list[str] | None = None,
    paths: list[str | Path] | None = None,
    root: str | Path | None = None,
) -> int:
    """선택 범위를 2차 그룹 정규화. 수동 그룹은 절대 덮어쓰지 않는다."""
    conn = conn or db()
    rows = conn.execute(
        """SELECT rowid AS id, path, mtime, project, kind, summary, ocr_text, deletable
           FROM images WHERE COALESCE(manual_group, 0)=0"""
    ).fetchall()
    rows = [r for r in rows if _path_in_scope(r["path"], paths=paths, root=root)]
    if not rows:
        return 0
    items = [dict(r) for r in rows]
    project_rules = resolve_project_rules(conn) if use_llm else []
    if provider_adapter:
        mapping = consolidate_with_provider(provider_adapter, items, project_rules)
    elif use_llm:  # 기존 직접 호출 호환
        mapping = consolidate_groups(get_client(), items, project_rules)
    else:
        mapping = consolidate_local(items)
    for rid, grp in mapping.items():
        conn.execute("UPDATE images SET grp=? WHERE rowid=?", (grp, rid))
    conn.commit()
    if project_hints:
        apply_project_hints(project_hints, conn=conn, paths=paths, root=root)
    apply_saved_projects(conn=conn, paths=paths, root=root)
    return len(mapping)


def apply_project_hints(
    hints: list[str], conn: sqlite3.Connection | None = None, *,
    paths: list[str | Path] | None = None,
    root: str | Path | None = None,
) -> int:
    """알려진 프로젝트명 힌트로 그룹을 덮어쓴다(로컬·Claude 공통 후처리).

    OCR 텍스트·1차 project·요약 어디든 힌트 단어가 (토큰 경계로) 나오면, 해당
    이미지의 grp 를 그 힌트로 강제한다. 로컬 OCR 휴리스틱이 못 묶는 act-server·hitc
    같은 프로젝트를 결정적으로 모아 준다. 반환: 재배치된 행 수.
    """
    cleaned = [h.strip() for h in hints if h and h.strip()]
    if not cleaned:
        return 0
    # 긴 힌트 우선(겹칠 때 더 구체적인 이름으로). 토큰 경계 매칭(하이픈은 단어 일부로 취급).
    patterns = [
        (h, _re.compile(rf"(?<![\w-]){_re.escape(h)}(?![\w-])", _re.I))
        for h in sorted(cleaned, key=len, reverse=True)
    ]
    conn = conn or db()
    rows = conn.execute(
        """SELECT rowid AS id, path, project, summary, ocr_text FROM images
           WHERE COALESCE(manual_group, 0)=0"""
    ).fetchall()
    moved = 0
    for r in rows:
        if not _path_in_scope(r["path"], paths=paths, root=root):
            continue
        blob = f"{Path(r['path']).name}\n{r['project'] or ''}\n{r['summary'] or ''}\n{r['ocr_text'] or ''}"
        for name, rx in patterns:
            if rx.search(blob):
                conn.execute("UPDATE images SET grp=? WHERE rowid=?", (name, r["id"]))
                moved += 1
                break
    conn.commit()
    return moved


def _path_in_scope(
    path: str | Path, *, paths: list[str | Path] | None, root: str | Path | None
) -> bool:
    """범위가 없으면 전체, paths/root가 있으면 둘 중 하나에 포함될 때만 참."""
    if paths is None and root is None:
        return True
    candidate = Path(path).expanduser().resolve()
    if paths is not None:
        allowed = {Path(p).expanduser().resolve() for p in paths}
        if candidate in allowed:
            return True
    if root is not None:
        scope = Path(root).expanduser().resolve()
        if candidate == scope:
            return True
        try:
            candidate.relative_to(scope)
            return True
        except ValueError:
            pass
    return False


def apply_saved_projects(
    conn: sqlite3.Connection | None = None, *,
    paths: list[str | Path] | None = None,
    root: str | Path | None = None,
) -> int:
    """활성 저장 프로젝트(이름+별칭)를 해당 범위의 자동 그룹에 적용한다."""
    conn = conn or db()
    rows = conn.execute(
        "SELECT name, aliases, characteristics FROM saved_projects WHERE enabled=1"
    ).fetchall()
    rules: list[tuple[str, str]] = []
    for row in rows:
        aliases = json.loads(row["aliases"])
        # 짧은 영문 프로젝트명(예: act)은 일반 문장에 너무 자주 등장한다.
        # 이름 자체는 4자 이상일 때만 텍스트 규칙으로 쓰고, 짧은 이름은 구체적 별칭/시각 특징으로 판별한다.
        name = row["name"]
        name_is_specific = bool(_re.search(r"[가-힣]{2,}", name) or len(name) >= 4)
        terms = ([name] if name_is_specific else []) + aliases
        rules.extend((name, term) for term in terms if term)
    rules.sort(key=lambda rule: len(rule[1]), reverse=True)
    patterns = [
        # 파일명의 '-'도 자연스러운 단어 구분자로 취급하되 영숫자 내부는 매칭하지 않는다.
        (name, _re.compile(rf"(?<!\w){_re.escape(term)}(?!\w)", _re.I))
        for name, term in rules
    ]
    characteristic_rules = [
        (row["name"], row["characteristics"].casefold())
        for row in rows if (row["characteristics"] or "").strip()
    ]
    image_rows = conn.execute(
        """SELECT rowid AS id, path, project, kind, summary, ocr_text FROM images
           WHERE COALESCE(manual_group, 0)=0"""
    ).fetchall()
    moved = 0
    for row in image_rows:
        if not _path_in_scope(row["path"], paths=paths, root=root):
            continue
        blob = (f"{Path(row['path']).name}\n{row['project'] or ''}\n"
                f"{row['summary'] or ''}\n{row['ocr_text'] or ''}")
        for name, rx in patterns:
            if rx.search(blob):
                conn.execute("UPDATE images SET grp=? WHERE rowid=?", (name, row["id"]))
                moved += 1
                break
        else:
            descriptor = _visual_descriptor(row["path"])
            for name, characteristic in characteristic_rules:
                # 현재 지원하는 보수적 로컬 해석: '주황색' + '대화/대화방' 규칙.
                # 색상만으로는 절대 매칭하지 않고 OCR로 판별된 chat 종류가 함께 필요하다.
                orange_chat = (
                    "주황" in characteristic
                    and ("대화" in characteristic or "채팅" in characteristic)
                    and row["kind"] == "chat"
                    and descriptor is not None and descriptor[1] >= 0.18
                )
                if orange_chat:
                    conn.execute("UPDATE images SET grp=? WHERE rowid=?", (name, row["id"]))
                    moved += 1
                    break
    conn.commit()
    return moved


def list_groups(deletable: bool = False) -> "OrderedDict[str, list[dict]]":
    """그룹명 → 이미지 행 리스트(dict). 행에는 path/summary/kind/deletable/project/grp 포함."""
    conn = db()
    where = "WHERE deletable=1" if deletable else ""
    rows = conn.execute(
        f"SELECT COALESCE(grp, project) AS g, path, summary, kind, deletable, project, grp, size "
        f"FROM images {where} ORDER BY g, deletable DESC, path"
    ).fetchall()
    groups: "OrderedDict[str, list[dict]]" = OrderedDict()
    for r in rows:
        groups.setdefault(r["g"], []).append(dict(r))

    # 정렬: '정리(삭제후보)' 최상단 → 큰 그룹 → 이름. 큰/유용한 그룹이 먼저 보이게.
    def key(item):
        name, its = item
        return (0 if name == CLEANUP_GROUP else 1, -len(its), name)

    return OrderedDict(sorted(groups.items(), key=key))


def collect_paths(group: str | None, deletable: bool) -> list[str]:
    """그룹명 또는 삭제후보에 해당하는, 실제 존재하는 파일 경로들."""
    conn = db()
    if deletable:
        rows = conn.execute("SELECT path FROM images WHERE deletable=1").fetchall()
    elif group:
        rows = conn.execute(
            "SELECT path FROM images WHERE COALESCE(grp, project)=?", (group,)
        ).fetchall()
    else:
        return []
    return [r["path"] for r in rows if Path(r["path"]).exists()]


def move_to_trash(paths: list[str]) -> bool:
    """macOS 휴지통으로 이동(복구 가능). Finder 의 put-back 메타 유지."""
    if not paths:
        return True
    posix = ", ".join('POSIX file "%s"' % p.replace('"', '\\"') for p in paths)
    script = f'tell application "Finder" to delete {{{posix}}}'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"휴지통 이동 실패: {e.stderr}")


def forget_paths(paths: list[str]) -> None:
    """DB 에서 해당 경로 행 제거(파일을 휴지통으로 보낸 뒤 호출)."""
    if not paths:
        return
    conn = db()
    conn.executemany("DELETE FROM images WHERE path=?", [(p,) for p in paths])
    conn.commit()


def trash(paths: list[str]) -> int:
    """주어진 경로들을 휴지통으로 보내고 DB 에서 제거. 반환: 처리한 개수."""
    if not paths:
        return 0
    move_to_trash(paths)
    forget_paths(paths)
    return len(paths)


# ─────────────────────────────────────────────────────────────────────────────
# 그룹 정리 동작 — 폴더로 이동 / zip 압축 / Finder 에서 보기 (전부 비파괴적)
# ─────────────────────────────────────────────────────────────────────────────
def safe_dirname(name: str) -> str:
    """그룹명을 폴더/파일명으로 안전하게. 경로 구분자·제어문자를 _ 로."""
    s = _re.sub(r'[/\\:*?"<>|\x00-\x1f]', "_", (name or "").strip())
    s = s.strip(". ") or "untitled"
    return s[:80]


def _unique_dest(dest_dir: Path, name: str) -> Path:
    """대상 폴더에서 이름 충돌 시 ' (2)', ' (3)' … 를 붙여 비충돌 경로를 만든다."""
    cand = dest_dir / name
    if not cand.exists():
        return cand
    stem, suffix = Path(name).stem, Path(name).suffix
    i = 2
    while True:
        cand = dest_dir / f"{stem} ({i}){suffix}"
        if not cand.exists():
            return cand
        i += 1


def default_export_root(scan_root: Path | str) -> Path:
    """기본 내보내기 루트: <스캔 디렉토리>/_shotsort. 스캔 대상이 파일이면 그 부모 기준."""
    p = Path(scan_root).expanduser()
    base = p if p.is_dir() else p.parent
    return base / "_shotsort"


def move_paths(paths: list[str], dest_dir: Path) -> int:
    """파일들을 dest_dir 로 이동하고 DB 의 path 를 새 위치로 갱신. 반환: 이동 개수."""
    dest_dir = Path(dest_dir).expanduser()
    dest_dir.mkdir(parents=True, exist_ok=True)
    conn = db()
    moved = 0
    for sp in paths:
        src = Path(sp)
        if not src.exists():
            continue
        target = _unique_dest(dest_dir, src.name)
        if target.resolve() == src.resolve():
            continue
        shutil.move(str(src), str(target))
        conn.execute("UPDATE images SET path=? WHERE path=?", (str(target), sp))
        moved += 1
    conn.commit()
    return moved


def move_group(
    group: str | None, dest_root: Path | str, *, deletable: bool = False
) -> tuple[int, Path]:
    """그룹(또는 삭제후보) 멤버를 dest_root/<그룹명>/ 으로 이동. 반환: (개수, 대상 폴더)."""
    paths = collect_paths(group, deletable)
    folder = "정리(삭제후보)" if deletable else (group or "untitled")
    dest_dir = Path(dest_root).expanduser() / safe_dirname(folder)
    n = move_paths(paths, dest_dir)
    return n, dest_dir


def zip_group(
    group: str | None, out_path: Path | str | None = None, *, deletable: bool = False
) -> tuple[int, Path]:
    """그룹 멤버를 zip 으로 압축(원본 유지). 반환: (압축한 개수, zip 경로)."""
    paths = collect_paths(group, deletable)
    name = "정리(삭제후보)" if deletable else (group or "untitled")
    if out_path is None:
        out_path = default_export_root(Path(paths[0]).parent if paths else HOME) / f"{safe_dirname(name)}.zip"
    out_path = Path(out_path).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path = _unique_dest(out_path.parent, out_path.name)
    written = 0
    used: set[str] = set()
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for sp in paths:
            src = Path(sp)
            if not src.exists():
                continue
            arc = src.name
            i = 2
            while arc in used:  # 다른 폴더의 동명 파일 충돌 방지
                arc = f"{src.stem} ({i}){src.suffix}"
                i += 1
            used.add(arc)
            zf.write(src, arc)
            written += 1
    return written, out_path


def rename_group(old: str, new: str) -> int:
    """그룹 이름 변경. 해당 그룹의 모든 이미지 grp 를 new 로 설정. 반환: 변경된 행 수.

    list_groups 는 `COALESCE(grp, project)` 로 그룹키를 만들므로, grp 가 비어 있어
    project 가 그룹명이던 경우도 grp=new 로 채워 새 이름으로 묶인다.
    이름을 바꿔 두면 '폴더로 이동'·'정리' 시 그 이름으로 폴더가 생성된다.
    """
    new = (new or "").strip()
    if not new or new == old:
        return 0
    conn = db()
    cur = conn.execute(
        """UPDATE images SET grp=?, manual_group=1
           WHERE COALESCE(grp, project)=?""", (new, old)
    )
    conn.commit()
    return cur.rowcount


def move_images_to_group(paths: list[str], group: str) -> int:
    """이미지 여러 개를 다른 그룹으로 재배치(grp 변경). 드래그 앤 드롭 수동 재분류용.

    선택한 카드들을 한꺼번에 끌어다 놓을 때 쓴다. 반환: 재배치된 행 수.
    """
    group = (group or "").strip()
    if not group or not paths:
        return 0
    conn = db()
    before = conn.total_changes
    conn.executemany(
        "UPDATE images SET grp=?, manual_group=1 WHERE path=?", [(group, p) for p in paths]
    )
    conn.commit()
    return conn.total_changes - before


def reveal_in_finder(path: str | Path) -> None:
    """Finder 에서 해당 파일을 선택해 보여 준다(open -R)."""
    p = Path(path)
    if not p.exists():
        raise RuntimeError(f"파일 없음: {p}")
    subprocess.run(["open", "-R", str(p)], check=True)


@dataclass
class Stats:
    total: int = 0
    groups: int = 0
    deletable: int = 0
    deletable_bytes: int = 0


def stats() -> Stats:
    conn = db()
    total = conn.execute("SELECT COUNT(*) c FROM images").fetchone()["c"]
    if not total:
        return Stats()
    dele = conn.execute("SELECT COUNT(*) c FROM images WHERE deletable=1").fetchone()["c"]
    size = conn.execute("SELECT COALESCE(SUM(size),0) s FROM images WHERE deletable=1").fetchone()["s"]
    ngroups = conn.execute(
        "SELECT COUNT(DISTINCT COALESCE(grp,project)) c FROM images"
    ).fetchone()["c"]
    return Stats(total=total, groups=ngroups, deletable=dele, deletable_bytes=size)


# ─────────────────────────────────────────────────────────────────────────────
# 자동 업데이트 (git 기반) — 앱이 원격과 비교해 뒤처지면 알림, 원클릭 pull
# ─────────────────────────────────────────────────────────────────────────────
def repo_dir() -> Path:
    return Path(__file__).resolve().parent


def _git(*args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_dir()), *args], capture_output=True, text=True
        )
    except (FileNotFoundError, OSError) as e:
        return 1, str(e)  # git 미설치(.app 번들 등) → 호출부가 error 로 처리
    return r.returncode, (r.stdout + r.stderr).strip()


@dataclass
class UpdateStatus:
    available: bool = False
    mode: str = "none"        # "git" | "release" | "none"
    behind: int = 0           # git 모드: 원격이 로컬보다 앞선 커밋 수
    latest: str | None = None  # release 모드: 최신 버전(tag)
    url: str | None = None     # release 모드: 다운로드 페이지
    error: str | None = None


def _ver_tuple(s: str) -> tuple:
    out = []
    for p in (s or "").split("."):
        n = "".join(c for c in p if c.isdigit())
        out.append(int(n) if n else 0)
    return tuple(out) or (0,)


def check_update(fetch: bool = True) -> UpdateStatus:
    """업데이트 확인. git 저장소면 원격 커밋 비교, 아니면(.app 번들) GitHub 릴리스 비교."""
    if _git("rev-parse", "--is-inside-work-tree")[0] == 0:
        return _check_update_git(fetch)
    return _check_update_release()


def _check_update_git(fetch: bool) -> UpdateStatus:
    if fetch:
        code, out = _git("fetch", "--quiet")
        if code != 0:
            return UpdateStatus(mode="git", error=f"fetch 실패: {out[:200]}")
    code, up = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if code != 0:
        return UpdateStatus(mode="git", error="upstream(원격 추적 브랜치) 없음")
    code, out = _git("rev-list", "--count", f"HEAD..{up}")
    if code != 0:
        return UpdateStatus(mode="git", error=out[:200])
    behind = int(out or "0")
    return UpdateStatus(available=behind > 0, mode="git", behind=behind)


def _check_update_release() -> UpdateStatus:
    """GitHub 최신 릴리스 tag 와 VERSION 비교(.app 번들용). 공개 API라 인증 불필요."""
    import json
    import ssl
    import urllib.request

    try:  # 시스템 CA 미설정 대비 certifi 번들 사용
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx = ssl.create_default_context()

    url = f"https://api.github.com/repos/{REPO_SLUG}/releases/latest"
    try:
        req = urllib.request.Request(
            url, headers={"Accept": "application/vnd.github+json", "User-Agent": "shotsort"}
        )
        with urllib.request.urlopen(req, timeout=8, context=ctx) as r:
            data = json.load(r)
    except Exception as e:
        return UpdateStatus(mode="release", error=str(e)[:200])
    tag = (data.get("tag_name") or "").lstrip("v")
    if not tag:
        return UpdateStatus(mode="release", error="릴리스를 찾을 수 없음")
    newer = _ver_tuple(tag) > _ver_tuple(VERSION)
    return UpdateStatus(
        available=newer, mode="release", latest=tag,
        url=data.get("html_url") or f"https://github.com/{REPO_SLUG}/releases/latest",
    )


def apply_update() -> tuple[bool, str]:
    """git 모드: fast-forward pull 로 최신 코드를 받는다. 적용 후 재시작 필요.

    release(.app) 모드는 자체 교체 대신 다운로드 페이지(UpdateStatus.url)를 연다 — app.py 참고.
    """
    code, out = _git("pull", "--ff-only")
    return code == 0, out[:300]
