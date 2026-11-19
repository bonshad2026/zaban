import random

from sqlalchemy.orm import Session as DBSession

from zaban.models import Student, TutorSession

# The topics the partner suggests for a free talk. The learner can choose another one, typed or spoken.
TOPICS = [
    "travel plans",
    "a memorable meal",
    "weekend hobbies",
    "a city you would like to visit",
    "your job or studies",
    "a film or series you liked",
    "technology in daily life",
    "sports and fitness",
    "music you enjoy",
    "a recent holiday",
    "cooking at home",
    "the weather and the seasons",
    "books you have read",
    "shopping habits",
    "plans for next year",
    "friends and family",
    "a funny day you remember",
    "animals and pets",
    "public transport",
    "learning a new skill",
]
# How many earlier free talks are looked at, so a topic is not repeated too soon.
HISTORY = 20


def recent_topics(db: DBSession, student_id: str) -> set[str]:
    rows = (
        db.query(TutorSession.topic)
        .filter(
            TutorSession.student_id == student_id,
            TutorSession.session_kind == "free",
            TutorSession.topic.isnot(None),
        )
        .order_by(TutorSession.started_at.desc())
        .limit(HISTORY)
        .all()
    )
    return {topic.strip().lower() for (topic,) in rows if topic}


def suggest_topic(db: DBSession, student: Student) -> str:
    # A topic the learner has not had in a recent free talk. When every topic was used, any topic is suggested again.
    used = recent_topics(db, student.id)
    options = [topic for topic in TOPICS if topic.lower() not in used] or TOPICS
    return random.choice(options)
