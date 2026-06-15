#!/usr/bin/env python3
"""shotsort CLI — engine.py 로직을 감싸는 얇은 커맨드라인 래퍼.

사용 예:
  shotsort scan ~/Desktop          # 분석 (캐시되지 않은 것만)
  shotsort groups                  # 프로젝트별 그룹 보기
  shotsort groups --deletable      # 삭제 후보만 보기
  shotsort trash --group "영수증"   # 그룹 통째로 휴지통(확인 후)
  shotsort trash --deletable       # 삭제 후보 전부 휴지통(확인 후)
  shotsort open --group "act-server"  # Finder 에서 그룹 파일 보기
  shotsort stats                   # 통계
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import engine
from engine import DEFAULT_MODEL, DEFAULT_SCAN_DIR


def cmd_scan(args):
    root = Path(args.path).expanduser()
    if not root.exists():
        sys.exit(f"경로 없음: {root}")

    use_llm = engine.resolve_mode(args.local)
    if not use_llm:
        reason = "--local 지정" if args.local else "ANTHROPIC_API_KEY 없음"
        print(f"⚠️  {reason} → 로컬 휴리스틱 모드(OCR + 규칙, Claude 미사용).")
        print("    무료·오프라인. 정확도는 낮음. 키 설정 후 다시 `scan` 하면 자동으로 LLM 분류로 업그레이드됩니다.\n")

    mode = f"모델: {args.model}" if use_llm else "로컬 휴리스틱"

    printed = False

    def on_item(i, total, path, tag, error):
        nonlocal printed
        if not printed:
            print(f"이미지 {total}개 발견. 분석 중... ({mode})")
            printed = True
        if error is not None:
            print(f"  [{i}/{total}] 분류 실패 {path.name}: {error}", file=sys.stderr)
            return
        mark = "  🗑 삭제후보" if tag["deletable"] else ""
        print(f"  [{i}/{total}] {path.name} → {tag['project']} ({tag['kind']}){mark}")

    hints = [h for h in (args.projects or "").split(",") if h.strip()]
    res = engine.scan_images(
        root,
        use_llm=use_llm,
        model=args.model,
        with_image=args.with_image,
        force=args.force,
        project_hints=hints,
        on_item=on_item,
    )

    if res.total == 0:
        print("이미지를 찾지 못했습니다.")
        return
    if not printed:
        print(f"이미지 {res.total}개 발견. 분석 중... ({mode})")

    print(f"\n분석 완료: 신규 {res.new}개, 캐시 스킵 {res.skipped}개")
    if res.consolidate_error:
        print(f"그룹 정규화 실패(개별 분류는 저장됨): {res.consolidate_error}", file=sys.stderr)
    else:
        print("완료. `shotsort groups` 로 확인하세요.")


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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="shotsort", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("scan", help="이미지 분석(캐시되지 않은 것만)")
    sp.add_argument("path", nargs="?", default=str(DEFAULT_SCAN_DIR), help=f"스캔 경로 (기본 {DEFAULT_SCAN_DIR})")
    sp.add_argument("--model", default=DEFAULT_MODEL, help=f"분류 모델 (기본 {DEFAULT_MODEL}; 비용절감: claude-haiku-4-5)")
    sp.add_argument("--with-image", action="store_true", help="OCR 텍스트와 함께 축소 썸네일도 Claude 에 전달(정확도↑ 비용↑)")
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
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
