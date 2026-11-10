import os

from zaban.db import SessionLocal
from zaban.models import Guardian, Student

# The demo adult from the test environment. Learning for oneself is the only way a learner signs in now.
PARENT_PHONE = os.environ["ZABAN_DEMO_PARENT_PHONE"]
PARENT_PASSWORD = os.environ["ZABAN_DEMO_PARENT_PASSWORD"]


def learner_login(client) -> None:
    # The adult signs in, then starts learning for themself. That sets the learner cookie.
    assert client.post("/v1/web/user/login", json={"phone": PARENT_PHONE, "password": PARENT_PASSWORD}).status_code == 200
    assert client.post("/v1/web/user/self").status_code == 200


def self_student(db) -> Student:
    # The learner profile of the demo adult. It exists after learner_login has run.
    guardian = db.query(Guardian).filter(Guardian.phone == PARENT_PHONE).one()
    return db.query(Student).filter(Student.self_owner_id == guardian.id).one()


def demo_student() -> Student:
    with SessionLocal() as db:
        student = self_student(db)
        db.expunge(student)
        return student
