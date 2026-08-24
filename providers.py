"""Provider-neutral structured AI calls for screenshot classification.

The module deliberately does not guess a vendor's newest model.  Remote providers
require an explicit model (argument or environment variable), which keeps model
availability and pricing decisions with the user.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping


PROVIDERS = ("local", "anthropic", "openai", "xai")


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


class StructuredProvider:
    """Small common interface implemented by remote vision/text providers."""

    def generate_json(
        self, *, system: str, prompt: str, schema: dict[str, Any],
        image_b64: str | None = None, image_media_type: str = "image/jpeg",
        max_tokens: int = 1000,
    ) -> dict[str, Any]:
        raise NotImplementedError


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
    if config.provider == "anthropic":
        return AnthropicProvider(config, client)
    if config.provider == "xai":
        return XAIProvider(config, client)
    return OpenAIProvider(config, client)
