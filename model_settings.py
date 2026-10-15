"""앱 화면에서만 유지하는 분류 모델 설정. API 키는 디스크에 저장하지 않는다."""
from dataclasses import dataclass, field

from nicegui import run, ui

from cli_provider import CLI_NAMES, check_cli_login

from providers import ProviderConfig, resolve_config, validate_config


NAMES = {"claude_cli": "Claude · PC 계정", "codex_cli": "Codex · PC 계정", "local": "내 Mac에서만 분석", "anthropic": "Claude API",
         "openai": "OpenAI API", "xai": "Grok API"}


@dataclass
class ModelSettings:
    config: ProviderConfig = field(default_factory=ProviderConfig)
    with_image: bool = False


def model_settings_controls(default_claude_model: str) -> ModelSettings:
    settings = ModelSettings()
    ui.add_css('''
        .model-settings-card :focus-visible { box-shadow: 0 0 0 3px var(--q-primary) !important; }
        .model-settings-card .q-btn, .model-settings-card .q-radio { min-height: 44px; }
    ''')
    with ui.row().classes("w-full items-center gap-3"):
        ui.icon("shield", color="primary").classes("text-2xl")
        with ui.column().classes("grow gap-1 min-w-0"):
            summary = ui.label("내 Mac에서만 분석 · 무료").classes("font-medium break-all")
            privacy = ui.label("계정 없이 사용 · 외부 전송 없음").classes("text-sm text-gray-600")
        open_btn = ui.button("모델 설정", icon="tune").props("outline no-caps")

    with ui.dialog() as dialog, ui.card().classes("model-settings-card w-full max-w-xl p-5 sm:p-7 gap-5"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("모델 설정").classes("text-xl font-bold")
            ui.button(icon="close", on_click=dialog.close).props(
                'flat round aria-label="모델 설정 닫기"'
            )
        ui.label("이 PC에 로그인된 Claude·Codex를 연결해 사용하세요.").classes(
            "text-sm text-gray-600"
        )
        provider = ui.radio({"claude_cli": NAMES["claude_cli"], "codex_cli": NAMES["codex_cli"],
                             "local": "내 Mac에서만 분석 · 무료", "api": "API 키로 연결 · 선택 사항"},
                            value="local").props('aria-label="분류 모델 선택"').classes("w-full")
        with ui.column().classes("w-full rounded-lg bg-gray-100 p-4 gap-3") as pc_info:
            ui.label("PC에 저장된 CLI 로그인을 사용합니다").classes("font-medium")
            ui.label("별도 API 키 입력 없이 연결합니다. 분석은 공급자 서버에서 이뤄지며, CLI 계정의 요금과 사용 한도가 적용됩니다.").classes("text-sm text-gray-700")
            login_labels = {name: ui.label(f"{label}: 확인 전").classes("text-sm text-gray-700")
                            for name, label in CLI_NAMES.items()}

            async def check_connections():
                check_btn.props("loading")
                check_btn.disable()
                try:
                    for name, label in login_labels.items():
                        _, message = await run.io_bound(check_cli_login, name)
                        label.text = f"{CLI_NAMES[name]}: {message}"
                finally:
                    check_btn.props(remove="loading")
                    check_btn.enable()

            check_btn = ui.button("PC 연결 확인", icon="refresh", on_click=check_connections).props("outline")
        with ui.column().classes("w-full rounded-lg bg-gray-100 p-4 gap-2") as local_info:
            ui.label("이 Mac 안에서 처리합니다").classes("font-medium")
            ui.label("OCR과 화면 특징을 비교해 묶습니다. API 키나 추가 결제가 필요 없습니다.").classes(
                "text-sm text-gray-700"
            )
        with ui.column().classes("w-full gap-4") as remote_fields:
            ui.label("사용자 본인의 API로 분석하며, 사용량에 따라 해당 공급자에서 과금됩니다.").classes(
                "text-sm text-gray-700"
            )
            api_provider = ui.select({k: NAMES[k] for k in ("anthropic", "openai", "xai")},
                                     value="anthropic", label="API 공급자").props("outlined").classes("w-full")
            key = ui.input("API 키", password=True,
                           placeholder="내 API 키를 붙여넣으세요").props(
                'outlined autocomplete="off"'
            ).classes("w-full")
            ui.label("키는 파일에 저장하지 않습니다. 화면을 새로 열면 다시 입력하세요. 이미 설정된 키가 있으면 비워둘 수 있습니다.").classes(
                "text-xs text-gray-600"
            )
            ui.label("API 키와 모델의 실제 사용 가능 여부는 스캔할 때 확인합니다.").classes("text-xs text-gray-600")
        model = ui.input("모델명 (선택)", placeholder="비워두면 CLI 기본 모델 사용").props("outlined").classes("w-full")
        images = ui.switch("이미지 내용도 AI로 분석", value=False)
        transfer = ui.label().classes("text-sm text-gray-700")
        error = ui.label().props('role="alert" aria-live="polite"').classes("text-sm text-red-700")
        error.visible = False

        def update_transfer():
            transfer.text = (
                "외부 전송: OCR 텍스트와 축소 이미지가 선택한 공급자에 전송됩니다."
                if images.value else "외부 전송: OCR 텍스트만 선택한 공급자에 전송됩니다."
            )

        def update_fields():
            is_api = provider.value == "api"
            is_cli = provider.value in CLI_NAMES
            remote_fields.set_visibility(is_api)
            pc_info.set_visibility(is_cli)
            local_info.set_visibility(provider.value == "local")
            model.set_visibility(is_api or is_cli)
            model.set_label("모델명" if is_api else "모델명 (선택)")
            model.props('placeholder="사용할 API 모델명을 입력하세요"' if is_api else
                        'placeholder="비워두면 CLI 기본 모델 사용"')
            images.set_visibility(is_api)
            transfer.set_visibility(is_api or is_cli)
            error.set_visibility(False)
            key.set_value("")
            model.set_value(default_claude_model if is_api and api_provider.value == "anthropic" else "")
            images.set_value(False)
            update_transfer()

        async def apply():
            name = api_provider.value if provider.value == "api" else provider.value
            config = resolve_config(
                name, (model.value or "").strip() or None,
                api_key=(key.value or "").strip() or None,
            ) if name != "local" else ProviderConfig()
            is_cli = name in CLI_NAMES
            if is_cli:
                apply_btn.props("loading")
                apply_btn.disable()
                try:
                    ready, message = await run.io_bound(check_cli_login, name)
                    login_labels[name].text = f"{CLI_NAMES[name]}: {message}"
                finally:
                    apply_btn.props(remove="loading")
                    apply_btn.enable()
                if not ready:
                    error.text = message
                    error.set_visibility(True)
                    return
            elif config.is_remote:
                if not config.model or not config.api_key:
                    error.text = "모델명을 입력하세요." if not config.model else "API 키를 입력하세요."
                    error.set_visibility(True)
                    return
                validate_config(config)
            with_image = config.is_remote and not is_cli and images.value
            with ui.dialog() as approval, ui.card().classes("model-settings-card w-full max-w-md gap-4 p-6"):
                ui.label("이 모델로 변경할까요?").classes("text-lg font-bold")
                ui.label(NAMES[name]).classes("font-medium")
                if config.is_remote:
                    ui.label(config.model or "CLI 기본 모델").classes("text-sm break-all")
                    ui.label(
                        "스캔할 때 OCR 텍스트와 축소 이미지가 전송됩니다."
                        if with_image else "스캔할 때 OCR 텍스트만 전송됩니다."
                    ).classes("text-sm text-gray-700")
                    ui.label("PC에 로그인된 CLI 계정의 요금·사용 한도가 적용됩니다." if is_cli else
                             "API 사용료는 본인의 공급자 계정에 청구됩니다.").classes("text-sm text-gray-700")
                else:
                    ui.label("무료 · 외부 전송 없이 이 Mac에서 처리합니다.").classes("text-sm text-gray-700")
                ui.label("승인하면 다음 스캔부터 적용됩니다.").classes("text-sm text-gray-600")
                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("취소", on_click=lambda: approval.submit(False)).props("flat autofocus")
                    ui.button("승인하고 사용", on_click=lambda: approval.submit(True))
            apply_btn.disable()
            try:
                approved = await approval
            finally:
                apply_btn.enable()
                approval.delete()
            if not approved:
                return
            settings.config = config
            settings.with_image = with_image
            summary.text = f"{NAMES[name]} · {config.model or 'CLI 기본 모델'}" if config.is_remote else "내 Mac에서만 분석 · 무료"
            privacy.text = (
                "스캔 시 OCR 텍스트와 축소 이미지 전송" if settings.with_image else
                "스캔 시 OCR 텍스트만 전송" if config.is_remote else "계정 없이 사용 · 외부 전송 없음"
            )
            dialog.close()
            ui.notify("다음 스캔에 사용할 모델을 설정했습니다.", type="positive")

        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("취소", on_click=dialog.close).props("flat")
            apply_btn = ui.button("이 방식으로 사용", on_click=apply)
        provider.on_value_change(update_fields)
        api_provider.on_value_change(update_fields)
        images.on_value_change(update_transfer)
        update_fields()
        update_transfer()

    def open_settings():
        is_api = settings.config.provider in {"anthropic", "openai", "xai"}
        if is_api:
            api_provider.set_value(settings.config.provider)
        provider.set_value("api" if is_api else settings.config.provider)
        update_fields()
        key.set_value(settings.config.api_key or "")
        model.set_value(settings.config.model or "")
        images.set_value(settings.with_image)
        error.set_visibility(False)
        dialog.open()

    open_btn.on_click(open_settings)
    return settings
