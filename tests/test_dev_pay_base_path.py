import itertools
import re

from fastapi.testclient import TestClient

from zaban.main import STATIC_DIR, app
from zaban.security import WEB_COOKIE
from zaban.services.sms import dev_outbox
from zaban import base
from zaban.config import settings

# The stand-in payment page is reached at /dev/pay/{id}. Behind a base path such as /zaban the proxy strips the prefix,
# so the app sees the same routes, and the browser sends the cookie only for addresses under the base path.
# The tests set the base path on purpose, then restore it.

_PHONES = itertools.count(1)
PASSWORD = "dev-pay-pass-1"


def _set_base_path(path: str) -> str:
    previous = settings.base_path
    object.__setattr__(settings, "base_path", path)
    return previous


def _signed_up_token() -> str:
    # The adult signs up and gets the one website cookie. The token is then sent by the test as the browser would send it.
    phone = f"09121231{next(_PHONES):03d}"
    adult = TestClient(app)
    adult.post("/v1/web/user/otp/request", json={"phone": phone, "purpose": "signup"})
    code = [c for n, c in dev_outbox() if n == phone][-1]
    created = adult.post(
        "/v1/web/user/signup",
        json={"phone": phone, "code": code, "full_name": "Dev Pay Adult", "password": PASSWORD},
    )
    assert created.status_code == 201, created.text
    token = created.cookies.get(WEB_COOKIE)
    assert token
    return token


def _browser(token: str | None) -> TestClient:
    browser = TestClient(app)
    if token:
        browser.cookies.set(WEB_COOKIE, token)
    return browser


def _dev_pay_source() -> str:
    return (STATIC_DIR / "dev-pay.html").read_text(encoding="utf-8")


def test_the_stand_in_page_never_calls_or_returns_to_a_root_address():
    source = _dev_pay_source()
    # Every API call and every navigation goes through Z.url() or Z.go(), so the base path is added.
    assert re.search(r'(fetch|location\.href|location\.replace)\(\s*["\']/', source) is None
    assert re.search(r'location\.href\s*=\s*["\']/', source) is None
    assert 'Z.url("/v1/web/billing/fake/confirm")' in source
    assert 'Z.go(ok ? "/plan?payment=paid" : "/plan?payment=failed", true)' in source


def test_the_stand_in_page_loads_the_shared_helpers_before_its_script(client):
    html = client.get("/dev/pay/does-not-matter").text
    assert html.index('src="/static/js/common.js"') < html.index("const paymentId")


def test_the_stand_in_page_is_scoped_to_the_base_path_when_installed_under_it(client):
    previous = _set_base_path("/zaban")
    try:
        html = client.get("/dev/pay/does-not-matter").text
    finally:
        _set_base_path(previous)
    assert 'window.ZABAN_BASE="/zaban";' in html
    assert 'src="/zaban/static/js/common.js"' in html
    assert 'href="/zaban/static/css/app.css' in html
    assert re.search(r'\s(?:href|src|action)="/(?!/|zaban/)', html) is None


def test_the_payment_flow_keeps_the_sign_in_at_the_root_of_a_domain():
    token = _signed_up_token()
    browser = _browser(token)
    plan = browser.get("/v1/web/billing/plans").json()[0]
    paid = browser.post("/v1/web/billing/checkout", json={"plan_id": plan["id"]})
    assert paid.status_code == 201, paid.text
    payment_id = paid.json()["payment_id"]
    assert paid.json()["redirect"] == f"/dev/pay/{payment_id}"

    confirmed = browser.post("/v1/web/billing/fake/confirm", json={"payment_id": payment_id, "ok": True})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    # The sign-in is still good after the payment, so the plan page and the other pages keep working.
    assert browser.get("/v1/web/user/profile").status_code == 200
    assert browser.get("/v1/web/billing/plan").json()["has_active_plan"] is True


def test_the_payment_flow_keeps_the_sign_in_under_a_base_path():
    token = _signed_up_token()
    previous = _set_base_path("/zaban")
    try:
        browser = _browser(token)
        plan = browser.get("/v1/web/billing/plans").json()[0]
        paid = browser.post("/v1/web/billing/checkout", json={"plan_id": plan["id"]})
        assert paid.status_code == 201, paid.text
        # The redirect the page follows already carries the base path.
        assert paid.json()["redirect"] == f"/zaban/dev/pay/{paid.json()['payment_id']}"
        page = browser.get(f"/dev/pay/{paid.json()['payment_id']}").text
        assert 'src="/zaban/static/js/common.js"' in page

        confirmed = browser.post("/v1/web/billing/fake/confirm", json={"payment_id": paid.json()["payment_id"], "ok": True})
        assert confirmed.status_code == 200, confirmed.text
        assert browser.get("/v1/web/user/profile").status_code == 200
        assert browser.get("/v1/web/billing/plan").json()["has_active_plan"] is True
    finally:
        _set_base_path(previous)


def test_a_missing_sign_in_is_reported_as_a_sign_in_error_not_a_route_error():
    token = _signed_up_token()
    owner = _browser(token)
    plan = owner.get("/v1/web/billing/plans").json()[0]
    payment_id = owner.post("/v1/web/billing/checkout", json={"plan_id": plan["id"]}).json()["payment_id"]

    # Without the cookie the server answers 401, which the page shows as a sign-in message.
    anonymous = _browser(None)
    assert anonymous.post("/v1/web/billing/fake/confirm", json={"payment_id": payment_id, "ok": True}).status_code == 401
    # A wrong payment id is a 404 for the route or the payment, which the page reports separately.
    assert owner.post("/v1/web/billing/fake/confirm", json={"payment_id": "missing", "ok": True}).status_code == 404


def test_the_stand_in_page_is_not_served_in_production(client):
    previous = settings.environment
    object.__setattr__(settings, "environment", "production")
    try:
        assert client.get("/dev/pay/any").status_code == 404
    finally:
        object.__setattr__(settings, "environment", previous)
