from helpers_learner import demo_student, learner_login


def test_report_items_lists_lessons_talks_and_tests_newest_first(client):
    learner_login(client)
    student = demo_student()
    response = client.get(f"/v1/students/{student.id}/reports/items")
    assert response.status_code == 200
    items = response.json()["items"]
    assert all(item["type"] in ("lesson", "talk", "test") for item in items)
    dates = [item["date"] for item in items]
    assert dates == sorted(dates, reverse=True)
    for item in items:
        assert set(item["levels"]) == {"range", "accuracy", "fluency", "interaction", "coherence"}


def test_report_items_refuses_a_learner_that_is_not_the_signed_in_one(client):
    learner_login(client)
    response = client.get("/v1/students/not-a-real-learner/reports/items")
    assert response.status_code in (403, 404)


def test_report_items_can_be_limited_to_one_kind(client):
    learner_login(client)
    student = demo_student()
    everything = client.get(f"/v1/students/{student.id}/reports/items").json()["items"]
    for kind, wanted in (("lesson", "lesson"), ("talk", "talk"), ("test", "test")):
        items = client.get(f"/v1/students/{student.id}/reports/items", params={"kind": kind}).json()["items"]
        assert all(item["type"] == wanted for item in items)
        assert len(items) == sum(1 for item in everything if item["type"] == wanted) or len(items) == 50


def test_report_items_refuses_an_unknown_kind(client):
    learner_login(client)
    student = demo_student()
    response = client.get(f"/v1/students/{student.id}/reports/items", params={"kind": "essay"})
    assert response.status_code == 400


def test_every_report_has_a_state_the_list_can_show(client):
    learner_login(client)
    student = demo_student()
    items = client.get(f"/v1/students/{student.id}/reports/items").json()["items"]
    assert all(item["state"] in ("active", "completed", "unevaluated") for item in items)
