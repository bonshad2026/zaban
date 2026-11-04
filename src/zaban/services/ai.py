from dataclasses import dataclass

import anthropic

from zaban.config import settings


@dataclass(frozen=True)
class TutorReply:
    text: str
    input_tokens: int
    output_tokens: int
    mode: str  # "live" when Claude answered, "offline" when no API key is configured


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * settings.input_price_per_mtok + output_tokens * settings.output_price_per_mtok
    ) / 1_000_000


def tutor_reply(system_prompt: str, messages: list[dict]) -> TutorReply:
    # The Messages API expects the conversation to start with a user turn.
    if not messages or messages[0]["role"] != "user":
        messages = [{"role": "user", "content": "Hi, I am ready to start the lesson."}] + messages

    if not settings.anthropic_api_key:
        return _offline_reply(messages)

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.model,
        max_tokens=300,
        system=system_prompt,
        messages=messages,
    )
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    return TutorReply(
        text=text,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        mode="live",
    )


def _offline_reply(messages: list[dict]) -> TutorReply:
    last = messages[-1]["content"]
    text = f'Nice try! You said: "{last[:60]}". Can you tell me one more thing about your day?'
    return TutorReply(
        text=text,
        input_tokens=len(last) // 4 + 1,
        output_tokens=len(text) // 4 + 1,
        mode="offline",
    )
