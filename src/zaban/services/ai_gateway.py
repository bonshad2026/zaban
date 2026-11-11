from collections.abc import Iterator
from dataclasses import dataclass

import anthropic

from zaban.config import settings


# The one place that talks to the language model. Tutor lessons, self-tests and any future feature call this,
# so the provider, model and key are set in one spot. Nothing here knows about students or sessions.
@dataclass(frozen=True)
class AIResult:
    text: str
    input_tokens: int
    output_tokens: int
    mode: str  # "live" when the model answered, "offline" when no API key is configured


def complete(system_prompt: str, messages: list[dict], max_tokens: int = 300) -> AIResult:
    # The Messages API expects the conversation to start with a user turn.
    if not messages or messages[0]["role"] != "user":
        messages = [{"role": "user", "content": "Hi, I am ready to start."}] + messages

    if not settings.anthropic_api_key:
        return _offline(messages)

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.model,
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


def _offline(messages: list[dict]) -> AIResult:
    last = messages[-1]["content"]
    text = f'Nice try! You said: "{last[:60]}". Can you tell me one more thing about your day?'
    return AIResult(
        text=text,
        input_tokens=len(last) // 4 + 1,
        output_tokens=len(text) // 4 + 1,
        mode="offline",
    )


def stream_complete(system_prompt: str, messages: list[dict], usage: dict, max_tokens: int = 300) -> Iterator[str]:
    # Same model and key as complete(), but the text is sent in pieces as it is written.
    # The token counts are put in usage once the reply has ended.
    if not messages or messages[0]["role"] != "user":
        messages = [{"role": "user", "content": "Hi, I am ready to start."}] + messages

    if not settings.anthropic_api_key:
        result = _offline(messages)
        usage.update(input_tokens=result.input_tokens, output_tokens=result.output_tokens)
        for word in result.text.split(" "):
            yield word + " "
        return

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    with client.messages.stream(
        model=settings.model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=messages,
    ) as stream:
        for piece in stream.text_stream:
            yield piece
        final = stream.get_final_message()
    usage.update(input_tokens=final.usage.input_tokens, output_tokens=final.usage.output_tokens)
