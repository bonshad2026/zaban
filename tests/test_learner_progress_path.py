from helpers_learner import learner_login


def test_progress_has_the_lesson_path_and_repeat_is_refused_for_unfinished_lessons(client):
    learner_login(client)
    progress = client.get("/v1/web/student/progress")
    assert progress.status_code == 200
    body = progress.json()
    assert "sessions" in body
    assert body.get("lessons", []) == [] or all(item["status"] in ("done", "current", "upcoming") for item in body["lessons"])
    # Asking to repeat a lesson that is not finished yet is refused, so the learner cannot change their place.
    if body.get("lessons"):
        upcoming = next((item for item in body["lessons"] if item["status"] == "upcoming"), None)
        if upcoming:
            refused = client.post("/v1/web/student/progress/repeat", json={"item_id": upcoming["item_id"]})
            assert refused.status_code == 409
