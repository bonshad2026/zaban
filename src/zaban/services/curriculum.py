from sqlalchemy.orm import Session as DBSession

from zaban.curriculum_data import BAND_CODES, BAND_LABELS, LEVELS, TOPICS, VARIANTS
from zaban.models import AppSetting, CurriculumTopic, CurriculumVariant, LessonTopic, Student, TutorSession

VERSION_KEY = "curriculum_version"
# Used when a learner has no level yet. It matches the lesson prompt, which assumes A2 in that case.
DEFAULT_LEVEL = "A2"
# A learner does not get the same topic again until this many lessons have passed.
RECENT_LIMIT = 5

_TOPIC_ORDER = {row[0]: index for index, row in enumerate(TOPICS)}


def ordered_topics(db: DBSession) -> list[CurriculumTopic]:
    return sorted(db.query(CurriculumTopic).all(), key=lambda t: _TOPIC_ORDER.get(t.id, len(_TOPIC_ORDER)))


def band_code(age_band: str) -> str | None:
    for code, value in BAND_CODES.items():
        if value == age_band:
            return code
    return None


def topic_levels(topic: CurriculumTopic) -> list[str]:
    return LEVELS[LEVELS.index(topic.first_level) : LEVELS.index(topic.last_level) + 1]


def catalog_version(db: DBSession) -> int:
    row = db.get(AppSetting, VERSION_KEY)
    return int(row.value) if row and row.value.isdigit() else 1


def bump_catalog_version(db: DBSession) -> int:
    version = catalog_version(db) + 1
    row = db.get(AppSetting, VERSION_KEY)
    if row is None:
        db.add(AppSetting(key=VERSION_KEY, value=str(version)))
    else:
        row.value = str(version)
    return version


def seed_curriculum(db: DBSession) -> None:
    # Adds topics and variants that are missing. Rows the administrator already changed are never overwritten.
    for topic_id, title, goal, first, last, bands in TOPICS:
        if db.get(CurriculumTopic, topic_id) is None:
            db.add(CurriculumTopic(id=topic_id, title=title, goal=goal, first_level=first, last_level=last, bands=bands))
    db.flush()
    for variant_id, topic_id, band, level, opener, phrases, style in VARIANTS:
        if db.get(CurriculumVariant, variant_id) is None:
            db.add(
                CurriculumVariant(
                    id=variant_id, topic_id=topic_id, band=band, level=level, opener=opener, phrases=phrases, style=style
                )
            )
    if db.get(AppSetting, VERSION_KEY) is None:
        db.add(AppSetting(key=VERSION_KEY, value="1"))
    db.commit()


def variant_for(db: DBSession, topic_id: str, band: str, level: str) -> CurriculumVariant | None:
    return db.get(CurriculumVariant, f"{topic_id}.{band}.{level}")


def _recent_topic_ids(db: DBSession, student_id: str) -> set[str]:
    rows = (
        db.query(LessonTopic.topic_id)
        .join(TutorSession, TutorSession.id == LessonTopic.session_id)
        .filter(TutorSession.student_id == student_id)
        .order_by(LessonTopic.created_at.desc())
        .limit(RECENT_LIMIT)
        .all()
    )
    return {row[0] for row in rows}


def _fits(topic: CurriculumTopic, band: str, level: str) -> bool:
    return band in topic.bands and level in topic_levels(topic)


def choose_topic(
    db: DBSession, student: Student, requested: str | None = None
) -> tuple[CurriculumTopic, CurriculumVariant] | None:
    # Picks the next topic for a learner: one that fits their age band and level and has a written variant.
    # With no request, topics used in the last few lessons come last, so the lessons keep moving forward.
    band = band_code(student.age_band)
    if band is None:
        return None
    level = student.cefr_level or DEFAULT_LEVEL

    if requested:
        topic = db.get(CurriculumTopic, requested)
        if topic is None or not _fits(topic, band, level):
            return None
        variant = variant_for(db, topic.id, band, level)
        return (topic, variant) if variant else None

    recent = _recent_topic_ids(db, student.id)
    fallback = None
    for topic in ordered_topics(db):
        if not _fits(topic, band, level):
            continue
        variant = variant_for(db, topic.id, band, level)
        if variant is None:
            continue
        if topic.id not in recent:
            return topic, variant
        fallback = fallback or (topic, variant)
    return fallback


def record_lesson_topic(db: DBSession, session_id: str, topic: CurriculumTopic, variant: CurriculumVariant) -> None:
    db.add(
        LessonTopic(
            session_id=session_id,
            topic_id=topic.id,
            variant_id=variant.id,
            catalog_version=catalog_version(db),
        )
    )


def session_topic(db: DBSession, session_id: str) -> tuple[CurriculumTopic, CurriculumVariant] | None:
    record = db.get(LessonTopic, session_id)
    if record is None:
        return None
    return db.get(CurriculumTopic, record.topic_id), db.get(CurriculumVariant, record.variant_id)


def topic_note(topic: CurriculumTopic, variant: CurriculumVariant) -> str:
    # The part of the lesson prompt that tells the model what this lesson is about.
    phrases = ", ".join(f'"{p}"' for p in variant.phrases) or "none"
    return (
        f"Today's topic: {topic.title}. Goal: {topic.goal}.\n"
        f"Version for this learner: {variant.id} ({variant.style}).\n"
        f"Start the topic in this style: {variant.opener}\n"
        f"Target phrases to practise: {phrases}. Use them naturally; do not list them all at once."
    )


def slots_for(topic: CurriculumTopic) -> list[dict]:
    # Every band and level the topic covers, and whether a variant is written for it yet.
    return [
        {"band": band, "level": level}
        for band in BAND_CODES
        if band in topic.bands
        for level in topic_levels(topic)
    ]


def catalog_view(db: DBSession) -> dict:
    # Everything the administrator sees on the curriculum page: topics, the variants written, and the slots still empty.
    variants = db.query(CurriculumVariant).all()
    written = {v.id: v for v in variants}
    topics = []
    for topic in ordered_topics(db):
        slots = [
            {**slot, "variant_id": f"{topic.id}.{slot['band']}.{slot['level']}",
             "written": f"{topic.id}.{slot['band']}.{slot['level']}" in written}
            for slot in slots_for(topic)
        ]
        topics.append(
            {
                "id": topic.id,
                "title": topic.title,
                "goal": topic.goal,
                "levels": topic_levels(topic),
                "bands": [b for b in topic.bands],
                "slots": slots,
            }
        )
    rows = [
        {
            "id": v.id,
            "topic_id": v.topic_id,
            "band": v.band,
            "level": v.level,
            "opener": v.opener,
            "phrases": v.phrases,
            "style": v.style,
        }
        for v in sorted(variants, key=lambda v: v.id)
    ]
    return {
        "version": catalog_version(db),
        "bands": [{"code": code, "age_band": BAND_CODES[code], "label": BAND_LABELS[code]} for code in BAND_CODES],
        "levels": LEVELS,
        "topics": topics,
        "variants": rows,
    }


def save_variant_text(variant: CurriculumVariant, opener: str, phrases: list[str], style: str) -> None:
    variant.opener = opener.strip()
    variant.phrases = [p.strip() for p in phrases if p.strip()]
    variant.style = style.strip()


def create_variant(db: DBSession, topic_id: str, band: str, level: str) -> CurriculumVariant | None:
    # Returns None when the topic does not cover this band or level. Raises nothing for a duplicate; the caller checks first.
    topic = db.get(CurriculumTopic, topic_id)
    if topic is None or band not in topic.bands or level not in topic_levels(topic):
        return None
    variant = CurriculumVariant(id=f"{topic_id}.{band}.{level}", topic_id=topic_id, band=band, level=level, opener="", phrases=[], style="")
    db.add(variant)
    return variant
