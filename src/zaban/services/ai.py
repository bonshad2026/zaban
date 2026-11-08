from dataclasses import dataclass

from zaban.config import settings
from zaban.services.ai_gateway import complete


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
    result = complete(system_prompt, messages, max_tokens=300)
    return TutorReply(
        text=result.text,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        mode=result.mode,
    )
