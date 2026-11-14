import json
from collections.abc import Iterator
from dataclasses import dataclass

import anthropic
import httpx

from zaban.config import settings
from zaban.db import SessionLocal
from zaban.services.settings_store import (
    AI_API_KEY_KEY,
    AI_BASE_URL_KEY,
    AI_MODEL_KEY,
    AI_PROVIDER_KEY,
    get_setting,
)

# The one place that talks to the language model. Tutor lessons, self-tests and any future feature call this,
# so the provider, model and key are set in one spot. Nothing here knows about students or sessions.
# The provider, key, address and model come from the admin panel first, and from the environment when a setting is empty.
@dataclass(frozen=True)
class AIResult:
    text: str
    input_tokens: int
    output_tokens: int
    mode: str  # "live" when the model answered, "offline" when no key or model is configured


@dataclass(frozen=True)
class AIConfig:
    provider: str  # "anthropic" or "openai" (any OpenAI-compatible service)
    api_key: str | None
    base_url: str
    model: str

    @property
    def ready(self) -> bool:
        return bool(self.api_key and self.model)


def current_config() -> AIConfig:
    with SessionLocal() as db:
        provider = (get_setting(db, AI_PROVIDER_KEY, settings.ai_provider) or "anthropic").strip().lower()
        if provider == "openai":
            api_key = get_setting(db, AI_API_KEY_KEY, settings.openai_api_key or "")
            model = get_setting(db, AI_MODEL_KEY, settings.openai_model or "")
            base_url = get_setting(db, AI_BASE_URL_KEY, settings.openai_base_url)
        else:
            provider = "anthropic"
            api_key = get_setting(db, AI_API_KEY_KEY, settings.anthropic_api_key or "")
            model = get_setting(db, AI_MODEL_KEY, settings.model)
            base_url = settings.openai_base_url
    return AIConfig(provider=provider, api_key=api_key or None, base_url=base_url.rstrip("/"), model=model)


def complete(system_prompt: str, messages: list[dict], max_tokens: int = 300) -> AIResult:
    # The Messages API expects the conversation to start with a user turn.
    if not messages or messages[0]["role"] != "user":
        messages = [{"role": "user", "content": "Hi, I am ready to start."}] + messages

    config = current_config()
    if not config.ready:
        return _offline(messages)
    if config.provider == "openai":
        return _openai_complete(config, system_prompt, messages, max_tokens)

    client = anthropic.Anthropic(api_key=config.api_key)
    response = client.messages.create(
        model=config.model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=messages,
    )
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    return AIResult(
        text=text,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        mode="live",
    )


def stream_complete(system_prompt: str, messages: list[dict], usage: dict, max_tokens: int = 300) -> Iterator[str]:
    # Same model and key as complete(), but the text is sent in pieces as it is written.
    # The token counts are put in usage once the reply has ended.
    if not messages or messages[0]["role"] != "user":
        messages = [{"role": "user", "content": "Hi, I am ready to start."}] + messages

    config = current_config()
    if not config.ready:
        result = _offline(messages)
        usage.update(input_tokens=result.input_tokens, output_tokens=result.output_tokens)
        for word in result.text.split(" "):
            yield word + " "
        return
    if config.provider == "openai":
        yield from _openai_stream(config, system_prompt, messages, usage, max_tokens)
        return

    client = anthropic.Anthropic(api_key=config.api_key)
    with client.messages.stream(
        model=config.model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=messages,
    ) as stream:
        for piece in stream.text_stream:
            yield piece
        final = stream.get_final_message()
    usage.update(input_tokens=final.usage.input_tokens, output_tokens=final.usage.output_tokens)


def _openai_url(config: AIConfig) -> str:
    return f"{config.base_url}/chat/completions"


def _openai_headers(config: AIConfig) -> dict:
    return {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}


def _openai_body(config: AIConfig, system_prompt: str, messages: list[dict], max_tokens: int, stream: bool) -> dict:
    body = {
        "model": config.model,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "max_completion_tokens": max_tokens,
        "stream": stream,
    }
    if stream:
        body["stream_options"] = {"include_usage": True}
    return body


def _openai_complete(config: AIConfig, system_prompt: str, messages: list[dict], max_tokens: int) -> AIResult:
    response = httpx.post(_openai_url(config), headers=_openai_headers(config),
                          json=_openai_body(config, system_prompt, messages, max_tokens, stream=False), timeout=60)
    response.raise_for_status()
    data = response.json()
    text = (data["choices"][0]["message"].get("content") or "").strip()
    return AIResult(
        text=text,
        input_tokens=data["usage"]["prompt_tokens"],
        output_tokens=data["usage"]["completion_tokens"],
        mode="live",
    )


def _openai_stream(config: AIConfig, system_prompt: str, messages: list[dict], usage: dict, max_tokens: int) -> Iterator[str]:
    body = _openai_body(config, system_prompt, messages, max_tokens, stream=True)
    with httpx.stream("POST", _openai_url(config), headers=_openai_headers(config), json=body, timeout=60) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[len("data: "):]
            if payload.strip() == "[DONE]":
                break
            chunk = json.loads(payload)
            if chunk.get("usage"):
                usage.update(input_tokens=chunk["usage"]["prompt_tokens"], output_tokens=chunk["usage"]["completion_tokens"])
            for choice in chunk.get("choices", []):
                piece = choice.get("delta", {}).get("content")
                if piece:
                    yield piece


def _offline(messages: list[dict]) -> AIResult:
    last = messages[-1]["content"]
    text = f'Nice try! You said: "{last[:60]}". Can you tell me one more thing about your day?'
    return AIResult(
        text=text,
        input_tokens=len(last) // 4 + 1,
        output_tokens=len(text) // 4 + 1,
        mode="offline",
    )
