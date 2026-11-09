import base64

from fastapi.testclient import TestClient

from zaban.main import app
from zaban.services.sms import dev_outbox

PHOTO = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xe0fake-jpeg-bytes").decode()


def _adult(phone: str, name: str = "Profile Adult") -> TestClient:
    adult = TestClient(app)
    adult.post("/v1/web/user/otp/request", json={"phone": phone, "purpose": "signup"})
    code = [c for n, c in dev_outbox() if n == phone][-1]
    created = adult.post(
        "/v1/web/user/signup",
        json={"phone": phone, "code": code, "full_name": name, "password": "first-pass-1", "age_confirmed": True},
    )
    assert created.status_code == 201, created.text
    return adult


def test_profile_starts_empty_and_saves_personal_details(client):
    adult = _adult("09121230201")

    empty = adult.get("/v1/web/user/profile").json()
    assert empty["name"] == "Profile Adult"
    assert empty["phone"] == "09121230201"
    assert empty["email"] == "" and empty["age"] is None and empty["gender"] == "" and empty["avatar"] == ""

    saved = adult.put(
        "/v1/web/user/profile",
        json={"full_name": "Parisa Karimi", "email": " Parisa@Example.com ", "age": 34, "gender": "female", "avatar": PHOTO},
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["name"] == "Parisa Karimi"
    assert body["email"] == "parisa@example.com"
    assert body["age"] == 34 and body["gender"] == "female"
    assert body["avatar"] == PHOTO


def test_partial_save_keeps_the_other_fields(client):
    adult = _adult("09121230202")
    adult.put("/v1/web/user/profile", json={"age": 40, "gender": "male", "avatar": PHOTO})

    # The old profile page only sends the name, so the photo, age and gender must stay.
    kept = adult.put("/v1/web/user/profile", json={"full_name": "Renamed Adult"}).json()
    assert kept["name"] == "Renamed Adult"
    assert kept["age"] == 40 and kept["gender"] == "male" and kept["avatar"] == PHOTO

    cleared = adult.put("/v1/web/user/profile", json={"avatar": "", "gender": None, "email": ""}).json()
    assert cleared["avatar"] == "" and cleared["gender"] == "" and cleared["email"] == ""


def test_profile_rejects_bad_values(client):
    adult = _adult("09121230203")
    assert adult.put("/v1/web/user/profile", json={"email": "not-an-email"}).status_code == 400
    assert adult.put("/v1/web/user/profile", json={"avatar": "data:text/html;base64,PGgxPg=="}).status_code == 400
    assert adult.put("/v1/web/user/profile", json={"age": 12}).status_code == 422
    assert adult.put("/v1/web/user/profile", json={"gender": "robot"}).status_code == 422
    assert adult.put("/v1/web/user/profile", json={"full_name": ""}).status_code == 422


def test_email_cannot_be_shared_between_adults(client):
    first = _adult("09121230204")
    second = _adult("09121230205")
    assert first.put("/v1/web/user/profile", json={"email": "shared@example.com"}).status_code == 200
    clash = second.put("/v1/web/user/profile", json={"email": "shared@example.com"})
    assert clash.status_code == 409
    assert "already used" in clash.json()["detail"]


def test_password_change_checks_the_current_password(client):
    adult = _adult("09121230206")
    wrong = adult.post("/v1/web/user/password", json={"current_password": "nope-nope", "new_password": "second-pass-2"})
    assert wrong.status_code == 400
    assert adult.post(
        "/v1/web/user/password", json={"current_password": "first-pass-1", "new_password": "second-pass-2"}
    ).status_code == 200
