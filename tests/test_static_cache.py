# Static files are checked with the server each time, so a browser does not keep an old script after a rebuild.


def test_static_files_must_be_revalidated(client):
    response = client.get("/static/js/common.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
