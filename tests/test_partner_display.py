# A stored answer is JSON. The learner must see only its reply, both when the lesson is shown again and in the conversation history.
import json

from zaban.services.partner_output import shown_text

REPLY = "Great! What do you enjoy doing in your free time? Tell me why you like it."
STORED = json.dumps(
    {"mode": "conversation", "reply": REPLY, "feedback": None, "new_phrase": None, "target": None, "next_action": "ask_learner"}
)


def test_valid_stored_answer_shows_only_the_reply():
    assert shown_text(STORED) == REPLY


def test_answer_in_a_code_fence_shows_only_the_reply():
    assert shown_text("```json\n" + STORED + "\n```") == REPLY


def test_invalid_answer_is_shown_as_it_was():
    assert shown_text("plain text from the model") == "plain text from the model"


def test_answer_without_reply_is_shown_as_it_was():
    raw = json.dumps({"mode": "conversation", "feedback": None})
    assert shown_text(raw) == raw
