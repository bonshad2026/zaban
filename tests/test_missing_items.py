import base64
import os
import sys
from pathlib import Path

from zaban.db import SessionLocal
from zaban.models import ConsultRequest, HelpContent, SelfTest, Student
from zaban.services.curriculum import band_code
from helpers_learner import learner_login, self_student

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def _admin(client) -> None:
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200




def _demo_student() -> Student:
    with SessionLocal() as db:
        student = self_student(db)
        db.expunge(student)
        return student


def _content_for_demo_student(**overrides) -> dict:
    student = _demo_student()
    body = {
        "title": "Ten-minute story",
        "category": "story",
        "age_band": band_code(student.age_band),
        "level": student.cefr_level or "A2",
        "interests": "animals",
        "url": "https://example.com/story",
    }
    body.update(overrides)
    return body


def test_cooperation_form_is_public_and_listed_for_admin(client):
    body = {"subject": "Teaching partner", "phone": "09121234567", "email": "teacher@example.com", "message": "Hi"}
    assert client.post("/v1/public/cooperation", json=body).status_code == 201
    _admin(client)
    rows = client.get("/v1/admin/api/cooperations").json()
    row = next(r for r in rows if r["subject"] == "Teaching partner")
    assert row["status"] == "new"
    assert client.post(f"/v1/admin/api/cooperations/{row['id']}/status", json={"status": "contacted"}).status_code == 200


def test_cooperation_rejects_a_bad_phone_and_email(client):
    assert client.post("/v1/public/cooperation", json={"subject": "Hi", "phone": "1234567890"}).status_code == 400
    bad_email = {"subject": "Hi", "phone": "09121234567", "email": "not-an-email"}
    assert client.post("/v1/public/cooperation", json=bad_email).status_code == 422


def test_cooperation_page_and_header_link_are_served(client):
    assert 'id="cooperationForm"' in client.get("/cooperation").text
    assert 'href="/cooperation"' in client.get("/").text


def test_consult_status_accepts_the_new_call_states(client):
    client.post("/v1/public/consult", json={"name": "Sara Test", "last_name": "Test", "subject": "Prices", "contact_permission": True, "phone": "09121230001", "message": "hello"})
    _admin(client)
    with SessionLocal() as db:
        item = db.query(ConsultRequest).filter(ConsultRequest.name == "Sara Test").order_by(ConsultRequest.id.desc()).first()
        item_id = item.id
    for status in ("reviewed", "called", "recall", "awaiting_reply"):
        assert client.post(f"/v1/admin/api/consults/{item_id}/status", json={"status": status}).status_code == 200
    assert client.post(f"/v1/admin/api/consults/{item_id}/status", json={"status": "lost"}).status_code == 422


def test_help_content_link_is_listed_for_matching_learner_only(client):
    _admin(client)
    assert client.post("/v1/admin/api/help-content", json=_content_for_demo_student()).status_code == 201
    learner_login(client)
    titles = [item["title"] for item in client.get("/v1/web/student/help-content").json()]
    assert "Ten-minute story" in titles

    student_band = band_code(_demo_student().age_band)
    other_band = "K" if student_band != "K" else "A"
    _admin(client)
    other = _content_for_demo_student(age_band=other_band, title="Only for others")
    client.post("/v1/admin/api/help-content", json=other)
    learner_login(client)
    titles = [item["title"] for item in client.get("/v1/web/student/help-content").json()]
    assert "Only for others" not in titles


def test_help_content_file_is_served_to_a_matching_learner(client):
    _admin(client)
    data = base64.b64encode(b"ID3fake-audio-bytes").decode()
    body = _content_for_demo_student(url=None, data_base64=data, mime="audio/mpeg", title="Podcast file")
    item_id = client.post("/v1/admin/api/help-content", json=body).json()["id"]
    learner_login(client)
    response = client.get(f"/v1/web/student/help-content/{item_id}/file")
    assert response.status_code == 200
    assert response.content == b"ID3fake-audio-bytes"
    assert response.headers["content-type"].startswith("audio/mpeg")


def test_help_content_needs_exactly_one_source(client):
    _admin(client)
    both = _content_for_demo_student(data_base64="AAAA", mime="audio/mpeg")
    assert client.post("/v1/admin/api/help-content", json=both).status_code == 422
    neither = _content_for_demo_student(url=None)
    assert client.post("/v1/admin/api/help-content", json=neither).status_code == 422


def test_help_content_is_admin_only_and_can_be_deleted(client):
    body = _content_for_demo_student(title="To delete")
    assert client.post("/v1/admin/api/help-content", json=body).status_code == 401
    _admin(client)
    item_id = client.post("/v1/admin/api/help-content", json=body).json()["id"]
    assert client.delete(f"/v1/admin/api/help-content/{item_id}").status_code == 200
    with SessionLocal() as db:
        assert db.get(HelpContent, item_id) is None


def test_self_test_runs_offline_and_saves_an_evaluation(client):
    learner_login(client)
    created = client.post("/v1/web/student/self-tests", json={"kind": "suggested", "skill": "speaking", "minutes": 5})
    assert created.status_code == 201
    test = created.json()
    assert test["status"] == "active"
    assert test["messages"][0]["role"] == "assistant"
    answered = client.post(f"/v1/web/student/self-tests/{test['id']}/messages", json={"content": "I like dogs."})
    assert answered.status_code == 200
    assert len(answered.json()["messages"]) == 3
    finished = client.post(f"/v1/web/student/self-tests/{test['id']}/finish").json()
    assert finished["status"] == "finished"
    assert finished["result"]
    later = client.post(f"/v1/web/student/self-tests/{test['id']}/messages", json={"content": "more"})
    assert later.status_code == 409
    with SessionLocal() as db:
        assert db.get(SelfTest, test["id"]).status == "finished"


def test_self_test_prompt_is_editable_by_admin(client):
    _admin(client)
    assert client.post("/v1/admin/api/self-test-prompt", json={"text": "Be extra gentle."}).status_code == 200
    assert client.get("/v1/admin/api/self-test-prompt").json()["text"] == "Be extra gentle."


def test_self_test_is_private_to_its_owner(client):
    learner_login(client)
    created = client.post("/v1/web/student/self-tests", json={"kind": "qa", "skill": "mixed", "minutes": 5})
    test_id = created.json()["id"]
    assert client.get(f"/v1/web/student/self-tests/{test_id}").status_code == 200
    assert client.get("/v1/web/student/self-tests/not-a-test").status_code == 404


def test_schema_changes_list_missing_tables_and_columns(tmp_path):
    from zaban.services.export import schema_changes
    from sqlalchemy import create_engine, text

    url = f"sqlite:///{tmp_path / 'old.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE students (id VARCHAR(32) PRIMARY KEY)"))
    engine.dispose()

    statements = "\n".join(schema_changes(url))
    assert "CREATE TABLE cooperation_requests" in statements
    assert "ALTER TABLE students ADD COLUMN display_name" in statements
    assert "CREATE TABLE self_tests" in statements


def test_build_export_writes_code_data_media_and_schema(tmp_path, client):
    from zaban.services.export import build

    summary = build(tmp_path / "out", since=None, with_data=True, target_url=os.environ["DATABASE_URL"])
    assert summary["code_files"] > 0
    assert (tmp_path / "out" / "schema" / "schema_changes.sql").exists()
    assert (tmp_path / "out" / "database" / "data.json").exists()
    assert (tmp_path / "out" / "media" / "index.json").exists()
