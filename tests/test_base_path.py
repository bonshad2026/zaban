import re

from helpers_learner import PARENT_PASSWORD, PARENT_PHONE
from zaban import base
from zaban.config import settings

# The site is served under /zaban on a shared domain. The settings object is frozen, so the test changes it on purpose and restores it.


def _set_base_path(path: str) -> str:
    previous = settings.base_path
    object.__setattr__(settings, "base_path", path)
    return previous


def test_the_helpers_add_the_base_path_only_to_root_relative_addresses():
    previous = _set_base_path("/zaban")
    try:
        assert base.with_base("/plan?payment=paid") == "/zaban/plan?payment=paid"
        assert base.with_base("https://pay.example.com/callback") == "https://pay.example.com/callback"
        assert base.with_base("//cdn.example.com/x.js") == "//cdn.example.com/x.js"
        assert base.cookie_path() == "/zaban"
    finally:
        _set_base_path(previous)
    assert base.with_base("/plan") == "/plan"
    assert base.cookie_path() == "/"


def test_pages_point_every_link_and_source_at_the_base_path(client):
    previous = _set_base_path("/zaban")
    try:
        html = client.get("/login").text
    finally:
        _set_base_path(previous)
    assert 'window.ZABAN_BASE="/zaban";' in html
    assert 'href="/zaban/static/css/app.css' in html
    assert 'src="/zaban/static/js/common.js' in html
    # No link or source is left at the root of the domain.
    assert re.search(r'\s(?:href|src|action)="/(?!/|zaban/)', html) is None


def test_pages_are_unchanged_without_a_base_path(client):
    html = client.get("/login").text
    assert "window.ZABAN_BASE" not in html
    assert 'href="/static/css/app.css' in html


def test_the_sign_in_cookie_is_scoped_to_the_base_path(client):
    previous = _set_base_path("/zaban")
    try:
        response = client.post("/v1/web/user/login", json={"phone": PARENT_PHONE, "password": PARENT_PASSWORD})
        assert response.status_code == 200
        cookie_headers = response.headers.get_list("set-cookie")
        assert cookie_headers and all("Path=/zaban" in header for header in cookie_headers)
    finally:
        _set_base_path(previous)
        client.cookies.clear()
