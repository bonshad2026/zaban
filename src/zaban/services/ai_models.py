# The chat models the admin panel offers. Prices are in US dollars per million tokens, as listed by the provider.
# Any other model name can still be typed in the panel, so this list is a choice, not a limit.
CHAT_MODELS = [
    {"id": "gpt-6-luna", "provider": "OpenAI", "input": 0.10, "output": 0.50},
    {"id": "gpt-5.6-luna", "provider": "OpenAI", "input": 0.20, "output": 1.20},
    {"id": "gpt-6-sol", "provider": "OpenAI", "input": 2.00, "output": 10.00},
    {"id": "gpt-6.1-sol", "provider": "OpenAI", "input": 2.00, "output": 10.00},
    {"id": "gpt-6.1-terra", "provider": "OpenAI", "input": 1.00, "output": 5.00},
    {"id": "gpt-5.6-terra", "provider": "OpenAI", "input": 2.00, "output": 12.00},
    {"id": "gpt-5.6-sol", "provider": "OpenAI", "input": 2.50, "output": 15.00},
    {"id": "gpt-5.5", "provider": "OpenAI", "input": 5.00, "output": 30.00},
    {"id": "gpt-5.4", "provider": "OpenAI", "input": 2.50, "output": 15.00},
    {"id": "gpt-5.2-pro", "provider": "OpenAI", "input": 21.00, "output": 126.00},
    {"id": "claude-sonnet-5-5", "provider": "Anthropic", "input": 2.00, "output": 10.00},
    {"id": "claude-opus-5-5", "provider": "Anthropic", "input": 4.00, "output": 20.00},
    {"id": "claude-opus-5", "provider": "Anthropic", "input": 5.00, "output": 25.00},
    {"id": "claude-fable-5-1", "provider": "Anthropic", "input": 10.00, "output": 50.00},
    {"id": "gemini-3.1-pro-preview", "provider": "Google", "input": 2.00, "output": 12.00},
    {"id": "gapgpt-deepseek-v4.1-flash", "provider": "GapGPT", "input": 0.15, "output": 0.60},
    {"id": "gapgpt-gemma-26b-a4b", "provider": "GapGPT", "input": 0.08, "output": 0.32},
]


def prices_for(model: str) -> tuple[float, float] | None:
    # Input and output price per million tokens for a model from the list, or None when the model is not listed.
    for entry in CHAT_MODELS:
        if entry["id"] == model:
            return entry["input"], entry["output"]
    return None
