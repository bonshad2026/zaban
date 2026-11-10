import os

from fastapi.testclient import TestClient

from zaban.main import app

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
PARENT_PHONE = os.environ["ZABAN_DEMO_PARENT_PHONE"]
PARENT_PASSWORD = os.environ["ZABAN_DEMO_PARENT_PASSWORD"]


def test_admin_lists_a_sign_in_and_ending_it_signs_that_device_out(client):
    user = TestClient(app)
    assert user.post("/v1/web/user/login", json={"phone": PARENT_PHONE, "password": PARENT_PASSWORD}).status_code == 200
    assert user.get("/v1/web/me?role=parent").status_code == 200

    admin = TestClient(app)
    assert admin.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200
    groups = admin.get("/v1/admin/api/sessions").json()
    adult = [g for g in groups if g["role"] == "guardian" and g["contact"] == PARENT_PHONE]
    assert adult, "the adult's active sign-ins should be listed"
    # The newest sign-in comes first, and it is the one this test just made.
    newest = adult[0]["sessions"][0]
    assert {"id", "started_at", "user_agent", "ip"} <= newest.keys()

    ended = admin.post("/v1/admin/api/sessions/revoke", json={"ids": [newest["id"]]})
    assert ended.status_code == 200 and ended.json()["revoked"] == 1
    assert user.get("/v1/web/me?role=parent").status_code == 401

    remaining = admin.get("/v1/admin/api/sessions").json()
    assert all(s["id"] != newest["id"] for g in remaining for s in g["sessions"])


def test_logout_ends_only_this_device(client):
    first = TestClient(app)
    second = TestClient(app)
    for device in (first, second):
        assert device.post("/v1/web/user/login", json={"phone": PARENT_PHONE, "password": PARENT_PASSWORD}).status_code == 200
    assert first.post("/v1/web/logout?role=parent").status_code == 200
    assert first.get("/v1/web/me?role=parent").status_code == 401
    assert second.get("/v1/web/me?role=parent").status_code == 200
