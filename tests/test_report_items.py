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
