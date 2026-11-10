from helpers_learner import PARENT_PHONE, learner_login, self_student
from zaban.api import _require_complete_profile
from zaban.db import SessionLocal
from zaban.models import Guardian, LearnerDetails


def test_adult_age_and_gender_count_for_a_self_learner(client):
    # The adult enters age and gender in the account. Starting a lesson must accept them without a second form.
    learner_login(client)
    with SessionLocal() as db:
        student = self_student(db)
        adult = db.query(Guardian).filter(Guardian.phone == PARENT_PHONE).one()
        student.cefr_level = student.cefr_level or "A1"
        adult.age = 25
        adult.gender = "female"
        existing = db.get(LearnerDetails, student.id)
        if existing is not None:
            db.delete(existing)
        db.commit()

        _require_complete_profile(db, student)

        details = db.get(LearnerDetails, student.id)
        assert details.age == 25 and details.gender == "female"


def test_missing_level_still_blocks_a_lesson(client):
    learner_login(client)
    with SessionLocal() as db:
        student = self_student(db)
        level = student.cefr_level
        student.cefr_level = None
        db.commit()
        try:
            _require_complete_profile(db, student)
        except Exception as exc:  # HTTPException 409 with the missing list
            assert "level" in str(exc.detail)
        else:
            raise AssertionError("a lesson must not start without a level")
        finally:
            student.cefr_level = level
            db.commit()
