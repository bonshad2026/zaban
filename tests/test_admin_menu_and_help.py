import os

from zaban.db import SessionLocal
from zaban.models import HelpContent
from zaban.services.curriculum import band_code
from helpers_learner import learner_login, self_student

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def _admin(client) -> None:
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200


def _demo_profile(client) -> tuple[str, str]:
    # The demo learner profile exists once a learner has signed in, so it is read after that.
    learner_login(client)
    with SessionLocal() as db:
        student = self_student(db)
        return band_code(student.age_band), student.cefr_level or "A1"


def _body(client, title: str, **overrides) -> dict:
    body = {
        "title": title,
        "category": "story",
        "age_band": _demo_profile(client)[0],
        "level": _demo_profile(client)[1],
        "url": "https://example.com/" + title.replace(" ", "-"),
    }
    body.update(overrides)
    return body


# ----- Admin menu: request dialogs, grouped sidebar, separate prompt / payment / SMS sections -----

def test_admin_page_has_the_request_details_dialog_and_status_list(client):
    html = client.get("/admin").text
    for element in ('id="requestDialog"', 'id="requestStatusSlot"', 'id="consultFilter"', 'id="cooperationFilter"'):
        assert element in html


def test_admin_sidebar_groups_are_parent_menus(client):
    html = client.get("/admin").text
    for group in ("درخواست‌ها", "کاربران", "مالی", "آموزش", "مجموعه پرامپت", "تنظیمات"):
        assert f'class="admin-group-title" aria-expanded="true">{group}</button>' in html
    # The user tabs sit under «کاربران».
    users = html.index('data-group="users"')
    assert users < html.index('data-tab="adults"') < html.index('data-tab="sessions"')
    assert 'data-tab="students"' not in html


def test_prompt_payment_and_sms_have_their_own_sections(client):
    html = client.get("/admin").text
    for tab in ("global", "promptgen", "promptview", "settings", "payment", "connections"):
        assert f'data-tab="{tab}"' in html
    assert 'id="tab-payment"' in html and 'id="paySave"' in html and 'id="smsSave"' in html
    # The payment gateway is no longer part of the prompt settings.
    prompt_section = html[html.index('id="tab-settings"'):html.index('id="tab-payment"')]
    assert "setProvider" not in prompt_section and "connPayProvider" not in prompt_section


# ----- Help content: tags, facets and classification -----

def test_admin_can_define_facets_and_tags_and_remove_them(client):
    _admin(client)
    facet_id = client.post("/v1/admin/api/help-facets", json={"name": "نوع فعالیت"}).json()["id"]
    tag_id = client.post(f"/v1/admin/api/help-facets/{facet_id}/tags", json={"label": "گوش دادن"}).json()["id"]
    facets = {f["name"]: f for f in client.get("/v1/admin/api/help-facets").json()}
    assert [t["label"] for t in facets["نوع فعالیت"]["tags"]] == ["گوش دادن"]

    assert client.delete(f"/v1/admin/api/help-tags/{tag_id}").status_code == 200
    assert client.delete(f"/v1/admin/api/help-facets/{facet_id}").status_code == 200
    assert "نوع فعالیت" not in {f["name"] for f in client.get("/v1/admin/api/help-facets").json()}


def test_seeded_facet_and_samples_exist_for_every_category(client):
    _admin(client)
    facets = {f["name"] for f in client.get("/v1/admin/api/help-facets").json()}
    assert "علایق" in facets
    titles = {row["title"]: row for row in client.get("/v1/admin/api/help-content").json() if row["title"].startswith("نمونه: ")}
    categories = {row["category"] for row in titles.values()}
    assert {"podcast", "story", "animation", "sample", "other"} <= categories


def test_tags_are_saved_and_can_be_changed_later(client):
    _admin(client)
    tag_id = next(t["id"] for f in client.get("/v1/admin/api/help-facets").json() for t in f["tags"] if t["label"] == "حیوانات")
    item_id = client.post("/v1/admin/api/help-content", json=_body(client, "Tagged story", tag_ids=[tag_id])).json()["id"]
    row = next(r for r in client.get("/v1/admin/api/help-content").json() if r["id"] == item_id)
    assert [t["label"] for t in row["tags"]] == ["حیوانات"]

    response = client.put(f"/v1/admin/api/help-content/{item_id}/classification",
                          json={"age_band": _demo_profile(client)[0], "level": "A2", "gender": "female", "tag_ids": []})
    assert response.status_code == 200
    row = next(r for r in client.get("/v1/admin/api/help-content").json() if r["id"] == item_id)
    assert row["level"] == "A2" and row["gender"] == "female" and row["tags"] == []


def test_learner_filters_by_tag_and_gets_the_options(client):
    _admin(client)
    with SessionLocal() as db:
        from zaban.models import HelpTag
        tag = db.query(HelpTag).filter(HelpTag.label == "موسیقی").one()
        tag_id = tag.id
    client.post("/v1/admin/api/help-content", json=_body(client, "Music story", tag_ids=[tag_id]))
    client.post("/v1/admin/api/help-content", json=_body(client, "Plain story"))
    learner_login(client)

    titles = [item["title"] for item in client.get("/v1/web/student/help-content", params={"tag": tag_id}).json()]
    assert titles == ["Music story"]

    filters = client.get("/v1/web/student/help-content/filters").json()
    facet = next(f for f in filters["facets"] if any(o["value"] == tag_id for o in f["options"]))
    assert next(o for o in facet["options"] if o["value"] == tag_id)["count"] == 1
    assert "level" in filters and "gender" in filters


def test_learner_gender_filter_keeps_content_for_everyone(client):
    _admin(client)
    client.post("/v1/admin/api/help-content", json=_body(client, "For girls", gender="female"))
    client.post("/v1/admin/api/help-content", json=_body(client, "For all"))
    learner_login(client)
    titles = [item["title"] for item in client.get("/v1/web/student/help-content", params={"gender": "male"}).json()]
    assert "For all" in titles and "For girls" not in titles


def test_sample_image_is_stored_with_its_file(client):
    _admin(client)
    rows = client.get("/v1/admin/api/help-content").json()
    sample = next(r for r in rows if r["category"] == "animation" and r["title"].startswith("نمونه: "))
    assert sample["size_bytes"] > 0 and sample["url"] is None and sample["mime"] == "image/png"


def test_sample_items_are_not_copied_twice(client):
    from zaban.services.help_content import seed_help_samples

    with SessionLocal() as db:
        before = db.query(HelpContent).filter(HelpContent.title.like("نمونه: %")).count()
        seed_help_samples(db)
        assert db.query(HelpContent).filter(HelpContent.title.like("نمونه: %")).count() == before


# ----- Plans: token cap, activation and delete -----

def test_plan_list_has_add_dialog_and_row_actions(client):
    html = client.get("/admin").text
    assert 'id="planAddOpen"' in html and 'id="planDialog"' in html and 'id="planTokens"' in html


def test_admin_can_add_a_plan_with_a_token_cap_and_delete_it(client):
    _admin(client)
    body = {"name": "Test plan", "price_toman": 1000, "days": 30, "token_allowance": 250000}
    plan_id = client.post("/v1/admin/api/plans", json=body).json()["id"]
    row = next(p for p in client.get("/v1/admin/api/plans").json() if p["id"] == plan_id)
    assert row["token_allowance"] == 250000
    assert client.delete(f"/v1/admin/api/plans/{plan_id}").status_code == 200
    assert all(p["id"] != plan_id for p in client.get("/v1/admin/api/plans").json())


def test_a_plan_with_payments_is_not_deleted(client):
    from zaban.models import BillingPlan, Guardian, Payment
    from helpers_learner import PARENT_PHONE

    _admin(client)
    plan_id = client.post("/v1/admin/api/plans", json={"name": "Paid plan", "price_toman": 500, "days": 10}).json()["id"]
    with SessionLocal() as db:
        guardian = db.query(Guardian).filter(Guardian.phone == PARENT_PHONE).one()
        db.add(Payment(guardian_id=guardian.id, plan_id=plan_id, amount_toman=500, status="pending"))
        db.commit()
    response = client.delete(f"/v1/admin/api/plans/{plan_id}")
    assert response.status_code == 409
    assert any(p["id"] == plan_id for p in client.get("/v1/admin/api/plans").json())


# ----- Curriculum: topic, goal and talking points -----

def test_curriculum_topic_points_can_be_added_and_removed(client):
    _admin(client)
    topics = client.get("/v1/admin/api/curriculum/topics").json()
    topic = topics[0]
    assert set(topic) == {"id", "title", "goal", "points"}
    point_id = client.post(f"/v1/admin/api/curriculum/topics/{topic['id']}/points", json={"text": "Talk about breakfast"}).json()["id"]
    topic = next(t for t in client.get("/v1/admin/api/curriculum/topics").json() if t["id"] == topic["id"])
    assert any(p["id"] == point_id for p in topic["points"])
    assert client.delete(f"/v1/admin/api/curriculum/points/{point_id}").status_code == 200


def test_curriculum_topic_goal_and_title_can_be_saved(client):
    _admin(client)
    topic = client.get("/v1/admin/api/curriculum/topics").json()[0]
    response = client.put(f"/v1/admin/api/curriculum/topics/{topic['id']}", json={"title": "New title", "goal": "A longer goal"})
    assert response.status_code == 200
    saved = next(t for t in client.get("/v1/admin/api/curriculum/topics").json() if t["id"] == topic["id"])
    assert saved["title"] == "New title" and saved["goal"] == "A longer goal"
    client.put(f"/v1/admin/api/curriculum/topics/{topic['id']}", json={"title": topic["title"], "goal": topic["goal"]})


# ----- Self-test prompt: template, rules and preview -----

def test_self_test_preview_names_kind_and_skills_in_full(client):
    learner_login(client)
    _admin(client)
    student_id = client.get("/v1/admin/api/students").json()[0]["id"]
    body = {"student_id": student_id, "kind": "mixed", "skill": "mixed", "minutes": 10}
    prompt = client.post("/v1/admin/api/self-test/preview", json=body).json()["prompt"]
    assert "ترکیبی (سؤال و جواب و مکالمه)" in prompt
    assert "نوشتن، شنیداری، گفتاری" in prompt
    assert "مدت آزمون: 10 دقیقه" in prompt
    assert prompt.rstrip().endswith("refuse anything unrelated. Keep your turns short and ask one question at a time.")


def test_self_test_suggested_kind_shows_the_chosen_kind(client):
    learner_login(client)
    _admin(client)
    student_id = client.get("/v1/admin/api/students").json()[0]["id"]
    prompt = client.post("/v1/admin/api/self-test/preview", json={"student_id": student_id, "kind": "suggested", "skill": "writing", "minutes": 5}).json()["prompt"]
    assert "نوع انتخاب‌شده: پیشنهاد سیستم" in prompt
    assert "نوع این آزمون:" in prompt and "نوشتن" in prompt


def test_self_test_rules_can_be_edited_added_and_removed(client):
    _admin(client)
    assert client.post("/v1/admin/api/self-test/rules", json={"key": "Bad Key", "text": "x"}).status_code == 422
    assert client.post("/v1/admin/api/self-test/rules", json={"key": "kind.quiz", "text": "Ask five quiz questions."}).status_code == 200
    template = client.get("/v1/admin/api/self-test/template").json()
    assert any(p["key"] == "rule.kind.quiz" for p in template["placeholders"])
    assert any(r["key"] == "kind.quiz" for r in template["rules"])
    assert client.delete("/v1/admin/api/self-test/rules/kind.quiz").status_code == 200
    assert all(r["key"] != "kind.quiz" for r in client.get("/v1/admin/api/self-test/template").json()["rules"])


def test_self_test_template_is_saved_and_used(client):
    _admin(client)
    template = client.get("/v1/admin/api/self-test/template").json()
    assert "{{test.kind}}" in template["template"]
    assert client.post("/v1/admin/api/self-test/template", json={"template": template["default_template"]}).status_code == 200


# ----- Admin sign-out: this device, and every device -----

def test_sign_out_everywhere_ends_older_admin_sign_ins(client):
    _admin(client)
    old_cookie = client.cookies.get("zaban_admin")
    assert client.post("/v1/admin/api/logout-all").status_code == 200
    assert client.get("/v1/admin/api/consults").status_code == 401
    client.cookies.set("zaban_admin", old_cookie)
    assert client.get("/v1/admin/api/consults").status_code == 401
    _admin(client)
    assert client.get("/v1/admin/api/consults").status_code == 200


def test_admin_page_offers_sign_out_everywhere(client):
    script = client.get("/static/js/admin.js").text
    assert "خروج از همه‌ی دستگاه‌ها" in script and "/logout-all" in script


# ----- Lesson score from the AI's closing line, and progress by topic -----

def test_ai_closing_line_gives_the_lesson_score(client, monkeypatch):
    from zaban.services import evaluation
    from zaban.services.ai_gateway import AIResult

    def fake_complete(system, messages, max_tokens=300):
        return AIResult(text="Good work today.\nSCORE: 72", input_tokens=10, output_tokens=5, mode="test")

    monkeypatch.setattr(evaluation, "complete", fake_complete)
    with SessionLocal() as db:
        from zaban.models import Message, TutorSession, utcnow
        student = self_student(db)
        session = TutorSession(student_id=student.id, duration_minutes=10, status="completed",
                               started_at=utcnow(), ends_at=utcnow(), ended_at=utcnow())
        db.add(session)
        db.flush()
        db.add(Message(session_id=session.id, role="user", content="Hello teacher"))
        db.commit()
        evaluation.evaluate_session(db, session)
        db.refresh(session)
        assert session.score == 72.0
        assert "SCORE" not in session.evaluation
        assert session.evaluation.startswith("Good work")
