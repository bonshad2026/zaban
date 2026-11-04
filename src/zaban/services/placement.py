# A short level check the learner takes before the first lesson. The answers are checked on the server,
# so the browser never decides the level. Each question is one multiple-choice item.
QUESTIONS = [
    {"text": "I ___ a student.", "options": ["am", "is", "are"], "answer": 0},
    {"text": "She ___ to school every day.", "options": ["go", "goes", "going"], "answer": 1},
    {"text": "Yesterday we ___ to the park.", "options": ["go", "goes", "went"], "answer": 2},
    {"text": "I have lived here ___ 2019.", "options": ["since", "for", "ago"], "answer": 0},
    {"text": "If it rains tomorrow, we ___ at home.", "options": ["will stay", "would stay", "stayed"], "answer": 0},
    {"text": "Not only ___ the exam, but she also got the top score.", "options": ["did she pass", "she passed", "passed she"], "answer": 0},
]

# Correct answers mapped to a level. Six questions cover the range from A1 to C1.
LEVEL_BY_SCORE = ["A1", "A1", "A2", "B1", "B1", "B2", "C1"]


def public_questions() -> list[dict]:
    # The answer key stays on the server.
    return [{"text": q["text"], "options": q["options"]} for q in QUESTIONS]


def score_answers(answers: list[int]) -> int:
    return sum(1 for given, question in zip(answers, QUESTIONS) if given == question["answer"])


def level_for_score(score: int) -> str:
    return LEVEL_BY_SCORE[score]
