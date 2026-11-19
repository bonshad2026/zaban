def test_the_shell_page_has_the_header_and_a_frame_and_no_footer(client):
    response = client.get("/app")
    assert response.status_code == 200
    html = response.text
    assert 'id="shellFrame"' in html
    assert 'id="siteActions"' in html
    assert "<!--no-footer-->" not in html
    assert 'src="/static/js/shell.js' in html


def test_member_pages_still_render_for_the_frame(client):
    assert client.get("/student?frame=1").status_code == 200
