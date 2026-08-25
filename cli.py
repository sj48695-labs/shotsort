#!/usr/bin/env python3
"""shotsort CLI — engine.py 로직을 감싸는 얇은 커맨드라인 래퍼.

사용 예:
  shotsort scan ~/Desktop          # 분석 (캐시되지 않은 것만)
  shotsort groups                  # 프로젝트별 그룹 보기
  shotsort groups --deletable      # 삭제 후보만 보기
  shotsort similarity ~/Desktop    # 중복·유사 이미지 검사
  shotsort trash --group "영수증"   # 그룹 통째로 휴지통(확인 후)
  shotsort trash --deletable       # 삭제 후보 전부 휴지통(확인 후)
  shotsort open --group "act-server"  # Finder 에서 그룹 파일 보기
  shotsort stats                   # 통계
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import engine
import providers
from engine import DEFAULT_MODEL, DEFAULT_SCAN_DIR


def cmd_scan(args):
    root = Path(args.path).expanduser()
    if not root.exists():
        sys.exit(f"경로 없음: {root}")

    requested = "local" if args.local else (args.provider or "auto")
    legacy_provider = requested if requested in {"anthropic", "openai", "xai"} else None
    selected_provider = legacy_provider or args.direct_provider
    if not selected_provider:
        env_provider = os.environ.get("SHOTSORT_AI_PROVIDER", "").strip().lower()
        selected_provider = env_provider if env_provider in {"anthropic", "openai", "xai"} else "anthropic"
    mode = "direct" if legacy_provider else requested
    if mode == "local":
        selected_provider = "local"

    # The flag is intentionally required for each non-interactive API execution.
    # Saving the scoped preference makes the user's affirmative choice inspectable
    # in the app, but an old saved value must never silently authorize this CLI run.
    api_consent = bool(args.allow_api_transfer)
    if api_consent and mode in {"api", "direct"}:
        engine.set_api_consent(selected_provider, with_image=args.with_image, allowed=True)

    print(f"분석 시작: requested_mode={mode}")
    if mode in {"api", "direct"} and not api_consent:
        print("API 후보는 감지되더라도 --allow-api-transfer 없이는 실행하지 않고 로컬 분석으로 fallback 합니다.")

    printed = False

    def on_item(i, total, path, tag, error):
        nonlocal printed
        if not printed:
            print(f"이미지 {total}개 발견. 분석 중...")
            printed = True
        if error is not None:
            print(f"  [{i}/{total}] 분류 실패 {path.name}: {providers.mask_secret(error)}", file=sys.stderr)
            return
        mark = "  🗑 삭제후보" if tag["deletable"] else ""
        print(f"  [{i}/{total}] {path.name} → {tag['project']} ({tag['kind']}){mark}")

    hints = [h for h in (args.projects or "").split(",") if h.strip()]
    res = engine.scan_images(
        root,
        provider=selected_provider,
        model=args.model,
        with_image=args.with_image,
        analysis_mode=mode,
        api_consent=api_consent,
        force=args.force,
        project_hints=hints,
        on_item=on_item,
    )

    if res.total == 0:
        _print_execution_status("실행 결과", res)
        print("이미지를 찾지 못했습니다.")
        return
    if not printed:
        print(f"이미지 {res.total}개 발견. 분석 중...")

    _print_execution_status("실행 결과", res)
    print(f"분석 완료: 신규 {res.new}개, 캐시 스킵 {res.skipped}개")
    if res.consolidate_error:
        print(f"그룹 정규화 실패(개별 분류는 저장됨): {providers.mask_secret(res.consolidate_error)}", file=sys.stderr)
    else:
        print("완료. `shotsort groups` 로 확인하세요.")


def _print_execution_status(label, result) -> None:
    """Print only the execution facts that are safe and actionable in a terminal."""
    method = getattr(result.actual_method, "value", result.actual_method)
    catalog_cache = bool(getattr(result, "catalog_from_cache",
                                 getattr(result, "model_catalog_from_cache", False)))
    fields = [
        f"provider={providers.mask_secret(result.actual_provider)}",
        f"method={providers.mask_secret(method)}",
        f"model={providers.mask_secret(result.actual_model) if result.actual_model else 'auto'}",
        f"external_transfer={'yes' if result.external_transfer else 'no'}",
        f"catalog={'cache' if catalog_cache else 'fresh'}",
    ]
    reason = getattr(result, "fallback_reason", None)
    if reason:
        fields.append(f"fallback={providers.mask_secret(reason)}")
    print(f"{label}: " + " · ".join(fields))


def cmd_groups(args):
    groups = engine.list_groups(deletable=args.deletable)
    if not groups:
        print("분석된 이미지가 없습니다. 먼저 `shotsort scan` 을 실행하세요.")
        return
    for g, items in groups.items():
        dele = sum(1 for it in items if it["deletable"])
        print(f"\n■ {g}  ({len(items)}개" + (f", 🗑 {dele}" if dele else "") + ")")
        for it in items:
            mark = "🗑 " if it["deletable"] else "   "
            print(f"  {mark}{Path(it['path']).name:40.40s}  {it['summary']}")


def cmd_trash(args):
    paths = engine.collect_paths(args.group, args.deletable)
    if not paths:
        print("대상이 없습니다. (--group 이름 또는 --deletable 지정)")
        return
    print(f"휴지통으로 보낼 파일 {len(paths)}개:")
    for p in paths:
        print(f"  {Path(p).name}")
    if not args.yes:
        ans = input(f"\n{len(paths)}개를 휴지통으로 보낼까요? (복구 가능) [y/N] ").strip().lower()
        if ans != "y":
            print("취소됨.")
            return
    try:
        n = engine.trash(paths)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return
    print(f"{n}개를 휴지통으로 보냈습니다.")


def _non_negative_int(value: str) -> int:
    """argparse용 0 이상의 정수 변환기."""
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("0 이상의 정수여야 합니다") from error
    if number < 0:
        raise argparse.ArgumentTypeError("0 이상의 정수여야 합니다")
    return number


def _render_similarity_groups(groups: list[engine.DuplicateGroup]) -> None:
    """탐지 API가 정한 순서와 keeper·점수를 CLI에 그대로 표시한다."""
    for group_number, group in enumerate(groups, start=1):
        kind = "exact" if group.kind == "exact" else "유사"
        print(f"\n■ [{group_number}] {kind} 이미지 ({len(group.members)}개)")
        print(f"  보존 후보: {group.keeper.path}")
        scores = {score.member: score for score in group.member_similarities}
        for member_number, member in enumerate(group.members, start=1):
            score = scores.get(member)
            similarity = f"{score.similarity_percent:.2f}%" if score else "-"
            try:
                size = engine.human_mb(member.path.stat().st_size)
            except OSError:
                size = "크기 확인 불가"
            keeper_mark = " (보존 후보)" if member == group.keeper else ""
            print(f"  {member_number}. {similarity:>7}  {size:>10}  {member.path}{keeper_mark}")


def _selected_similarity_paths(groups: list[engine.DuplicateGroup], selections: list[str]) -> list[str] | None:
    """명시한 ``GROUP:NUMBER``만 비-keeper 경로로 바꾼다.

    잘못된 선택 하나라도 있으면 부분 삭제하지 않아 사용자가 출력 번호를 다시
    확인하도록 한다.
    """
    paths: list[str] = []
    seen: set[tuple[int, int]] = set()
    for selection in selections:
        try:
            group_text, member_text = selection.split(":", 1)
            group_number, member_number = int(group_text), int(member_text)
        except ValueError:
            print(f"잘못된 삭제 선택: {selection!r} (GROUP:NUMBER 형식)", file=sys.stderr)
            return None
        if group_number < 1 or member_number < 1 or group_number > len(groups):
            print(f"존재하지 않는 삭제 선택: {selection}", file=sys.stderr)
            return None
        group = groups[group_number - 1]
        if member_number > len(group.members):
            print(f"존재하지 않는 삭제 선택: {selection}", file=sys.stderr)
            return None
        key = (group_number, member_number)
        member = group.members[member_number - 1]
        if key in seen:
            print(f"중복된 삭제 선택: {selection}", file=sys.stderr)
            return None
        if member == group.keeper:
            print(f"보존 후보는 삭제할 수 없습니다: {selection}", file=sys.stderr)
            return None
        seen.add(key)
        paths.append(str(member.path))
    return paths


def cmd_similarity(args):
    root = Path(args.path).expanduser()
    if not root.exists():
        sys.exit(f"경로 없음: {root}")

    groups_result = engine.find_duplicate_groups(
        engine.find_images(root), hamming_threshold=args.threshold
    )
    groups = list(groups_result)
    if groups:
        _render_similarity_groups(groups)
    else:
        print("중복·유사 이미지를 찾지 못했습니다.")
    for error in groups_result.errors:
        print(f"검사 실패: {error.path}: {error.message}", file=sys.stderr)

    if not args.delete:
        return
    paths = _selected_similarity_paths(groups, args.delete)
    if not paths:
        return
    print(f"\n휴지통으로 보낼 파일 {len(paths)}개:")
    for path in paths:
        print(f"  {path}")
    if not args.yes:
        answer = input(f"\n{len(paths)}개를 휴지통으로 보낼까요? (복구 가능) [y/N] ").strip().lower()
        if answer != "y":
            print("취소됨.")
            return
    try:
        count = engine.trash(paths)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return
    print(f"{count}개를 휴지통으로 보냈습니다.")


def cmd_open(args):
    paths = engine.collect_paths(args.group, args.deletable)
    if not paths:
        print("대상이 없습니다.")
        return
    subprocess.run(["open", "-R", paths[0]])  # Finder 에서 첫 파일 위치 표시
    print(f"{len(paths)}개 중 첫 파일을 Finder 에 표시했습니다.")


def cmd_move(args):
    dest_root = Path(args.to).expanduser() if args.to else engine.default_export_root(DEFAULT_SCAN_DIR)
    paths = engine.collect_paths(args.group, args.deletable)
    if not paths:
        print("대상이 없습니다. (--group 이름 또는 --deletable 지정)")
        return
    n, folder = engine.move_group(args.group, dest_root, deletable=args.deletable)
    print(f"{n}개를 {folder} 로 이동했습니다.")


def cmd_zip(args):
    paths = engine.collect_paths(args.group, args.deletable)
    if not paths:
        print("대상이 없습니다. (--group 이름 또는 --deletable 지정)")
        return
    n, out = engine.zip_group(args.group, args.out, deletable=args.deletable)
    print(f"{n}개를 압축했습니다: {out}")


def cmd_stats(args):
    s = engine.stats()
    if not s.total:
        print("분석된 이미지가 없습니다.")
        return
    print(f"분석된 이미지 : {s.total}개")
    print(f"그룹 수       : {s.groups}개")
    print(f"삭제 후보     : {s.deletable}개 (약 {engine.human_mb(s.deletable_bytes)})")


def cmd_projects(args):
    """자주 쓰는 프로젝트 규칙 관리."""
    if args.action == "list":
        projects = engine.list_projects()
        if not projects:
            print("저장된 프로젝트가 없습니다.")
            return
        for project in projects:
            mark = "●" if project["enabled"] else "○"
            aliases = ", ".join(project["aliases"]) or "(별칭 없음)"
            print(f"{mark} {project['name']}: {aliases}")
        return

    if args.action == "add":
        aliases = [a.strip() for a in (args.aliases or "").split(",") if a.strip()]
        project = engine.save_project(
            args.name, aliases, enabled=True, characteristics=args.characteristics or ""
        )
        print(f"저장: {project['name']} ({', '.join(project['aliases']) or '별칭 없음'})")
        if project["characteristics"]:
            print(f"특징: {project['characteristics']}")
        return

    if args.action == "remove":
        n = engine.delete_project(args.name)
        print("삭제했습니다." if n else f"프로젝트를 찾지 못했습니다: {args.name}")
        return

    enabled = args.action == "enable"
    n = engine.set_project_enabled(args.name, enabled)
    if not n:
        print(f"프로젝트를 찾지 못했습니다: {args.name}", file=sys.stderr)
        return
    print(f"{args.name}: {'활성' if enabled else '비활성'}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="shotsort", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("scan", help="이미지 분석(캐시되지 않은 것만)")
    sp.add_argument("path", nargs="?", default=str(DEFAULT_SCAN_DIR), help=f"스캔 경로 (기본 {DEFAULT_SCAN_DIR})")
    sp.add_argument("--provider", default="auto",
                    choices=["auto", "cli", "api", "direct", "local", "anthropic", "openai", "xai"],
                    help="분석 방식 (auto: Codex CLI → 동의된 API → local; 기존 공급자명은 direct 단축값)")
    sp.add_argument("--direct-provider", choices=["anthropic", "openai", "xai"],
                    help="api/direct에 사용할 API 공급자 (기본: SHOTSORT_AI_PROVIDER 또는 anthropic)")
    sp.add_argument("--model", help=f"API/CLI 모델명 (Anthropic 기본 {DEFAULT_MODEL}; 다른 API는 필수)")
    sp.add_argument("--with-image", action="store_true", help="OCR 텍스트와 함께 축소 이미지를 선택한 API에 전송")
    sp.add_argument("--allow-api-transfer", action="store_true",
                    help="이번 비대화식 실행의 API 외부 전송에 명시 동의하고 공급자·이미지 범위 동의를 저장")
    sp.add_argument("--local", action="store_true", help="API 키가 있어도 로컬 휴리스틱 모드 강제(무료/오프라인)")
    sp.add_argument("--force", action="store_true", help="캐시 무시하고 전부 재분석")
    sp.add_argument("--projects", help="알려진 프로젝트명(쉼표 구분). OCR 에 이 단어가 있으면 해당 프로젝트로 묶음. 예: act-server,hitc,zipath")
    sp.set_defaults(func=cmd_scan)

    gp = sub.add_parser("groups", help="프로젝트별 그룹 보기")
    gp.add_argument("--deletable", action="store_true", help="삭제 후보만")
    gp.set_defaults(func=cmd_groups)

    tp = sub.add_parser("trash", help="그룹/삭제후보를 휴지통으로(복구 가능)")
    tp.add_argument("--group", help="그룹명")
    tp.add_argument("--deletable", action="store_true", help="삭제 후보 전체")
    tp.add_argument("-y", "--yes", action="store_true", help="확인 없이 실행")
    tp.set_defaults(func=cmd_trash)

    sip = sub.add_parser("similarity", help="중복·유사 이미지를 검사하고 명시 선택만 휴지통으로")
    sip.add_argument("path", nargs="?", default=str(DEFAULT_SCAN_DIR), help=f"검사 경로 (기본 {DEFAULT_SCAN_DIR})")
    sip.add_argument("--threshold", type=_non_negative_int, default=8,
                     help="pHash Hamming 거리 임계값 (기본: 8, 낮을수록 엄격)")
    sip.add_argument("--delete", action="append", default=[], metavar="GROUP:NUMBER",
                     help="출력 그룹과 구성원 번호를 명시해 삭제 (반복 가능, 보존 후보 제외)")
    sip.add_argument("-y", "--yes", action="store_true", help="삭제 확인 없이 실행")
    sip.set_defaults(func=cmd_similarity)

    op = sub.add_parser("open", help="그룹 파일을 Finder 에 표시")
    op.add_argument("--group", help="그룹명")
    op.add_argument("--deletable", action="store_true")
    op.set_defaults(func=cmd_open)

    mp = sub.add_parser("move", help="그룹/삭제후보를 폴더로 이동(<대상>/<그룹명>/)")
    mp.add_argument("--group", help="그룹명")
    mp.add_argument("--deletable", action="store_true", help="삭제 후보 전체")
    mp.add_argument("--to", help="대상 루트 폴더 (기본: <스캔 디렉토리>/_shotsort)")
    mp.set_defaults(func=cmd_move)

    zp = sub.add_parser("zip", help="그룹/삭제후보를 zip 으로 압축(원본 유지)")
    zp.add_argument("--group", help="그룹명")
    zp.add_argument("--deletable", action="store_true", help="삭제 후보 전체")
    zp.add_argument("--out", help="출력 zip 경로 (기본: <스캔 디렉토리>/_shotsort/<그룹명>.zip)")
    zp.set_defaults(func=cmd_zip)

    stp = sub.add_parser("stats", help="통계")
    stp.set_defaults(func=cmd_stats)

    pp = sub.add_parser("projects", help="자주 쓰는 프로젝트 규칙 관리")
    psub = pp.add_subparsers(dest="action", required=True)
    pl = psub.add_parser("list", help="저장 프로젝트 목록")
    pl.set_defaults(func=cmd_projects)
    pa = psub.add_parser("add", help="프로젝트 추가 또는 수정")
    pa.add_argument("name", help="표시할 프로젝트명")
    pa.add_argument("--aliases", default="", help="OCR/파일명에서 찾을 별칭(쉼표 구분)")
    pa.add_argument(
        "--characteristics", default="",
        help="화면의 색상·형태 등 시각적 특징(썸네일 전송 시 Claude 분류에 사용)",
    )
    pa.set_defaults(func=cmd_projects)
    for action, help_text in (("remove", "프로젝트 삭제"), ("enable", "프로젝트 활성화"),
                              ("disable", "프로젝트 비활성화")):
        px = psub.add_parser(action, help=help_text)
        px.add_argument("name")
        px.set_defaults(func=cmd_projects)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
