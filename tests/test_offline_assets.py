from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "src" / "zaban" / "static"


def test_the_service_worker_is_served_from_the_root_with_the_whole_site_in_scope(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["service-worker-allowed"] == "/"


def test_pages_and_styles_do_not_load_anything_from_the_internet():
    # The look must survive without a connection, so every stylesheet and font comes from the project.
    outside = ("cdn.jsdelivr.net", "fonts.googleapis.com", "fonts.gstatic.com")
    for path in list(STATIC.glob("*.html")) + [STATIC / "css" / "app.css"]:
        text = path.read_text(encoding="utf-8")
        for host in outside:
            assert host not in text, f"{path.name} loads {host}"
