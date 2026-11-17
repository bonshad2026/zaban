# Level policy of the conversation partner (docs/conversation-partner.md, sections 5.2 and 5.4).
# The prompt is in English, so the values here are English too. The administrator may override any level in
# the setting partner_level_policy, one line per level: level | sentence | vocab | question | correction | turn.
from dataclasses import dataclass

LEVEL_CODES = ["A1", "A2", "B1", "B2", "C1", "C2"]
POLICY_FIELDS = ["sentence", "vocab", "question", "correction", "turn"]

DEFAULT_POLICY = {
    "A1": {"sentence": "3 to 6 words", "vocab": "high-frequency words", "question": "yes/no",
           "correction": "explicit, with a short example", "turn": "one or two sentences"},
    "A2": {"sentence": "6 to 10 words", "vocab": "high-frequency and common words", "question": "yes/no and simple open",
           "correction": "explicit, less often", "turn": "two or three sentences"},
    "B1": {"sentence": "10 to 15 words", "vocab": "common words and some informal phrases", "question": "open",
           "correction": "natural recast", "turn": "three or four sentences"},
    "B2": {"sentence": "one full sentence with a linking structure", "vocab": "common and less frequent words",
           "question": "open and hypothetical", "correction": "natural recast and an informal note",
           "turn": "a few sentences with a reason"},
    "C1": {"sentence": "no fixed limit, with nuance", "vocab": "wide range, idioms, irony", "question": "open, discussion",
           "correction": "only when needed", "turn": "no fixed limit"},
    "C2": {"sentence": "no fixed limit, with nuance", "vocab": "wide range, idioms, irony", "question": "open, discussion",
           "correction": "only when needed", "turn": "no fixed limit"},
}

# Linking words by the coherence level (section 5.2).
CONNECTORS = {
    "A1": "and, but, because", "A2": "and, but, because", "B1": "so, then, after that",
    "B2": "however, although, on the other hand", "C1": "however, although, on the other hand",
    "C2": "however, although, on the other hand",
}

# How much Persian the partner may use, by the lowest of the five criteria (section 5.2).
PERSIAN_BY_LEVEL = {
    "A1": "one short Persian sentence, only to clear up confusion",
    "A2": "one short Persian sentence, only to clear up confusion",
    "B1": "one short Persian sentence, only when needed",
    "B2": "no Persian unless the learner is stuck",
    "C1": "no Persian unless the learner is stuck",
    "C2": "no Persian unless the learner is stuck",
}

CRITERIA = ["level_range", "level_accuracy", "level_fluency", "level_interaction", "level_coherence"]


@dataclass(frozen=True)
class LevelBehaviour:
    # What the partner does at this learner's levels. Each part comes from its own criterion (section 5.2).
    vocab: str
    sentence: str
    correction: str
    question: str
    turn: str
    connectors: str
    persian: str


def parse_override(text: str) -> dict[str, dict[str, str]]:
    # Reads the administrator's lines. Raises ValueError with a short reason when a line is not usable.
    rows: dict[str, dict[str, str]] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 1 + len(POLICY_FIELDS):
            raise ValueError(f"line {number} needs a level and {len(POLICY_FIELDS)} values separated by |")
        level, values = parts[0], parts[1:]
        if level not in LEVEL_CODES:
            raise ValueError(f"line {number}: the level must be one of {', '.join(LEVEL_CODES)}")
        if not all(values) or any(len(value) > 200 for value in values):
            raise ValueError(f"line {number}: every value must be filled in and at most 200 characters")
        rows[level] = dict(zip(POLICY_FIELDS, values))
    return rows


def policy_table(override_text: str) -> dict[str, dict[str, str]]:
    # The default table with the administrator's lines written over it.
    table = {level: dict(values) for level, values in DEFAULT_POLICY.items()}
    table.update(parse_override(override_text))
    return table


def behaviour_for(table: dict[str, dict[str, str]], criteria: dict[str, str]) -> LevelBehaviour:
    # criteria maps each criterion name to a level code. Missing or unknown levels fall back to A1.
    def level_of(name: str) -> str:
        value = criteria.get(name, "A1")
        return value if value in LEVEL_CODES else "A1"

    lowest = min((level_of(name) for name in CRITERIA), key=LEVEL_CODES.index)
    return LevelBehaviour(
        vocab=table[level_of("level_range")]["vocab"],
        sentence=table[level_of("level_accuracy")]["sentence"],
        correction=table[level_of("level_accuracy")]["correction"],
        question=table[level_of("level_interaction")]["question"],
        turn=table[level_of("level_fluency")]["turn"],
        connectors=CONNECTORS[level_of("level_coherence")],
        persian=PERSIAN_BY_LEVEL[lowest],
    )
