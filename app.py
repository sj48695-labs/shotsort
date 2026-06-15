#!/usr/bin/env python3
"""shotsort 데스크탑 앱 (NiceGUI native) — 썸네일 격자로 보고 체크해서 일괄 휴지통.

실행:
  .venv/bin/python3 app.py          # 독립 앱 창(native)으로 뜸
  SHOTSORT_BROWSER=1 .venv/bin/python3 app.py   # 브라우저 탭으로 뜸
  SHOTSORT_DEV=1 .venv/bin/python3 app.py        # 개발: 파일변경 자동 리로드(브라우저)

엔진(engine.py)을 그대로 재사용한다. 썸네일은 engine.thumbnail_uri 로 만든
data-URI 라 별도 정적 파일 서버가 필요 없다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from nicegui import run, ui

import engine


@ui.page("/")
def index():
    # 현재 렌더된 카드의 체크박스 핸들 (경로 → checkbox) = 선택 상태의 단일 출처.
    checks: dict[str, "ui.checkbox"] = {}
    # 드래그 중인 이미지 경로 목록(카드 → 다른 그룹으로 끌어 재분류). 서버측 단일 출처.
    # 선택(체크)된 카드를 끌면 선택 전체, 아니면 그 카드 하나만 담긴다.
    dragging: dict[str, list[str]] = {"paths": []}
    # 스캔 진행률(워커 스레드가 갱신, UI 타이머가 읽음)
    progress = {"i": 0, "total": 0, "running": False}

    ui.label("shotsort — 스크린샷 정리").classes("text-2xl font-bold")
    ui.label(
        "스크린샷을 프로젝트별로 묶고, 지워도 되는 것을 체크해서 한꺼번에 휴지통으로 보냅니다 (복구 가능)."
    ).classes("text-sm text-gray-500")

    # ── 업데이트 알림 배너 (기본 숨김, 로드 시 백그라운드 체크) ───────────────
    update_banner = ui.row().classes(
        "w-full items-center gap-3 p-2 rounded"
    ).style("background:#fff3cd")
    update_banner.visible = False
    with update_banner:
        update_lbl = ui.label().classes("text-sm")
        ui.space()
        update_btn = ui.button("업데이트", icon="system_update").props("dense")
        ui.button("나중에", on_click=lambda: update_banner.set_visibility(False)).props("flat dense")

    # ── 스캔 컨트롤 ──────────────────────────────────────────────────────────
    has_key = engine.has_api_key()
    with ui.card().classes("w-full"):
        with ui.row().classes("items-center gap-3 w-full"):
            path_in = ui.input("스캔 경로", value=str(engine.DEFAULT_SCAN_DIR)).classes("grow")
            local_sw = ui.switch("로컬 모드(무료)", value=not has_key)
            img_sw = ui.switch("썸네일도 전송", value=False)
            scan_btn = ui.button("스캔", icon="search")
        with ui.row().classes("items-center gap-2 w-full"):
            hints_in = ui.input(
                "프로젝트 힌트 (쉼표)",
                placeholder="act-server, hitc, zipath — OCR 에 이 단어가 있으면 해당 프로젝트로 묶음",
            ).classes("grow")
            apply_hints_btn = ui.button("힌트로 다시 묶기", icon="auto_awesome").props("outline")
        mode_lbl = ui.label().classes("text-xs text-gray-500")

        def refresh_mode():
            use_llm = engine.resolve_mode(local_sw.value)
            if use_llm:
                mode_lbl.text = "모드: Claude 분류 (claude-opus-4-8). '썸네일도 전송' 켜면 정확도↑ 비용↑."
                img_sw.enable()
            else:
                why = "로컬 강제" if local_sw.value else "ANTHROPIC_API_KEY 없음"
                mode_lbl.text = f"모드: 로컬 휴리스틱 ({why}) — 무료·오프라인, 정확도는 낮음."
                img_sw.disable()

        local_sw.on_value_change(lambda _: refresh_mode())
        refresh_mode()
        prog_lbl = ui.label().classes("text-xs text-primary")

    # ── 통계 + 일괄 액션 ─────────────────────────────────────────────────────
    with ui.row().classes("items-center gap-4 w-full"):
        stats_lbl = ui.label().classes("text-sm")
        sel_lbl = ui.label("선택 0개").classes("text-sm text-primary")
        ui.space()
        organize_btn = ui.button("그룹 폴더로 정리…", icon="create_new_folder").props("outline")
        trash_sel_btn = ui.button("선택 항목 휴지통으로", icon="delete", color="red")
        refresh_btn = ui.button("새로고침", icon="refresh").props("flat")

    groups_box = ui.column().classes("w-full gap-2")

    # ── 렌더링 ──────────────────────────────────────────────────────────────
    def update_stats():
        s = engine.stats()
        stats_lbl.text = (
            f"이미지 {s.total}개 · 그룹 {s.groups}개 · 삭제후보 {s.deletable}개({engine.human_mb(s.deletable_bytes)})"
        )

    def selected_paths() -> list[str]:
        return [p for p, cb in checks.items() if cb.value]

    def update_sel():
        n = len(selected_paths())
        sel_lbl.text = f"선택 {n}개"
        trash_sel_btn.set_enabled(bool(n))

    def render_groups():
        checks.clear()
        update_sel()
        groups = engine.list_groups()
        groups_box.clear()
        with groups_box:
            if not groups:
                ui.label("분석된 이미지가 없습니다. 경로를 정하고 '스캔'을 누르세요.").classes(
                    "text-gray-500"
                )
                return
            for g, items in groups.items():
                dele = sum(1 for it in items if it["deletable"])
                title = f"{g}  ({len(items)}개" + (f", 🗑 {dele}" if dele else "") + ")"
                # 기본은 접힘 — 삭제후보 그룹과 큰 그룹(5장+)만 펼쳐서 노이즈를 줄인다.
                expand = (g == engine.CLEANUP_GROUP) or len(items) >= 5
                exp = ui.expansion(title, value=expand).classes("w-full border rounded")
                # 그룹 전체를 드롭존으로 — 카드를 끌어다 놓으면 그 그룹으로 재분류(접힘 무관).
                exp.on("dragover.prevent", lambda: None)
                exp.on("drop", lambda _, name=g: on_drop_to(name))
                with exp:
                    paths = [it["path"] for it in items]
                    with ui.row().classes("gap-2 mb-2 items-center"):
                        ui.button(
                            "이 그룹 전체선택",
                            on_click=lambda _, ps=paths: select_paths(ps, True),
                        ).props("flat dense")
                        ui.button(
                            "해제", on_click=lambda _, ps=paths: select_paths(ps, False)
                        ).props("flat dense")
                        ui.button(
                            "이름 변경", icon="edit",
                            on_click=lambda _, name=g: do_rename_group(name),
                        ).props("flat dense")
                        ui.button(
                            "폴더로 이동", icon="drive_file_move",
                            on_click=lambda _, name=g: do_move_group(name),
                        ).props("flat dense")
                        ui.button(
                            "압축", icon="folder_zip",
                            on_click=lambda _, name=g: do_zip_group(name),
                        ).props("flat dense")
                        ui.button(
                            "이 그룹 휴지통으로", color="red",
                            on_click=lambda _, name=g: do_trash_group(name),
                        ).props("flat dense")
                    with ui.row().classes("flex-wrap gap-3"):
                        for it in items:
                            _thumb_card(it)

    def _start_drag(p: str):
        # 끄는 카드가 선택돼 있으면 선택 전체를, 아니면 그 카드만 끈다.
        sel = selected_paths()
        dragging["paths"] = sel if p in sel else [p]

    def on_drop_to(group: str):
        paths = dragging.get("paths") or []
        dragging["paths"] = []
        if not paths:
            return
        n = engine.move_images_to_group(paths, group)
        if n:
            label = Path(paths[0]).name if n == 1 else f"{n}개"
            ui.notify(f"{label} → '{group}' 그룹으로 이동", type="positive")
            update_stats()
            render_groups()

    def select_paths(paths: list[str], on: bool):
        for p in paths:
            if p in checks:
                checks[p].value = on
        update_sel()

    def _thumb_card(it: dict):
        path = it["path"]
        card = ui.card().classes("p-1 cursor-move").style("width:180px")
        card.props("draggable=true")
        card.on("dragstart", lambda _, p=path: _start_drag(p))
        with card:
            uri = engine.thumbnail_uri(path)
            if uri:
                img = ui.image(uri).classes("w-full cursor-pointer").style(
                    "height:120px;object-fit:cover"
                )
                img.props("draggable=false")  # 카드가 드래그되도록 이미지 기본 드래그 끔
                img.tooltip("클릭=미리보기 · 끌어서 다른 그룹으로 이동")
                img.on("click", lambda _, it=it: open_preview(it))
            else:
                ui.label("(미리보기 없음)").classes("text-xs text-gray-400")
            ui.label(Path(path).name).classes(
                "text-xs truncate w-full cursor-pointer"
            ).tooltip(Path(path).name).on("click", lambda _, it=it: open_preview(it))
            if it["summary"]:
                ui.label(it["summary"]).classes("text-xs text-gray-500 truncate w-full")
            checks[path] = ui.checkbox(
                "삭제 선택" + ("  🗑" if it["deletable"] else ""),
                value=False,
                on_change=lambda e: update_sel(),
            ).classes("text-xs")

    # ── 액션 ────────────────────────────────────────────────────────────────
    async def do_scan():
        root = Path(path_in.value).expanduser()
        if not root.exists():
            ui.notify(f"경로 없음: {root}", type="negative")
            return
        use_llm = engine.resolve_mode(local_sw.value)
        scan_btn.props("loading")
        scan_btn.disable()
        progress.update(i=0, total=0, running=True)
        ui.notify("스캔 시작…", type="info")
        try:
            hints = [h for h in hints_in.value.split(",") if h.strip()]
            res = await run.io_bound(
                engine.scan_images,
                root,
                use_llm=use_llm,
                with_image=img_sw.value,
                project_hints=hints,
                on_item=on_scan_item,
            )
        except Exception as e:
            ui.notify(f"스캔 실패: {e}", type="negative")
            return
        finally:
            progress["running"] = False
            scan_btn.props(remove="loading")
            scan_btn.enable()
        msg = f"완료: 신규 {res.new}개, 스킵 {res.skipped}개"
        if res.consolidate_error:
            msg += f" (그룹 정규화 실패: {res.consolidate_error})"
        ui.notify(msg, type="positive")
        update_stats()
        render_groups()

    async def do_trash_selected():
        paths = sorted(selected_paths())
        if not paths:
            return
        ok = await _confirm(f"{len(paths)}개를 휴지통으로 보낼까요? (복구 가능)")
        if not ok:
            return
        try:
            n = await run.io_bound(engine.trash, paths)
        except Exception as e:
            ui.notify(f"휴지통 이동 실패: {e}", type="negative")
            return
        ui.notify(f"{n}개를 휴지통으로 보냈습니다.", type="positive")
        update_stats()
        render_groups()

    async def do_trash_group(name: str):
        paths = engine.collect_paths(name, deletable=False)
        if not paths:
            return
        ok = await _confirm(f"'{name}' 그룹 {len(paths)}개를 휴지통으로 보낼까요? (복구 가능)")
        if not ok:
            return
        try:
            n = await run.io_bound(engine.trash, paths)
        except Exception as e:
            ui.notify(f"휴지통 이동 실패: {e}", type="negative")
            return
        ui.notify(f"{n}개를 휴지통으로 보냈습니다.", type="positive")
        update_stats()
        render_groups()

    async def do_apply_hints():
        hints = [h for h in hints_in.value.split(",") if h.strip()]
        if not hints:
            ui.notify("프로젝트 힌트를 쉼표로 입력하세요. 예: act-server, hitc, zipath", type="warning")
            return
        n = await run.io_bound(engine.apply_project_hints, hints)
        ui.notify(f"{n}개 스크린샷을 힌트 프로젝트로 다시 묶었습니다.", type="positive")
        update_stats()
        render_groups()

    async def do_organize_selected():
        groups = engine.list_groups()
        if not groups:
            return
        default_root = str(engine.default_export_root(path_in.value))
        boxes: dict[str, "ui.checkbox"] = {}
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("폴더로 정리할 그룹 선택").classes("font-bold")
            ui.label("선택한 그룹만 대상 폴더 아래 '<그룹명>/' 폴더로 이동합니다.").classes(
                "text-xs text-gray-500"
            )

            def set_all(v: bool):
                for b in boxes.values():
                    b.value = v

            with ui.row().classes("gap-2"):
                ui.button("전체 선택", on_click=lambda: set_all(True)).props("flat dense")
                ui.button("전체 해제", on_click=lambda: set_all(False)).props("flat dense")
            with ui.column().classes("max-h-60 overflow-auto w-full gap-0 border rounded p-1"):
                for name, items in groups.items():
                    boxes[name] = ui.checkbox(
                        f"{name}  ({len(items)}개)", value=False
                    ).classes("text-sm")
            dest_in = ui.input("대상 루트 폴더", value=default_root).classes("w-full")
            with ui.row().classes("justify-end w-full"):
                ui.button("취소", on_click=lambda: dialog.submit(False)).props("flat")
                ui.button("정리", icon="create_new_folder",
                          on_click=lambda: dialog.submit(True))
        ok = await dialog
        if not ok:
            return
        chosen = [n for n, b in boxes.items() if b.value]
        if not chosen:
            ui.notify("정리할 그룹을 하나 이상 선택하세요.", type="warning")
            return
        total = 0
        try:
            for name in chosen:
                n, _ = await run.io_bound(engine.move_group, name, dest_in.value, deletable=False)
                total += n
        except Exception as e:
            ui.notify(f"정리 실패: {e}", type="negative")
            update_stats(); render_groups()
            return
        ui.notify(f"{total}개를 {len(chosen)}개 그룹 폴더로 정리했습니다.", type="positive")
        update_stats()
        render_groups()

    async def do_rename_group(name: str):
        new = await _prompt_path(
            f"'{name}' 그룹의 새 이름 (정리 시 이 이름의 폴더가 만들어집니다):", name
        )
        if not new or not new.strip() or new.strip() == name:
            return
        n = await run.io_bound(engine.rename_group, name, new.strip())
        ui.notify(f"'{name}' → '{new.strip()}' ({n}개) 이름을 바꿨습니다.", type="positive")
        update_stats()
        render_groups()

    async def do_move_group(name: str):
        paths = engine.collect_paths(name, deletable=False)
        if not paths:
            return
        default_root = str(engine.default_export_root(path_in.value))
        dest = await _prompt_path(
            f"'{name}' 그룹 {len(paths)}개를 옮길 대상 루트 폴더 (그 아래 '{name}' 폴더가 생깁니다):",
            default_root,
        )
        if not dest:
            return
        try:
            n, folder = await run.io_bound(engine.move_group, name, dest, deletable=False)
        except Exception as e:
            ui.notify(f"이동 실패: {e}", type="negative")
            return
        ui.notify(f"{n}개를 {folder} 로 이동했습니다.", type="positive")
        update_stats()
        render_groups()

    async def do_zip_group(name: str):
        paths = engine.collect_paths(name, deletable=False)
        if not paths:
            return
        default_out = str(
            engine.default_export_root(path_in.value) / f"{engine.safe_dirname(name)}.zip"
        )
        out = await _prompt_path(
            f"'{name}' 그룹 {len(paths)}개를 압축할 zip 경로 (원본은 그대로 둡니다):",
            default_out,
        )
        if not out:
            return
        try:
            n, dest = await run.io_bound(engine.zip_group, name, out, deletable=False)
        except Exception as e:
            ui.notify(f"압축 실패: {e}", type="negative")
            return
        ui.notify(f"{n}개를 압축했습니다: {dest}", type="positive")

    def open_preview(it: dict):
        path = it["path"]
        with ui.dialog().props("maximized") as dialog, ui.card().classes(
            "w-full h-full items-center"
        ):
            with ui.row().classes("items-center w-full gap-2"):
                ui.label(Path(path).name).classes("font-bold text-lg")
                ui.space()
                ui.button("Finder 에서 보기", icon="folder_open",
                          on_click=lambda: _reveal(path)).props("flat")
                ui.button(icon="close", on_click=dialog.close).props("flat round")
            uri = engine.thumbnail_uri(path, max_edge=2200)
            if uri:
                # 남는 공간을 꽉 채워 가능한 한 크게(원본 비율 유지).
                ui.image(uri).classes("grow w-full").style("object-fit:contain;min-height:0")
            meta = f"그룹: {it.get('grp') or it.get('project') or '-'}  ·  종류: {it.get('kind') or '-'}"
            ui.label(meta).classes("text-sm text-gray-500")
            if it.get("summary"):
                ui.label(it["summary"]).classes("text-sm text-gray-500")
            ui.label(path).classes("text-xs text-gray-400 break-all")
        dialog.open()

    def _reveal(path: str):
        try:
            engine.reveal_in_finder(path)
        except Exception as e:
            ui.notify(str(e), type="negative")

    async def _prompt_path(message: str, default: str) -> str | None:
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label(message).classes("text-sm")
            inp = ui.input(value=default).classes("w-full")
            with ui.row().classes("justify-end w-full"):
                ui.button("취소", on_click=lambda: dialog.submit(None)).props("flat")
                ui.button("확인", on_click=lambda: dialog.submit(inp.value))
        return await dialog

    async def _confirm(message: str) -> bool:
        with ui.dialog() as dialog, ui.card():
            ui.label(message)
            with ui.row().classes("justify-end w-full"):
                ui.button("취소", on_click=lambda: dialog.submit(False)).props("flat")
                ui.button("휴지통으로", color="red", on_click=lambda: dialog.submit(True))
        return await dialog

    def on_scan_item(i, total, path, tag, error):
        progress["i"], progress["total"] = i, total  # 워커 스레드에서 호출

    def tick_progress():
        if progress["running"]:
            prog_lbl.text = f"분석 중… {progress['i']}/{progress['total']}"
        elif prog_lbl.text:
            prog_lbl.text = ""

    upd = {"status": None}

    async def check_for_update():
        st = await run.io_bound(engine.check_update)
        upd["status"] = st
        if not st.available:
            return
        if st.mode == "release":  # .app 번들 → 다운로드 페이지로 안내
            update_lbl.text = f"새 버전 {st.latest} 이 있습니다. '다운로드'로 릴리스 페이지를 엽니다."
            update_btn.text = "다운로드"
        else:                      # git 설치 → pull + 재시작
            update_lbl.text = (
                f"새 버전이 있습니다 — {st.behind}개 커밋 뒤처짐. "
                "'업데이트'를 누르면 받아서 자동 재시작합니다."
            )
            update_btn.text = "업데이트"
        update_banner.set_visibility(True)

    async def do_update():
        st = upd["status"]
        if st and st.mode == "release":  # 번들: 자체 교체 대신 다운로드 페이지 열기
            import webbrowser
            webbrowser.open(st.url or f"https://github.com/{engine.REPO_SLUG}/releases/latest")
            update_banner.set_visibility(False)
            return
        update_btn.props("loading")
        update_btn.disable()
        ok, msg = await run.io_bound(engine.apply_update)
        if not ok:
            update_btn.props(remove="loading")
            update_btn.enable()
            ui.notify(f"업데이트 실패: {msg}", type="negative")
            return
        ui.notify("업데이트 적용됨 — 재시작합니다…", type="positive")
        ui.timer(1.2, _restart, once=True)  # notify 가 렌더된 뒤 재시작

    scan_btn.on_click(do_scan)
    apply_hints_btn.on_click(do_apply_hints)
    organize_btn.on_click(do_organize_selected)
    trash_sel_btn.on_click(do_trash_selected)
    refresh_btn.on_click(lambda: (update_stats(), render_groups()))
    update_btn.on_click(do_update)
    ui.timer(0.3, tick_progress)
    ui.timer(0.5, check_for_update, once=True)  # 로드 직후 1회 업데이트 체크

    # 최초 표시
    update_stats()
    update_sel()
    render_groups()


def _restart():
    """현재 프로세스를 같은 인자로 재실행(업데이트 적용 후 새 코드 로드)."""
    os.execv(sys.executable, [sys.executable, *sys.argv])


def _free_port(preferred: int = 8713) -> int:
    """preferred 가 비어 있으면 그대로, 점유 중이면 OS 가 주는 빈 포트를 쓴다."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    # 개발 모드(SHOTSORT_DEV=1): 파일변경 자동 리로드. reload 는 native 와 충돌하므로
    # 이때는 브라우저로 띄운다.
    dev = os.environ.get("SHOTSORT_DEV") == "1"
    native = (os.environ.get("SHOTSORT_BROWSER") != "1") and not dev
    port = _free_port(int(os.environ.get("SHOTSORT_PORT", "8713")))
    ui.run(
        native=native,
        reload=dev,
        title="shotsort",
        window_size=(1100, 800) if native else None,
        port=port,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
