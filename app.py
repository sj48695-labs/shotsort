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
import providers
from lazy_groups import GroupPage
from preview_layout import (
    PREVIEW_CARD_CLASSES,
    PREVIEW_HEADER_CLASSES,
    PREVIEW_IMAGE_CLASSES,
    PREVIEW_IMAGE_PROPS,
    PREVIEW_IMAGE_WRAPPER_CLASSES,
    PREVIEW_IMAGE_WRAPPER_STYLE,
    PREVIEW_METADATA_CLASSES,
)


GROUP_PAGE_SIZE = 24
ANALYSIS_MODE_OPTIONS = {
    "auto": "자동 (Codex CLI → 동의한 API → 로컬)",
    "local": "로컬 분석만 (외부 전송 없음)",
    "cli": "Codex CLI",
    "api": "설치된 API Key 사용",
    "direct": "직접 설정 (고급)",
}
API_PROVIDER_OPTIONS = {
    "anthropic": "Anthropic Claude",
    "openai": "OpenAI",
    "xai": "xAI Grok",
}


@ui.page("/")
def index():
    # 현재 렌더된 카드의 체크박스 핸들 (경로 → checkbox) = 선택 상태의 단일 출처.
    checks: dict[str, "ui.checkbox"] = {}
    # Shift+클릭 범위 선택용: 렌더 순서(그룹별)와 마지막으로 클릭한 앵커.
    group_order: dict[str, list[str]] = {}  # 그룹명 → 그 그룹의 경로 순서
    path_group: dict[str, str] = {}         # 경로 → 그룹명
    anchor: dict[str, str | None] = {"path": None}
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
    with ui.card().classes("w-full"):
        with ui.row().classes("items-center gap-3 w-full"):
            path_in = ui.input("스캔 경로", value=str(engine.DEFAULT_SCAN_DIR)).classes("grow")
            scan_btn = ui.button("스캔", icon="search")
        ai_settings = engine.load_ai_settings()
        with ui.row().classes("items-start gap-3 w-full"):
            mode_in = ui.select(
                ANALYSIS_MODE_OPTIONS, value=ai_settings.get("analysis_mode", "auto"),
                label="분석 방식",
            ).classes("w-72")
            provider_in = ui.select(
                API_PROVIDER_OPTIONS, value=ai_settings.get("analysis_provider", "anthropic"),
                label="API 공급자",
            ).classes("w-48")
            model_select = ui.select({"__auto__": "자동 추천"}, value="__auto__", label="모델").classes("w-48")
            model_in = ui.input("직접 모델 입력", placeholder="목록에 없을 때만 입력").classes("grow")
            img_sw = ui.switch("이미지 내용도 AI로 분석", value=False)
        ui.separator()
        with ui.row().classes("items-center gap-3 w-full"):
            with ui.column().classes("gap-0 grow"):
                ui.label("자주 쓰는 프로젝트").classes("text-sm font-medium")
                ui.label("저장한 이름과 별칭은 다음 스캔부터 자동으로 우선 적용됩니다.").classes(
                    "text-xs text-gray-500"
                )
            projects_btn = ui.button("프로젝트 관리", icon="bookmark").props("outline")
        projects_box = ui.row().classes("items-center gap-2 w-full")
        mode_lbl = ui.label().classes("text-xs text-gray-500")
        model_warning = ui.label().classes("text-xs text-amber-800")
        model_warning.visible = False
        reset_model_btn = ui.button("자동 추천으로 바꾸기").props("flat dense")
        reset_model_btn.visible = False

        def selected_model() -> str | None:
            direct = (model_in.value or "").strip()
            return direct or (None if model_select.value == "__auto__" else model_select.value)

        def refresh_mode():
            """Show the exact safe route before scanning; this never performs AI work."""
            mode = mode_in.value
            provider = provider_in.value
            model = selected_model()
            catalog_mode = "cli" if mode == "cli" else "api"
            catalog = engine.load_model_catalog(provider, catalog_mode)
            options = {"__auto__": "자동 추천"}
            if catalog:
                options.update({name: name for name in catalog["models"]})
            model_select.set_options(options)
            capability = (providers.probe_codex_cli()
                          if mode in {"auto", "cli"} else None)
            config = providers.resolve_config(provider, model)
            consent = engine.has_api_consent(provider, with_image=img_sw.value)
            plan = providers.resolve_execution(
                mode, config, api_consent=consent, cli_capability=capability,
            )
            status = engine.keychain_status(provider)
            route = f"선택 예정: {plan.status.provider} / {plan.status.method.value}"
            if plan.status.model:
                route += f" / {plan.status.model}"
            transfer = "외부 전송 있음" if plan.status.external_transfer else "외부 전송 없음"
            detail = plan.status.fallback_reason or (capability.reason if capability else None)
            cache = (f"모델 목록: 캐시 {len(catalog['models'])}개"
                     if catalog else "모델 목록: 캐시 없음 · 자동 추천 사용")
            if catalog and catalog["stale"]:
                cache += " (24시간 경과)"
            mode_lbl.text = f"{route} · {transfer} · {cache} · Keychain/환경변수 상태: {status}"
            if detail:
                mode_lbl.text += f" · Codex CLI: {providers.mask_secret(detail)}"

            saved = ai_settings.get("analysis_model")
            missing = bool(saved and catalog and saved not in catalog["models"])
            model_warning.text = "저장된 모델을 찾을 수 없습니다. 확인 후 자동 추천으로 바꿉니다."
            model_warning.visible = missing
            reset_model_btn.visible = missing

        async def confirm_missing_saved_model():
            ok = await _confirm("저장된 모델을 찾을 수 없습니다. 자동 추천으로 바꿀까요?")
            if ok:
                model_select.value = "__auto__"
                model_in.value = ""
                ai_settings["analysis_model"] = ""
                engine.save_ai_settings({"analysis_model": ""})
                refresh_mode()

        for control in (mode_in, provider_in, model_select, model_in, img_sw):
            control.on_value_change(lambda _: refresh_mode())
        reset_model_btn.on_click(confirm_missing_saved_model)
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

    def render_projects():
        projects_box.clear()
        projects = engine.list_projects()
        with projects_box:
            if not projects:
                ui.label("아직 저장된 프로젝트가 없습니다.").classes("text-xs text-gray-400")
                return
            for project in projects:
                aliases = ", ".join(project["aliases"])
                chip = ui.chip(
                    project["name"],
                    icon="check_circle" if project["enabled"] else "pause_circle",
                ).props("dense outline" if project["enabled"] else "dense outline color=grey")
                detail = aliases or "별칭 없음"
                if project["characteristics"]:
                    detail += f"\n특징: {project['characteristics']}"
                chip.tooltip(detail)

    def selected_paths() -> list[str]:
        return [p for p, cb in checks.items() if cb.value]

    def update_sel():
        n = len(selected_paths())
        sel_lbl.text = f"선택 {n}개"
        trash_sel_btn.set_enabled(bool(n))

    def render_groups():
        checks.clear()
        group_order.clear()
        path_group.clear()
        anchor["path"] = None
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
                # 시작 속도를 위해 일반 그룹은 접어 둔다. 삭제 후보만 바로 보여 준다.
                expand = g == engine.CLEANUP_GROUP
                exp = ui.expansion(title, value=expand).classes("w-full border rounded")
                # 그룹 전체를 드롭존으로 — 카드를 끌어다 놓으면 그 그룹으로 재분류(접힘 무관).
                exp.on("dragover.prevent", lambda: None)
                exp.on("drop", lambda _, name=g: on_drop_to(name))
                with exp:
                    paths = [it["path"] for it in items]
                    group_order[g] = paths
                    for p in paths:
                        path_group[p] = g
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
                    _lazy_group_cards(exp, items, initially_expanded=expand)

    def _lazy_group_cards(expansion, items: list[dict], *, initially_expanded: bool):
        """Create thumbnail cards only as an expansion needs each bounded page."""
        cards_box = ui.row().classes("flex-wrap gap-3")
        more_box = ui.row().classes("items-center gap-2")
        page = GroupPage(len(items), GROUP_PAGE_SIZE)

        def render_page(indexes: range):
            if not indexes:
                return
            with cards_box:
                for index in indexes:
                    _thumb_card(items[index])

        def refresh_more():
            more_box.clear()
            if not page.remaining:
                return

            def load_more():
                render_page(page.more())
                refresh_more()

            with more_box:
                ui.button(
                    f"{min(page.page_size, page.remaining)}개 더 보기",
                    icon="expand_more",
                    on_click=load_more,
                ).props("flat dense")
                ui.label(f"{page.remaining}개 남음").classes("text-xs text-gray-500")

        def reveal_group(expanded: bool):
            render_page(page.reveal(expanded=expanded))
            if expanded:
                refresh_more()

        expansion.on_value_change(lambda e: reveal_group(e.value))
        reveal_group(initially_expanded)

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

    def _on_check_click(e, p: str):
        """체크박스 클릭 — Shift+클릭이면 같은 그룹 내 앵커~현재까지 범위 선택.

        클릭 시점엔 이미 체크박스가 토글된 뒤라 checks[p].value 가 목표 상태다.
        그 상태를 앵커~현재 구간 전체에 적용한다(파일 탐색기식 범위 선택).
        """
        shift = e.args.get("shiftKey") if isinstance(e.args, dict) else bool(e.args)
        a = anchor["path"]
        if shift and a and a != p and path_group.get(a) == path_group.get(p):
            order = group_order.get(path_group[p], [])
            try:
                i, j = order.index(a), order.index(p)
            except ValueError:
                i = j = -1
            if i >= 0 and j >= 0:
                lo, hi = (i, j) if i <= j else (j, i)
                target = checks[p].value
                for q in order[lo : hi + 1]:
                    if q in checks:
                        checks[q].value = target
                update_sel()
        anchor["path"] = p

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
            cb = ui.checkbox(
                "삭제 선택" + ("  🗑" if it["deletable"] else ""),
                value=False,
                on_change=lambda e: update_sel(),
            ).classes("text-xs")
            cb.tooltip("Shift+클릭: 같은 그룹 범위 선택")
            cb.on("click", lambda e, p=path: _on_check_click(e, p), args=["shiftKey"])
            checks[path] = cb

    # ── 액션 ────────────────────────────────────────────────────────────────
    async def request_api_consent() -> bool:
        """Ask once for the precise provider/image transfer scope before an API call."""
        provider = provider_in.value
        image_scope = "축소 이미지와 OCR 텍스트" if img_sw.value else "OCR 텍스트"
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("API 전송 동의").classes("text-lg font-bold")
            ui.label(
                f"{API_PROVIDER_OPTIONS[provider]} API로 {image_scope}를 전송해 분석합니다. "
                "이 동의는 현재 공급자와 이미지 포함 여부에만 적용됩니다."
            ).classes("text-sm")
            with ui.row().classes("justify-end w-full"):
                ui.button("취소", on_click=lambda: dialog.submit(False)).props("flat")
                ui.button("동의하고 계속", on_click=lambda: dialog.submit(True))
        allowed = await dialog
        if allowed:
            engine.set_api_consent(provider, with_image=img_sw.value, allowed=True)
        return bool(allowed)

    async def do_scan():
        root = Path(path_in.value).expanduser()
        if not root.exists():
            ui.notify(f"경로 없음: {root}", type="negative")
            return
        mode = mode_in.value
        provider = provider_in.value
        model = selected_model()
        config = providers.resolve_config(provider, model)
        capability = providers.probe_codex_cli() if mode in {"auto", "cli"} else None
        consent = engine.has_api_consent(provider, with_image=img_sw.value)
        possible_api = providers.resolve_execution(
            mode, config, api_consent=True, cli_capability=capability,
        )
        if possible_api.method == providers.ExecutionMethod.API and not consent:
            if not await request_api_consent():
                ui.notify("API 전송 동의가 없어 로컬 분석을 사용합니다.", type="info")
            consent = engine.has_api_consent(provider, with_image=img_sw.value)
        engine.save_ai_settings({
            "analysis_mode": mode,
            "analysis_provider": provider,
            "analysis_model": model or "",
        })
        if mode in {"api", "direct"} and not model:
            ui.notify("자동 추천 모델을 사용합니다. 목록에 없는 모델은 직접 입력할 수 있습니다.", type="info")
        scan_btn.props("loading")
        scan_btn.disable()
        progress.update(i=0, total=0, running=True)
        ui.notify("스캔 시작…", type="info")
        try:
            res = await run.io_bound(
                engine.scan_images,
                root,
                provider=provider,
                model=model,
                with_image=img_sw.value,
                analysis_mode=mode,
                api_consent=consent,
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
        msg += f" · 실제: {res.actual_provider}/{res.actual_method.value}"
        if res.actual_model:
            msg += f"/{res.actual_model}"
        msg += " · 외부 전송" if res.external_transfer else " · 외부 전송 없음"
        if res.fallback_reason:
            msg += f" · fallback: {providers.mask_secret(res.fallback_reason)}"
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

    async def manage_projects():
        rows = engine.list_projects()
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl"):
            with ui.row().classes("items-start w-full"):
                with ui.column().classes("gap-0"):
                    ui.label("자주 쓰는 프로젝트").classes("text-xl font-bold")
                    ui.label("텍스트 별칭과 화면의 시각적 특징을 함께 저장할 수 있습니다.").classes(
                        "text-sm text-gray-500"
                    )
                ui.space()
                ui.button(icon="close", on_click=dialog.close).props("flat round")

            name_in = ui.input("프로젝트명", placeholder="예: act-server").classes("w-full")
            aliases_in = ui.input(
                "별칭 (쉼표 구분)", placeholder="예: act server, github.com/acme/act-server"
            ).classes("w-full")
            characteristics_in = ui.textarea(
                "화면 특징", placeholder="예: 주황색 대화방 형태"
            ).props("autogrow").classes("w-full")
            ui.label(
                "색상·형태 특징은 Claude 모드에서 ‘썸네일도 전송’을 켰을 때 사용됩니다."
            ).classes("text-xs text-amber-700")

            async def save_current():
                name = (name_in.value or "").strip()
                if not name:
                    ui.notify("프로젝트명을 입력하세요.", type="warning")
                    return
                aliases = [a.strip() for a in (aliases_in.value or "").split(",") if a.strip()]
                await run.io_bound(
                    engine.save_project,
                    name,
                    aliases,
                    True,
                    (characteristics_in.value or "").strip(),
                )
                dialog.submit(True)

            with ui.row().classes("justify-end w-full"):
                ui.button("저장", icon="add", on_click=save_current)

            if rows:
                ui.separator()
                with ui.column().classes("w-full gap-2 max-h-72 overflow-auto"):
                    for project in rows:
                        with ui.row().classes("items-center w-full p-2 border rounded"):
                            toggle = ui.switch(value=project["enabled"])
                            with ui.column().classes("gap-0 grow"):
                                ui.label(project["name"]).classes("font-medium")
                                ui.label(", ".join(project["aliases"]) or "별칭 없음").classes(
                                    "text-xs text-gray-500"
                                )
                                if project["characteristics"]:
                                    ui.label(project["characteristics"]).classes(
                                        "text-xs text-amber-700"
                                    )
                            toggle.on_value_change(
                                lambda e, name=project["name"]: engine.set_project_enabled(name, e.value)
                            )

                            async def remove(name=project["name"]):
                                await run.io_bound(engine.delete_project, name)
                                dialog.submit(True)

                            ui.button(icon="delete", on_click=remove).props("flat round color=grey").tooltip(
                                f"{project['name']} 삭제"
                            )
        changed = await dialog
        if changed:
            render_projects()
            ui.notify("프로젝트 설정을 저장했습니다. 다음 스캔부터 적용됩니다.", type="positive")

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
        with ui.dialog().props("maximized") as dialog, ui.card().classes(PREVIEW_CARD_CLASSES):
            with ui.row().classes(PREVIEW_HEADER_CLASSES):
                ui.label(Path(path).name).classes("font-bold text-lg")
                ui.space()
                ui.button("Finder 에서 보기", icon="folder_open",
                          on_click=lambda: _reveal(path)).props("flat")
                ui.button(icon="close", on_click=dialog.close).props("flat round")
            uri = engine.thumbnail_uri(path, max_edge=2200)
            with ui.element("div").classes(PREVIEW_IMAGE_WRAPPER_CLASSES).style(
                PREVIEW_IMAGE_WRAPPER_STYLE
            ):
                if uri:
                    ui.image(uri).classes(PREVIEW_IMAGE_CLASSES).props(PREVIEW_IMAGE_PROPS)
            with ui.column().classes(PREVIEW_METADATA_CLASSES):
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
    projects_btn.on_click(manage_projects)
    organize_btn.on_click(do_organize_selected)
    trash_sel_btn.on_click(do_trash_selected)
    refresh_btn.on_click(lambda: (update_stats(), render_groups()))
    update_btn.on_click(do_update)
    ui.timer(0.3, tick_progress)
    ui.timer(0.5, check_for_update, once=True)  # 로드 직후 1회 업데이트 체크

    # 최초 표시
    update_stats()
    update_sel()
    render_projects()
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
