# The content library of the conversation partner (docs/conversation-partner.md, sections 4.5, 4.12 and 8.1).
# Stories, poems and listening texts. The partner uses an item of the learner's level when one is active,
# and otherwise writes its own text (the system's own texts need no licence).
from sqlalchemy.orm import Session as DBSession

from zaban.models import ContentItem, Student
from zaban.services.partner_policy import LEVEL_CODES

KINDS = ["story", "poem", "listening"]
# The mode that uses each kind of content.
KIND_OF_MODE = {"story": "story", "poetry": "poem", "listening": "listening"}
MAX_TEXT_LENGTH = 6000


def validate_item(kind: str, level: str, title: str, text: str, source: str, licence: str) -> None:
    # Raises ValueError with a short reason. A text needs its source and its licence to be stored.
    if kind not in KINDS:
        raise ValueError("kind must be story, poem or listening")
    if level not in LEVEL_CODES:
        raise ValueError("level must be A1 to C2")
    if not title.strip() or not text.strip():
        raise ValueError("title and text are needed")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"text is longer than {MAX_TEXT_LENGTH} characters")
    if not source.strip() or not licence.strip():
        raise ValueError("source and licence are both needed")


def add_item(db: DBSession, kind: str, level: str, title: str, text: str, source: str, licence: str) -> ContentItem:
    validate_item(kind, level, title, text, source, licence)
    item = ContentItem(kind=kind, level=level, title=title.strip(), text=text.strip(), source=source.strip(), licence=licence.strip())
    db.add(item)
    return item


def active_item(db: DBSession, mode: str, student: Student) -> ContentItem | None:
    # The newest active text of the learner's level, or of a lower level when none exists at that level.
    kind = KIND_OF_MODE.get(mode)
    if kind is None:
        return None
    allowed = LEVEL_CODES[: LEVEL_CODES.index(student.level_range or "A1") + 1]
    items = (
        db.query(ContentItem)
        .filter(ContentItem.kind == kind, ContentItem.active.is_(True), ContentItem.level.in_(allowed))
        .order_by(ContentItem.id.desc())
        .all()
    )
    if not items:
        return None
    best = max(LEVEL_CODES.index(item.level) for item in items)
    return next(item for item in items if LEVEL_CODES.index(item.level) == best)
