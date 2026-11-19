# Every evaluated activity is kept in the one evaluation table (stage 1 of the per-skill level plan).
from helpers_learner import learner_login, self_student
from zaban.db import SessionLocal
from zaban.models import LearnerEvaluation, SelfTest


def test_a_finished_self_test_is_recorded_in_the_evaluation_table(client, monkeypatch):
    # The evaluation is all-or-nothing: the notebook step must succeed for the row to be kept. Offline, it is stubbed here.
    monkeypatch.setattr("zaban.services.partner_selftest.write_notebook", lambda *args, **kwargs: "notebook")
    learner_login(client)
    test = client.post("/v1/web/student/self-tests", json={"kind": "suggested", "skill": "writing", "minutes": 5}).json()
    client.post(f"/v1/web/student/self-tests/{test['id']}/messages", json={"content": "I like dogs."})
    assert client.post(f"/v1/web/student/self-tests/{test['id']}/finish").status_code == 200
    with SessionLocal() as db:
        rows = db.query(LearnerEvaluation).filter(LearnerEvaluation.source_id == test["id"]).all()
        status = db.get(SelfTest, test["id"]).partner_status
    assert len(rows) == 1, status
    assert rows[0].source == "self_test"
    assert rows[0].skill == "writing"


def test_two_scored_writing_tests_move_the_writing_level_one_step(client, monkeypatch):
    # Stage 2: a writing test scores the writing level. Two results in a row above the level move it up one step.
    from zaban.services.ai_gateway import AIResult

    monkeypatch.setattr("zaban.services.partner_selftest.write_notebook", lambda *args, **kwargs: "notebook")
    monkeypatch.setattr(
        "zaban.services.self_test.complete",
        lambda *args, **kwargs: AIResult(text="Good work.\nSCORE: 85", input_tokens=1, output_tokens=1, mode="live"),
    )
    learner_login(client)
    for _ in range(2):
        test = client.post("/v1/web/student/self-tests", json={"kind": "qa", "skill": "writing", "minutes": 5}).json()
        client.post(f"/v1/web/student/self-tests/{test['id']}/messages", json={"content": "I like dogs."})
        client.post(f"/v1/web/student/self-tests/{test['id']}/finish")
    with SessionLocal() as db:
        assert self_student(db).level_writing == "A2"
