"""Provider-neutral structured AI calls for screenshot classification.

The module deliberately does not guess a vendor's newest model.  Remote providers
require an explicit model (argument or environment variable), which keeps model
availability and pricing decisions with the user.
"""
from __future__ import annotations

import json
import os
import base64
import re
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


PROVIDERS = ("local", "anthropic", "openai", "xai")


class AnalysisMode(str, Enum):
    AUTO = "auto"
    LOCAL = "local"
    CLI = "cli"
    API = "api"
    DIRECT = "direct"


class ExecutionMethod(str, Enum):
    LOCAL = "local"
    CODEX_CLI = "codex_cli"
    API = "api"


class ProviderError(RuntimeError):
    """A user-displayable provider error with secrets removed."""


class CapabilityError(ProviderError):
    pass


class AuthenticationError(ProviderError):
    pass


class ExecutionTimeout(ProviderError):
    pass


class StructuredOutputError(ProviderError):
    pass


@dataclass(frozen=True)
class ProviderCapability:
    available: bool
    logged_in: bool = False
    supports_images: bool = False
    supports_structured_output: bool = False
    reason: str | None = None

    @property
    def ready(self) -> bool:
        return (self.available and self.logged_in and self.supports_images
                and self.supports_structured_output)

    @classmethod
    def codex_cli(cls, *, available: bool, logged_in: bool = False,
                  supports_images: bool = True,
                  supports_structured_output: bool = True,
                  reason: str | None = None) -> "ProviderCapability":
        return cls(available, logged_in, supports_images,
                   supports_structured_output, reason)


@dataclass(frozen=True)
class ExecutionStatus:
    provider: str
    method: ExecutionMethod
    model: str | None = None
    external_transfer: bool = False
    fallback_reason: str | None = None


@dataclass(frozen=True)
class ExecutionPlan:
    method: ExecutionMethod
    config: "ProviderConfig"
    status: ExecutionStatus
    capability: ProviderCapability | None = None


_SECRET_PATTERNS = (
    (re.compile(r"(?i)\b(Bearer)\s+[^\s,;]+"), r"\1 ***"),
    (re.compile(r"\b(sk-[A-Za-z0-9_-]+)"), "***"),
    (re.compile(r"(?i)\b((?:OPENAI|ANTHROPIC|XAI)_API_KEY)=[^\s,;]+"), r"\1=***"),
)


def mask_secret(value: object) -> str:
    """Return text safe for UI, logs, and exceptions.

    Environment variable names remain useful for remediation, but their values and
    common bearer/key forms never escape this module.
    """
    text = str(value or "")
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


@dataclass(frozen=True)
class ProviderConfig:
    provider: str = "local"
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None

    @property
    def is_remote(self) -> bool:
        return self.provider != "local"


def resolve_config(
    provider: str | None = None,
    model: str | None = None,
    env: Mapping[str, str] | None = None,
) -> ProviderConfig:
    """Resolve provider credentials without silently selecting a remote service.

    Generic ``SHOTSORT_AI_*`` values take precedence over provider-specific model
    variables. API keys retain their vendors' conventional environment names.
    """
    values = os.environ if env is None else env
    name = (provider or values.get("SHOTSORT_AI_PROVIDER") or "local").strip().lower()
    if name == "claude":
        name = "anthropic"
    if name == "grok":
        name = "xai"
    if name == "codex":
        # There is no Codex CLI classification API. Treat this UI alias as OpenAI.
        name = "openai"
    if name not in PROVIDERS:
        raise ValueError(f"지원하지 않는 AI 공급자입니다: {name}")

    model_vars = {
        "anthropic": "ANTHROPIC_MODEL",
        "openai": "OPENAI_MODEL",
        "xai": "XAI_MODEL",
    }
    key_vars = {
        "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
        "openai": ("OPENAI_API_KEY",),
        "xai": ("XAI_API_KEY",),
    }
    selected_model = model or values.get("SHOTSORT_AI_MODEL")
    if not selected_model and name != "local":
        selected_model = values.get(model_vars[name])
    api_key = next((values.get(k) for k in key_vars.get(name, ()) if values.get(k)), None)
    base_url = values.get("SHOTSORT_AI_BASE_URL")
    if name == "xai" and not base_url:
        base_url = "https://api.x.ai/v1"
    return ProviderConfig(name, selected_model, api_key, base_url)


def validate_config(config: ProviderConfig) -> None:
    if not config.is_remote:
        return
    if not config.model:
        raise ValueError(
            f"{config.provider} 모델을 선택하거나 SHOTSORT_AI_MODEL을 설정하세요"
        )
    if not config.api_key:
        key_name = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
                    "xai": "XAI_API_KEY"}[config.provider]
        raise ValueError(f"{key_name}가 설정되지 않았습니다")


def probe_codex_cli(*, runner: Any = subprocess.run) -> ProviderCapability:
    """Check only Codex's read-only login state; never start a paid request."""
    try:
        result = runner(["codex", "login", "status"], capture_output=True,
                        text=True, timeout=5, check=False)
    except FileNotFoundError:
        return ProviderCapability.codex_cli(available=False, reason="Codex CLI가 설치되지 않았습니다")
    except subprocess.TimeoutExpired:
        return ProviderCapability.codex_cli(available=True, reason="Codex CLI 로그인 확인 시간이 초과되었습니다")
    except OSError as exc:
        return ProviderCapability.codex_cli(available=False, reason=mask_secret(exc))
    if result.returncode != 0:
        detail = mask_secret(result.stderr or result.stdout)
        return ProviderCapability.codex_cli(available=True, reason=detail or "Codex CLI에 로그인하지 않았습니다")
    return ProviderCapability.codex_cli(available=True, logged_in=True)


def _local_plan(reason: str | None = None) -> ExecutionPlan:
    config = ProviderConfig("local")
    return ExecutionPlan(ExecutionMethod.LOCAL, config,
                         ExecutionStatus("local", ExecutionMethod.LOCAL,
                                         external_transfer=False,
                                         fallback_reason=reason))


def resolve_execution(mode: AnalysisMode | str = AnalysisMode.AUTO,
                      config: ProviderConfig | None = None, *,
                      api_consent: bool = False,
                      cli_capability: ProviderCapability | None = None,
                      runner: Any = subprocess.run) -> ExecutionPlan:
    """Choose exactly one safe execution route.

    API fallback is deliberately never a provider search: the supplied config is
    the only remote API candidate, and it is skipped until the caller records
    consent for that provider/image scope.
    """
    selected_mode = AnalysisMode(mode)
    selected_config = config or ProviderConfig("local")
    if selected_mode == AnalysisMode.LOCAL:
        return _local_plan()

    capability = cli_capability
    if selected_mode in (AnalysisMode.AUTO, AnalysisMode.CLI) and capability is None:
        capability = probe_codex_cli(runner=runner)
    if selected_mode in (AnalysisMode.AUTO, AnalysisMode.CLI) and capability and capability.ready:
        cli_config = ProviderConfig("codex", selected_config.model or "gpt-5")
        status = ExecutionStatus("codex", ExecutionMethod.CODEX_CLI, cli_config.model,
                                 external_transfer=True)
        return ExecutionPlan(ExecutionMethod.CODEX_CLI, cli_config, status, capability)
    if selected_mode == AnalysisMode.CLI:
        return _local_plan((capability.reason if capability else None) or "Codex CLI를 사용할 수 없습니다")

    wants_api = selected_mode in (AnalysisMode.AUTO, AnalysisMode.API, AnalysisMode.DIRECT)
    if wants_api and selected_config.is_remote and api_consent:
        try:
            validate_config(selected_config)
        except ValueError as exc:
            return _local_plan(mask_secret(exc))
        status = ExecutionStatus(selected_config.provider, ExecutionMethod.API,
                                 selected_config.model, external_transfer=True)
        return ExecutionPlan(ExecutionMethod.API, selected_config, status, capability)
    if wants_api and selected_config.is_remote and not api_consent:
        return _local_plan("API 외부 전송 동의가 없어 로컬 분석을 사용합니다")
    reason = capability.reason if capability and selected_mode == AnalysisMode.AUTO else None
    return _local_plan(reason)


class StructuredProvider:
    """Small common interface implemented by remote vision/text providers."""

    def generate_json(
        self, *, system: str, prompt: str, schema: dict[str, Any],
        image_b64: str | None = None, image_media_type: str = "image/jpeg",
        max_tokens: int = 1000,
    ) -> dict[str, Any]:
        raise NotImplementedError


class CodexCliProvider(StructuredProvider):
    """Codex CLI adapter using its isolated, structured-output invocation."""

    def __init__(self, config: ProviderConfig, *, runner: Any = subprocess.run,
                 timeout: float = 60):
        if config.provider != "codex":
            raise ValueError("Codex CLI 설정의 provider는 codex여야 합니다")
        self.config = config
        self.runner = runner
        self.timeout = timeout

    def generate_json(self, *, system, prompt, schema, image_b64=None,
                      image_media_type="image/jpeg", max_tokens=1000):
        del image_media_type, max_tokens  # Codex CLI receives the image as a file.
        paths: list[str] = []
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False,
                                             encoding="utf-8") as schema_file:
                json.dump(schema, schema_file)
                schema_path = schema_file.name
            paths.append(schema_path)
            command = ["codex", "exec", "--sandbox", "read-only", "--ephemeral",
                       "--output-schema", schema_path]
            if image_b64:
                try:
                    image_bytes = base64.b64decode(image_b64, validate=True)
                except (ValueError, TypeError) as exc:
                    raise StructuredOutputError("CLI 이미지 데이터가 올바르지 않습니다") from exc
                with tempfile.NamedTemporaryFile(suffix=".image", delete=False) as image_file:
                    image_file.write(image_bytes)
                    image_path = image_file.name
                paths.append(image_path)
                command.extend(["--image", image_path])
            command.append(f"{system}\n\n{prompt}")
            try:
                result = self.runner(command, capture_output=True, text=True,
                                     timeout=self.timeout, check=False)
            except FileNotFoundError as exc:
                raise CapabilityError("Codex CLI가 설치되지 않았습니다") from exc
            except subprocess.TimeoutExpired as exc:
                detail = mask_secret(getattr(exc, "stderr", ""))
                suffix = f": {detail}" if detail else ""
                raise ExecutionTimeout(f"Codex CLI 실행 시간이 초과되었습니다{suffix}") from exc
            except OSError as exc:
                raise ProviderError(mask_secret(exc)) from exc
            if result.returncode != 0:
                detail = mask_secret(result.stderr or result.stdout)
                error_type = AuthenticationError if "login" in detail.lower() else ProviderError
                raise error_type(f"Codex CLI 실행에 실패했습니다: {detail or 'unknown error'}")
            try:
                parsed = json.loads(result.stdout)
            except (TypeError, json.JSONDecodeError) as exc:
                detail = mask_secret(result.stderr)
                suffix = f": {detail}" if detail else ""
                raise StructuredOutputError(f"Codex CLI가 구조화된 JSON을 반환하지 않았습니다{suffix}") from exc
            if not isinstance(parsed, dict):
                raise StructuredOutputError("Codex CLI 결과 JSON은 객체여야 합니다")
            return parsed
        finally:
            for path in paths:
                try:
                    Path(path).unlink(missing_ok=True)
                except OSError:
                    pass


class AnthropicProvider(StructuredProvider):
    def __init__(self, config: ProviderConfig, client: Any = None):
        validate_config(config)
        self.config = config
        if client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise RuntimeError("anthropic SDK가 필요합니다") from exc
            kwargs = {"api_key": config.api_key}
            if config.base_url:
                kwargs["base_url"] = config.base_url
            client = anthropic.Anthropic(**kwargs)
        self.client = client

    def generate_json(self, *, system, prompt, schema, image_b64=None,
                      image_media_type="image/jpeg", max_tokens=1000):
        content = []
        if image_b64:
            content.append({"type": "image", "source": {"type": "base64",
                            "media_type": image_media_type, "data": image_b64}})
        content.append({"type": "text", "text": prompt})
        response = self.client.messages.create(
            model=self.config.model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        text = next(block.text for block in response.content if block.type == "text")
        return json.loads(text)


class OpenAIProvider(StructuredProvider):
    """OpenAI Responses API adapter."""

    def __init__(self, config: ProviderConfig, client: Any = None):
        validate_config(config)
        self.config = config
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("openai SDK가 필요합니다") from exc
            kwargs = {"api_key": config.api_key}
            if config.base_url:
                kwargs["base_url"] = config.base_url
            client = OpenAI(**kwargs)
        self.client = client

    def generate_json(self, *, system, prompt, schema, image_b64=None,
                      image_media_type="image/jpeg", max_tokens=1000):
        content = [{"type": "input_text", "text": prompt}]
        if image_b64:
            content.insert(0, {"type": "input_image", "image_url":
                           f"data:{image_media_type};base64,{image_b64}"})
        response = self.client.responses.create(
            model=self.config.model,
            instructions=system,
            input=[{"role": "user", "content": content}],
            max_output_tokens=max_tokens,
            text={"format": {"type": "json_schema", "name": "shotsort_result",
                              "strict": True, "schema": schema}},
        )
        return json.loads(response.output_text)


class XAIProvider(OpenAIProvider):
    """xAI adapter using its OpenAI-compatible Chat Completions surface."""

    def generate_json(self, *, system, prompt, schema, image_b64=None,
                      image_media_type="image/jpeg", max_tokens=1000):
        content = [{"type": "text", "text": prompt}]
        if image_b64:
            content.append({"type": "image_url", "image_url": {"url":
                           f"data:{image_media_type};base64,{image_b64}"}})
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": content}],
            max_tokens=max_tokens,
            response_format={"type": "json_schema", "json_schema": {
                "name": "shotsort_result", "strict": True, "schema": schema}},
        )
        return json.loads(response.choices[0].message.content)


def create_provider(config: ProviderConfig, client: Any = None) -> StructuredProvider | None:
    """Create a provider adapter. ``None`` means the offline local classifier."""
    if config.provider == "local":
        return None
    if config.provider == "codex":
        if client is not None:
            raise ValueError("Codex CLI는 SDK client를 받지 않습니다")
        return CodexCliProvider(config)
    if config.provider == "anthropic":
        return AnthropicProvider(config, client)
    if config.provider == "xai":
        return XAIProvider(config, client)
    return OpenAIProvider(config, client)
