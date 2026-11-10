from pathlib import Path

from sqlalchemy import delete, func
from sqlalchemy.orm import Session as DBSession

from zaban.models import HelpContent, HelpFacet, HelpTag, help_content_tags

# The levels and genders are fixed, because the learner rules use them. The tags are the part the administrator changes.
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
GENDERS = {"female": "دختر", "male": "پسر"}

# The first facet every installation starts with. The administrator can rename it, add facets and change the tags.
SEED_FACETS = {
    "علایق": ["فوتبال", "نقاشی", "حیوانات", "موسیقی", "سفر", "غذا", "فیلم", "کتاب", "طبیعت", "علم"],
}


def seed_help_facets(db: DBSession) -> None:
    if db.query(HelpFacet).count():
        return
    for order, (name, labels) in enumerate(SEED_FACETS.items()):
        facet = HelpFacet(name=name, sort_order=order)
        facet.tags = [HelpTag(label=label, sort_order=i) for i, label in enumerate(labels)]
        db.add(facet)
    db.commit()


def facet_tree(db: DBSession) -> list[dict]:
    facets = db.query(HelpFacet).order_by(HelpFacet.sort_order, HelpFacet.name).all()
    return [
        {"id": f.id, "name": f.name, "tags": [{"id": t.id, "label": t.label} for t in f.tags]}
        for f in facets
    ]


def tags_by_content(db: DBSession, content_ids: list[str]) -> dict[str, list[HelpTag]]:
    # One query for a whole list, so the admin list and the learner list do not run a query per row.
    out: dict[str, list[HelpTag]] = {cid: [] for cid in content_ids}
    if not content_ids:
        return out
    rows = (
        db.query(help_content_tags.c.content_id, HelpTag)
        .join(HelpTag, HelpTag.id == help_content_tags.c.tag_id)
        .filter(help_content_tags.c.content_id.in_(content_ids))
        .order_by(HelpTag.sort_order)
        .all()
    )
    for content_id, tag in rows:
        out[content_id].append(tag)
    return out


def set_content_tags(db: DBSession, content: HelpContent, tag_ids: list[str]) -> None:
    # Only tags that exist can be attached. Unknown ids are ignored, so an old page cannot attach a deleted tag.
    tags = db.query(HelpTag).filter(HelpTag.id.in_(tag_ids)).all() if tag_ids else []
    content.tags = tags


def delete_tag(db: DBSession, tag_id: str) -> bool:
    tag = db.get(HelpTag, tag_id)
    if tag is None:
        return False
    db.execute(delete(help_content_tags).where(help_content_tags.c.tag_id == tag_id))
    db.delete(tag)
    return True


def delete_facet(db: DBSession, facet_id: str) -> bool:
    facet = db.get(HelpFacet, facet_id)
    if facet is None:
        return False
    for tag in list(facet.tags):
        db.execute(delete(help_content_tags).where(help_content_tags.c.tag_id == tag.id))
    db.delete(facet)
    return True


def tag_counts(db: DBSession, content_ids: list[str]) -> dict[str, int]:
    if not content_ids:
        return {}
    rows = (
        db.query(help_content_tags.c.tag_id, func.count())
        .filter(help_content_tags.c.content_id.in_(content_ids))
        .group_by(help_content_tags.c.tag_id)
        .all()
    )
    return {tag_id: count for tag_id, count in rows}


# One simple sample for each category, so the library is not empty. A video sample needs a real video file, so it is not here.
SAMPLE_DIR = Path(__file__).resolve().parent.parent / "seed_media" / "help"
SAMPLES = [
    # (category, title, file, mime, tags)
    ("podcast", "نمونه: پادکست کوتاه درباره‌ی غذا", "podcast-sample.wav", "audio/wav", ["غذا"]),
    ("story", "نمونه: داستان یک روز در پارک", "story-sample.pdf", "application/pdf", ["طبیعت", "حیوانات"]),
    ("animation", "نمونه: انیمیشن (یک فریم)", "animation-sample.png", "image/png", ["طبیعت"]),
    ("sample", "نمونه: کاربرگ خانواده", "sample-worksheet.pdf", "application/pdf", []),
    ("other", "نمونه: راهنمای تمرین", "guide-sample.pdf", "application/pdf", ["کتاب"]),
]


def seed_help_samples(db: DBSession) -> None:
    # Adds a sample only when no item with its title exists, so a restart does not copy it again.
    for category, title, filename, mime, tag_labels in SAMPLES:
        if db.query(HelpContent).filter(HelpContent.title == title).first():
            continue
        data = (SAMPLE_DIR / filename).read_bytes()
        item = HelpContent(
            title=title,
            category=category,
            age_band="T",
            level="A1",
            stage=None,
            url=None,
            mime=mime,
            data=data,
        )
        db.add(item)
        db.flush()
        tags = db.query(HelpTag).filter(HelpTag.label.in_(tag_labels)).all() if tag_labels else []
        item.tags = tags
    db.commit()
