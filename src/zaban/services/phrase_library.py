# The phrase library (docs/conversation-partner.md, section 8). Phrases are compared without case and punctuation.
import re

from sqlalchemy.orm import Session as DBSession

from zaban.models import CurriculumTopic, CurriculumVariant, PhraseItem
from zaban.services.partner_settings import LEVEL_CODES
from zaban.services.settings_store import get_setting, set_setting

PHRASE_SEED_KEY = "partner_phrases_seeded"


def phrase_key(text: str) -> str:
    # "I'm particularly interested in…" and "im particularly interested in" give the same key.
    return " ".join(re.sub(r"[^\w\s]", "", text.lower()).split())


def add_phrase(db: DBSession, text: str, level: str, situation: str = "", register: str = "neutral", source: str = "admin") -> PhraseItem | None:
    # Returns None when the library already has the phrase, so the same phrase is never stored twice.
    key = phrase_key(text)
    if not key or db.query(PhraseItem).filter(PhraseItem.text_key == key).first() is not None:
        return None
    item = PhraseItem(text=text.strip(), text_key=key, level=level, situation=situation, register=register, source=source)
    db.add(item)
    return item


def seed_phrase_library(db: DBSession) -> None:
    # Fills the library once from the phrases of the curriculum variants. Later additions come from the review queue.
    if get_setting(db, PHRASE_SEED_KEY):
        return
    for variant in db.query(CurriculumVariant).all():
        topic = db.get(CurriculumTopic, variant.topic_id)
        situation = topic.title if topic else ""
        for phrase in variant.phrases or []:
            if isinstance(phrase, str) and variant.level in LEVEL_CODES:
                add_phrase(db, phrase, variant.level, situation=situation, source="curriculum")
    db.flush()
    set_setting(db, PHRASE_SEED_KEY, "1")
    db.commit()
