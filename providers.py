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
CLI_PROVIDERS = ("codex", "claude")


class AnalysisMode(str, Enum):
    AUTO = "auto"
    LOCAL = "local"
    CLI = "cli"
    API = "api"
    DIRECT = "direct"


class ExecutionMethod(str, Enum):
    LOCAL = "local"
    CODEX_CLI = "codex_cli"
    CLAUDE_CLI = "claude_cli"
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

    def ready_for(self, *, with_image: bool) -> bool:
        return (self.available and self.logged_in and self.supports_structured_output
                and (not with_image or self.supports_images))

    @classmethod
    def codex_cli(cls, *, available: bool, logged_in: bool = False,
                  supports_images: bool = True,
                  supports_structured_output: bool = True,
                  reason: str | None = None) -> "ProviderCapability":
        return cls(available, logged_in, supports_images,
                   supports_structured_output, reason)

    @classmethod
    def claude_cli(cls, *, available: bool, logged_in: bool = False,
                   supports_structured_output: bool = True,
                   reason: str | None = None) -> "ProviderCapability":
        return cls(available, logged_in, False, supports_structured_output, reason)


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
    """비용이 드는 요청 없이 Codex CLI의 실행 계약과 로그인 상태를 확인한다."""
    try:
        help_result = runner(["codex", "exec", "--help"], capture_output=True,
                             text=True, timeout=5, check=False)
    except FileNotFoundError:
        return ProviderCapability.codex_cli(available=False, reason="Codex CLI가 설치되지 않았습니다")
    except subprocess.TimeoutExpired:
        return ProviderCapability.codex_cli(available=True, reason="Codex CLI 기능 확인 시간이 초과되었습니다")
    except OSError as exc:
        return ProviderCapability.codex_cli(available=False, reason=mask_secret(exc))
    if help_result.returncode != 0:
        detail = mask_secret(help_result.stderr or help_result.stdout)
        return ProviderCapability.codex_cli(available=True, reason=detail or "Codex CLI 기능을 확인할 수 없습니다")
    help_text = f"{help_result.stdout}\n{help_result.stderr}"
    missing = []
    if "--image" not in help_text:
        missing.append("이미지 입력")
    if "--output-schema" not in help_text:
        missing.append("구조화 출력")
    if missing:
        return ProviderCapability.codex_cli(
            available=True,
            supports_images="이미지 입력" not in missing,
            supports_structured_output="구조화 출력" not in missing,
            reason=f"Codex CLI가 {' 및 '.join(missing)}을 지원하지 않습니다",
        )
    try:
        result = runner(["codex", "login", "status"], capture_output=True,
                        text=True, timeout=5, check=False)
    except subprocess.TimeoutExpired:
        return ProviderCapability.codex_cli(available=True, reason="Codex CLI 로그인 확인 시간이 초과되었습니다")
    except OSError as exc:
        return ProviderCapability.codex_cli(available=True, reason=mask_secret(exc))
    if result.returncode != 0:
        detail = mask_secret(result.stderr or result.stdout)
        return ProviderCapability.codex_cli(available=True, reason=detail or "Codex CLI에 로그인하지 않았습니다")
    return ProviderCapability.codex_cli(available=True, logged_in=True)


def probe_claude_cli(*, runner: Any = subprocess.run) -> ProviderCapability:
    """Check Claude Code's non-interactive structured-output contract safely.

    Claude Code currently has no local image attachment option.  It remains a
    valid OCR-text-only adapter, but is never selected when image transfer is
    requested.
    """
    try:
        help_result = runner(["claude", "--help"], capture_output=True, text=True,
                             timeout=5, check=False)
    except FileNotFoundError:
        return ProviderCapability.claude_cli(available=False, reason="Claude CLI가 설치되지 않았습니다")
    except subprocess.TimeoutExpired:
        return ProviderCapability.claude_cli(available=True, reason="Claude CLI 기능 확인 시간이 초과되었습니다")
    except OSError as exc:
        return ProviderCapability.claude_cli(available=False, reason=mask_secret(exc))
    if help_result.returncode != 0:
        detail = mask_secret(help_result.stderr or help_result.stdout)
        return ProviderCapability.claude_cli(available=True, reason=detail or "Claude CLI 기능을 확인할 수 없습니다")
    help_text = f"{help_result.stdout}\n{help_result.stderr}"
    missing = [flag for flag in ("-p", "--json-schema", "--output-format") if flag not in help_text]
    if missing:
        return ProviderCapability.claude_cli(
            available=True, supports_structured_output=False,
            reason=f"Claude CLI가 {', '.join(missing)}을 지원하지 않습니다",
        )
    try:
        result = runner(["claude", "auth", "status"], capture_output=True, text=True,
                        timeout=5, check=False)
    except subprocess.TimeoutExpired:
        return ProviderCapability.claude_cli(available=True, reason="Claude CLI 로그인 확인 시간이 초과되었습니다")
    except OSError as exc:
        return ProviderCapability.claude_cli(available=True, reason=mask_secret(exc))
    if result.returncode != 0:
        detail = mask_secret(result.stderr or result.stdout)
        return ProviderCapability.claude_cli(available=True, reason=detail or "Claude CLI에 로그인하지 않았습니다")
    try:
        logged_in = bool(json.loads(result.stdout).get("loggedIn"))
    except (TypeError, json.JSONDecodeError):
        logged_in = "logged" in (result.stdout or "").lower()
    if not logged_in:
        return ProviderCapability.claude_cli(available=True, reason="Claude CLI에 로그인하지 않았습니다")
    return ProviderCapability.claude_cli(available=True, logged_in=True)


def probe_cli_capabilities(*, runner: Any = subprocess.run) -> dict[str, ProviderCapability]:
    """Return safe capability facts for every supported CLI, without AI calls."""
    return {"codex": probe_codex_cli(runner=runner),
            "claude": probe_claude_cli(runner=runner)}


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
                      cli_capabilities: Mapping[str, ProviderCapability] | None = None,
                      with_image: bool = False,
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

    capabilities = dict(cli_capabilities or {})
    if cli_capability is not None:  # P1 caller compatibility.
        capabilities.setdefault("codex", cli_capability)
    if selected_mode in (AnalysisMode.AUTO, AnalysisMode.CLI) and "codex" not in capabilities:
        capabilities["codex"] = probe_codex_cli(runner=runner)
    capability = capabilities.get("codex")
    if selected_mode in (AnalysisMode.AUTO, AnalysisMode.CLI) and capability and capability.ready_for(with_image=with_image):
        cli_config = ProviderConfig("codex", selected_config.model or "gpt-5")
        status = ExecutionStatus("codex", ExecutionMethod.CODEX_CLI, cli_config.model,
                                 external_transfer=True)
        return ExecutionPlan(ExecutionMethod.CODEX_CLI, cli_config, status, capability)
    if (selected_mode in (AnalysisMode.AUTO, AnalysisMode.CLI)
            and cli_capability is None and "claude" not in capabilities):
        capabilities["claude"] = probe_claude_cli(runner=runner)
    claude_capability = capabilities.get("claude")
    if selected_mode in (AnalysisMode.AUTO, AnalysisMode.CLI) and claude_capability and claude_capability.ready_for(with_image=with_image):
        cli_config = ProviderConfig("claude")
        status = ExecutionStatus("claude", ExecutionMethod.CLAUDE_CLI,
                                 external_transfer=True)
        return ExecutionPlan(ExecutionMethod.CLAUDE_CLI, cli_config, status, claude_capability)
    if selected_mode == AnalysisMode.CLI:
        reasons = [item.reason for item in capabilities.values() if item and item.reason]
        if with_image and claude_capability and not claude_capability.supports_images:
            reasons.append("Claude CLI는 이미지 입력을 지원하지 않습니다")
        return _local_plan("; ".join(reasons) or "사용 가능한 AI CLI가 없습니다")

    wants_api = selected_mode in (AnalysisMode.AUTO, AnalysisMode.API, AnalysisMode.DIRECT)
    # 자동 모드에서 API 공급자의 기본 모델명을 Codex CLI에 넘기면 안 된다.
    # CLI 경로가 제외된 뒤에만 기존 Anthropic 기본값을 적용해 API fallback도
    # 모델명을 직접 입력하지 않고 사용할 수 있게 한다.
    if wants_api and selected_config.provider == "anthropic" and not selected_config.model:
        selected_config = ProviderConfig(
            selected_config.provider, "claude-opus-4-8", selected_config.api_key,
            selected_config.base_url,
        )
    if wants_api and selected_config.is_remote and api_consent:
        try:
            validate_config(selected_config)
        except ValueError as exc:
            return _local_plan(mask_secret(exc))
        status = ExecutionStatus(selected_config.provider, ExecutionMethod.API,
                                 selected_config.model, external_transfer=True)
        return ExecutionPlan(ExecutionMethod.API, selected_config, status, capability)
    if wants_api and selected_config.is_remote and not api_consent:
        reasons = [item.reason for item in capabilities.values() if item and item.reason]
        if with_image and claude_capability and not claude_capability.supports_images:
            reasons.append("Claude CLI는 이미지 입력을 지원하지 않습니다")
        reasons.append("API 외부 전송 동의가 없어 로컬 분석을 사용합니다")
        return _local_plan("; ".join(reasons))
    reasons = [item.reason for item in capabilities.values() if item and item.reason]
    if with_image and claude_capability and not claude_capability.supports_images:
        reasons.append("Claude CLI는 이미지 입력을 지원하지 않습니다")
    reason = "; ".join(reasons) if selected_mode == AnalysisMode.AUTO else None
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


class ClaudeCliProvider(StructuredProvider):
    """Claude Code adapter for OCR-text-only structured classification."""

    def __init__(self, config: ProviderConfig, *, runner: Any = subprocess.run,
                 timeout: float = 60):
        if config.provider != "claude":
            raise ValueError("Claude CLI 설정의 provider는 claude여야 합니다")
        self.config = config
        self.runner = runner
        self.timeout = timeout

    def generate_json(self, *, system, prompt, schema, image_b64=None,
                      image_media_type="image/jpeg", max_tokens=1000):
        del image_media_type, max_tokens
        if image_b64:
            raise CapabilityError("Claude CLI는 로컬 이미지 입력을 지원하지 않습니다")
        command = ["claude", "-p", "--output-format", "json", "--json-schema",
                   json.dumps(schema, ensure_ascii=False), "--no-session-persistence",
                   "--tools", ""]
        if self.config.model:
            command.extend(["--model", self.config.model])
        command.append(f"{system}\n\n{prompt}")
        try:
            result = self.runner(command, capture_output=True, text=True,
                                 timeout=self.timeout, check=False)
        except FileNotFoundError as exc:
            raise CapabilityError("Claude CLI가 설치되지 않았습니다") from exc
        except subprocess.TimeoutExpired as exc:
            detail = mask_secret(getattr(exc, "stderr", ""))
            suffix = f": {detail}" if detail else ""
            raise ExecutionTimeout(f"Claude CLI 실행 시간이 초과되었습니다{suffix}") from exc
        except OSError as exc:
            raise ProviderError(mask_secret(exc)) from exc
        if result.returncode != 0:
            detail = mask_secret(result.stderr or result.stdout)
            error_type = AuthenticationError if "auth" in detail.lower() or "login" in detail.lower() else ProviderError
            raise error_type(f"Claude CLI 실행에 실패했습니다: {detail or 'unknown error'}")
        try:
            parsed = json.loads(result.stdout)
            if isinstance(parsed, dict) and isinstance(parsed.get("result"), str):
                parsed = json.loads(parsed["result"])
        except (TypeError, json.JSONDecodeError) as exc:
            detail = mask_secret(result.stderr)
            suffix = f": {detail}" if detail else ""
            raise StructuredOutputError(f"Claude CLI가 구조화된 JSON을 반환하지 않았습니다{suffix}") from exc
        if not isinstance(parsed, dict):
            raise StructuredOutputError("Claude CLI 결과 JSON은 객체여야 합니다")
        return parsed


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
    if config.provider == "claude":
        if client is not None:
            raise ValueError("Claude CLI는 SDK client를 받지 않습니다")
        return ClaudeCliProvider(config)
    if config.provider == "anthropic":
        return AnthropicProvider(config, client)
    if config.provider == "xai":
        return XAIProvider(config, client)
    return OpenAIProvider(config, client)
