import os


ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
DEMO = {"X-API-Key": os.environ["ZABAN_DEMO_API_KEY"]}


def _admin(client) -> None:
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200


def _student_row(client, student_id: str) -> dict:
    return next(s for s in client.get("/v1/admin/api/students").json() if s["id"] == student_id)


def test_student_list_needs_admin_sign_in(client):
    assert client.get("/v1/admin/api/students").status_code == 401


def test_parent_or_api_key_can_set_interests_and_motivation_at_creation(client):
    created = client.post(
        "/v1/students",
        headers=DEMO,
        json={"age_band": "adult", "display_name": "Sara", "interests": "drawing", "motivation": "travel"},
    )
    assert created.status_code == 201, created.text

    _admin(client)
    row = _student_row(client, created.json()["id"])
    assert (row["interests"], row["motivation"]) == ("drawing", "travel")


def test_unknown_student_profile_is_not_found(client):
    _admin(client)
    response = client.post("/v1/admin/api/students/missing/profile", json={"instructions": "Hi"})
    assert response.status_code == 404


def test_profile_and_general_prompt_lengths_are_limited(client):
    _admin(client)
    student_id = client.get("/v1/admin/api/students").json()[0]["id"]
    too_long_notes = client.post(
        f"/v1/admin/api/students/{student_id}/profile", json={"instructions": "x" * 2001}
    )
    assert too_long_notes.status_code == 422
    too_long_global = client.post("/v1/admin/api/global-prompt", json={"text": "x" * 4001})
    assert too_long_global.status_code == 422
