from helpers_learner import PARENT_PHONE, learner_login, self_student
from zaban.api import _require_complete_profile
from zaban.db import SessionLocal
from zaban.models import Guardian, LearnerDetails
from zaban.services.learner_details import save_details


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


def test_missing_age_still_blocks_a_lesson(client):
    # Every skill starts at the beginner level, so only age and gender are needed before a lesson.
    learner_login(client)
    with SessionLocal() as db:
        student = self_student(db)
        # The age can come from the adult's account, so the account's age is cleared too.
        adult = db.query(Guardian).filter(Guardian.id == student.self_owner_id).one()
        adult_age = adult.age
        details = save_details(db, student.id, {"age": 30, "gender": "female"})
        db.commit()
        details.age = None
        adult.age = None
        db.commit()
        try:
            _require_complete_profile(db, student)
        except Exception as exc:  # HTTPException 409 with the missing list
            assert "age" in str(exc.detail)
        else:
            raise AssertionError("a lesson must not start without an age")
        finally:
            details.age = 30
            adult.age = adult_age
            db.commit()
