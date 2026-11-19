from dataclasses import dataclass

from zaban.services.ai_gateway import complete


@dataclass(frozen=True)
class TutorReply:
    text: str
    input_tokens: int
    output_tokens: int
    mode: str  # "live" when Claude answered, "offline" when no API key is configured
    stop_reason: str | None = None


def estimate_cost(input_tokens: int, output_tokens: int, prices: tuple[float, float]) -> float:
    # prices are (input, output) per million tokens of the model that answered.
    input_price, output_price = prices
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


def tutor_reply(system_prompt: str, messages: list[dict]) -> TutorReply:
    # The partner answers in one JSON object (reply, feedback, new phrase, next action). 300 tokens cut long answers short.
    result = complete(system_prompt, messages, max_tokens=1200)
    return TutorReply(
        text=result.text,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        mode=result.mode,
        stop_reason=result.stop_reason,
    )
