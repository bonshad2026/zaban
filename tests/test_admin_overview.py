import os

from helpers_learner import learner_login

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def _admin(client) -> None:
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200


def test_learner_list_contains_every_learner_with_a_name(client):
    # The list used by the overview picker includes the learner who signed in, so there is always something to pick.
    learner_login(client)
    _admin(client)
    learners = client.get("/v1/admin/api/learners").json()
    assert learners, "the learner list must not be empty after a learner signs in"
    assert all(item["id"] and item["name"] for item in learners)
    assert all({"id", "name", "kind", "parent"} <= set(item) for item in learners)


def test_overview_returns_the_counts_the_panel_shows(client):
    _admin(client)
    data = client.get("/v1/admin/api/overview").json()
    assert {"users", "active_plans", "payments", "consults", "cooperations", "lessons", "self_tests", "tokens"} <= set(data)
