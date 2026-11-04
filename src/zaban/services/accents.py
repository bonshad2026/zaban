# The English accents a learner can practise. The first one is the default.
# The note tells the lesson model which spelling and everyday words fit that accent.
ACCENTS = {
    "en-US": (
        "American",
        "American spelling (color, favorite, apartment) and everyday American words (truck, vacation, cookie).",
    ),
    "en-GB": (
        "British",
        "British spelling (colour, favourite, flat) and everyday British words (lorry, holiday, biscuit).",
    ),
    "en-AU": (
        "Australian",
        "British-style spelling, with everyday Australian words now and then (arvo, brekkie, mate).",
    ),
    "en-CA": (
        "Canadian",
        "Mostly American spelling, with some British words such as colour and centre.",
    ),
}

DEFAULT_ACCENT = "en-US"


def accent_note(code: str) -> str:
    _, note = ACCENTS.get(code, ACCENTS[DEFAULT_ACCENT])
    return note
