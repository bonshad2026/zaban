from dataclasses import dataclass

from zaban.config import settings
from zaban.services.ai_gateway import complete


@dataclass(frozen=True)
class TutorReply:
    text: str
    input_tokens: int
    output_tokens: int
    mode: str  # "live" when Claude answered, "offline" when no API key is configured


def estimate_cost(input_tokens: int, output_tokens: int, prices: tuple[float, float] | None = None) -> float:
    # prices are (input, output) per million tokens of the model that answered. Without them the environment prices are used.
    input_price, output_price = prices or (settings.input_price_per_mtok, settings.output_price_per_mtok)
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


def tutor_reply(system_prompt: str, messages: list[dict]) -> TutorReply:
    result = complete(system_prompt, messages, max_tokens=300)
    return TutorReply(
        text=result.text,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        mode=result.mode,
    )
