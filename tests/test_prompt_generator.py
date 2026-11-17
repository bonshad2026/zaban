from zaban.services.prompt_template import render

def test_render_fills_known_placeholders_and_lists_unknown_ones():
    text, unknown = render("A {{learner.name}} B {{nope}} C {{ general }}", {"learner.name": "Sara", "general": "G"})
    assert text == "A Sara B  C G"
    assert unknown == ["nope"]

