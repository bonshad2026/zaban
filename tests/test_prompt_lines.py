from zaban.services.prompt_template import render


def test_lines_without_information_are_left_out():
    template = "نام: {{learner.name}}\nسن: {{learner.age}}\nعلاقه‌ها: {{learner.interests}}\nدرس: {{lesson.number}} {{lesson.title}}"
    text, unknown = render(template, {"learner.name": "Sara", "learner.age": "", "learner.interests": "", "lesson.number": "1", "lesson.title": "Greetings"})
    assert text == "نام: Sara\nدرس: 1 Greetings"
    assert unknown == []


def test_unknown_placeholders_are_reported_and_removed():
    text, unknown = render("سطح: {{learner.level}}", {})
    assert text == ""
    assert unknown == ["learner.level"]
