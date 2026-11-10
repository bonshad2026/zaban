import json
from datetime import datetime

from sqlalchemy.orm import Session as DBSession

from zaban.models import PlacementAttempt, PlacementQuestion, Student, utcnow

# The level test is kept in the database. Each skill is scored on its own, from A1 up to C1.
# The test goes up one level at a time: a learner who gets at least PASS_CORRECT of the questions of a level
# moves on to the next one, and the test stops at the first level they do not pass. Skipping a skill gives A1.
SKILLS = {
    "reading": "خواندن",
    "grammar": "دستور و واژگان",
    "listening": "شنیداری",
}
LEVELS = ["A1", "A2", "B1", "B2", "C1"]
PASS_CORRECT = 2
DEFAULT_LEVEL = "A1"

# The starting bank. The administrator can edit it, switch items off, and add more from the admin panel.
# Each entry: skill, level, text, options, answer (index of the correct option), audio (read aloud for listening).
SEED_BANK = [
    ("grammar", "A1", "I ___ a teacher.", ["am", "is", "are"], 0, ""),
    ("grammar", "A1", "They ___ from Iran.", ["is", "are", "am"], 1, ""),
    ("grammar", "A1", "She ___ a red bag.", ["have", "has", "having"], 1, ""),
    ("grammar", "A2", "Yesterday I ___ to the cinema.", ["go", "went", "goes"], 1, ""),
    ("grammar", "A2", "There ___ two cats in the garden.", ["is", "are", "be"], 1, ""),
    ("grammar", "A2", "She is ___ than her sister.", ["tall", "taller", "tallest"], 1, ""),
    ("grammar", "B1", "If I ___ time tomorrow, I will call you.", ["have", "had", "will have"], 0, ""),
    ("grammar", "B1", "I have lived here ___ five years.", ["since", "for", "ago"], 1, ""),
    ("grammar", "B1", "He asked me where ___.", ["did I live", "I lived", "I live"], 1, ""),
    ("grammar", "B2", "By next year, she ___ her degree.", ["will finish", "will have finished", "finishes"], 1, ""),
    ("grammar", "B2", "I wish I ___ more time last week.", ["had", "have", "would have"], 0, ""),
    ("grammar", "B2", "The report, ___ was written last month, is now ready.", ["which", "who", "whose"], 0, ""),
    ("grammar", "C1", "Not only ___ the exam, but she also got the top score.", ["did she pass", "she passed", "passed she"], 0, ""),
    ("grammar", "C1", "Had I known about the delay, I ___ earlier.", ["would have left", "would leave", "left"], 0, ""),
    ("grammar", "C1", "The results ___ to be announced next week.", ["are expected", "expect", "are expecting"], 0, ""),
    ("reading", "A1", "Tom has a dog. The dog is black. What colour is the dog?", ["black", "white", "brown"], 0, ""),
    ("reading", "A1", "Ann wakes up at 7. She eats breakfast at 7:30. When does Ann eat breakfast?", ["at 7", "at 7:30", "at 8"], 1, ""),
    ("reading", "A1", "The shop is open on Monday and Tuesday. Is the shop open on Sunday?", ["Yes, it is.", "No, it is not.", "We do not know."], 2, ""),
    ("reading", "A2", "Sam missed the bus, so he walked to work. Why did Sam walk to work?", ["He was late.", "He missed the bus.", "He liked walking."], 1, ""),
    ("reading", "A2", "The museum is closed on Mondays. We visited on Monday. What happened?", ["We could not enter.", "We bought tickets.", "We ate lunch there."], 0, ""),
    ("reading", "A2", "Lisa is taller than Ben but shorter than Kate. Who is the tallest?", ["Lisa", "Ben", "Kate"], 2, ""),
    ("reading", "B1", "Although the film was long, most people enjoyed it. What is the main idea?", ["The film was boring.", "Most people liked the film despite its length.", "Nobody watched the film."], 1, ""),
    ("reading", "B1", "The meeting has been moved from Tuesday to Thursday because the manager is ill. What should you do?", ["Come on Tuesday.", "Come on Thursday.", "Cancel your plans."], 1, ""),
    ("reading", "B1", "Recycling reduces waste and saves natural resources. What does recycling do?", ["It creates new jobs.", "It reduces waste.", "It makes things cheaper."], 1, ""),
    ("reading", "B2", "The committee rejected the proposal on the grounds that it was too expensive. Why was the proposal rejected?", ["It was unpopular.", "It cost too much.", "It was unsafe."], 1, ""),
    ("reading", "B2", "Despite the rain, the organisers went ahead with the festival, though attendance was lower than expected. What is true?", ["The festival was cancelled.", "The festival went ahead with fewer people.", "The festival moved indoors."], 1, ""),
    ("reading", "B2", "Researchers argue that sleep deprivation impairs memory consolidation. What do the researchers claim?", ["Sleep improves memory.", "Lack of sleep harms memory.", "Memory is unrelated to sleep."], 1, ""),
    ("reading", "C1", "Her remarks were ostensibly conciliatory, yet they concealed a deep resentment. What did her remarks hide?", ["Happiness", "Resentment", "Indifference"], 1, ""),
    ("reading", "C1", "The policy, though well-intentioned, had unintended repercussions that undermined its objectives. What happened to the objectives?", ["They were fully achieved.", "They were undermined.", "They were ignored."], 1, ""),
    ("reading", "C1", "Notwithstanding the initial scepticism, the findings were eventually widely accepted. How were the findings received in the end?", ["They were rejected.", "They were widely accepted.", "They were forgotten."], 1, ""),
    ("listening", "A1", "I am going to the shop to buy some milk.", ["Where is the speaker going?", ["school", "shop", "park"]], 1, "I am going to the shop to buy some milk."),
    ("listening", "A1", "My name is Sara and I live in a small house near the sea.", ["Where does Sara live?", ["in a big city", "near the sea", "in the mountains"]], 1, "My name is Sara and I live in a small house near the sea."),
    ("listening", "A1", "It is cold today, so please wear your coat.", ["What should the listener wear?", ["a hat", "a coat", "shoes"]], 1, "It is cold today, so please wear your coat."),
    ("listening", "A2", "The train to London leaves at half past nine from platform four.", ["When does the train leave?", ["9:00", "9:30", "4:30"]], 1, "The train to London leaves at half past nine from platform four."),
    ("listening", "A2", "We are having a party on Saturday at my house. Please bring some music.", ["What should guests bring?", ["food", "music", "drinks"]], 1, "We are having a party on Saturday at my house. Please bring some music."),
    ("listening", "A2", "The bakery opens at seven, but on Sundays it opens at nine.", ["When does the bakery open on Sunday?", ["at seven", "at nine", "at ten"]], 1, "The bakery opens at seven, but on Sundays it opens at nine."),
    ("listening", "B1", "Please remember that the library closes early on Fridays, at four o'clock.", ["When does the library close on Fridays?", ["at noon", "at four", "at six"]], 1, "Please remember that the library closes early on Fridays, at four o'clock."),
    ("listening", "B1", "The report must be finished before the end of the month, not after.", ["When must the report be finished?", ["by the end of the month", "after the month", "next year"]], 0, "The report must be finished before the end of the month, not after."),
    ("listening", "B1", "If you want to join the club, you need to fill in this form and pay the fee.", ["What must you do to join?", ["fill the form and pay", "call the manager", "attend a test"]], 0, "If you want to join the club, you need to fill in this form and pay the fee."),
    ("listening", "B2", "Although the forecast predicted rain, the match went ahead under clear skies.", ["What was the weather during the match?", ["It rained all day.", "It was clear.", "The match was cancelled."]], 1, "Although the forecast predicted rain, the match went ahead under clear skies."),
    ("listening", "B2", "Despite the delay, the engineers finished the bridge two weeks ahead of schedule.", ["How was the bridge completed?", ["late", "two weeks early", "on time"]], 1, "Despite the delay, the engineers finished the bridge two weeks ahead of schedule."),
    ("listening", "B2", "The proposal would reduce costs, but critics worry it could affect quality.", ["What do critics worry about?", ["costs", "quality", "time"]], 1, "The proposal would reduce costs, but critics worry it could affect quality."),
    ("listening", "C1", "Contrary to popular belief, the decline in reading habits is not as severe as some reports suggest.", ["What does the speaker think about the reports?", ["They are accurate.", "They exaggerate the decline.", "They ignore reading."]], 1, "Contrary to popular belief, the decline in reading habits is not as severe as some reports suggest."),
    ("listening", "C1", "Given the scale of the crisis, the government's response was remarkably swift.", ["How was the response described?", ["slow", "swift", "unclear"]], 1, "Given the scale of the crisis, the government's response was remarkably swift."),
    ("listening", "C1", "Her argument hinges on the assumption that consumers are consistently rational.", ["What does her argument depend on?", ["consumers being rational", "prices being low", "markets being large"]], 0, "Her argument hinges on the assumption that consumers are consistently rational."),
]


def ensure_bank(db: DBSession) -> None:
    # Fills the bank once. After that the administrator owns it, and nothing is added back automatically.
    if db.query(PlacementQuestion).first() is not None:
        return
    for skill, level, text, options, answer, audio in SEED_BANK:
        if isinstance(options[-1], list):
            # Listening items keep the question and its choices together in the seed list.
            question, choices = options
            text, options = question, choices
        db.add(PlacementQuestion(skill=skill, level=level, text=text, options=json.dumps(options), answer=answer,
                                 audio_text=audio, active=True))
    db.commit()


def bank_for(db: DBSession, skill: str, level: str) -> list[PlacementQuestion]:
    return (
        db.query(PlacementQuestion)
        .filter(PlacementQuestion.skill == skill, PlacementQuestion.level == level, PlacementQuestion.active.is_(True))
        .order_by(PlacementQuestion.id)
        .all()
    )


def _answers(attempt: PlacementAttempt) -> list[dict]:
    return json.loads(attempt.answers or "[]")


def _level_index_of(level: str) -> int:
    return LEVELS.index(level)


def _next_level_with_questions(db: DBSession, skill: str, index: int) -> int:
    # A level with no questions in the bank is passed over, so the test never waits on an empty level.
    while index < len(LEVELS) and not bank_for(db, skill, LEVELS[index]):
        index += 1
    return index


def start_attempt(db: DBSession, student: Student, skill: str) -> PlacementAttempt:
    running = (
        db.query(PlacementAttempt)
        .filter(PlacementAttempt.student_id == student.id, PlacementAttempt.skill == skill,
                PlacementAttempt.status == "in_progress")
        .first()
    )
    if running is not None:
        return running
    attempt = PlacementAttempt(student_id=student.id, skill=skill, status="in_progress", level_index=0, answers="[]")
    attempt.level_index = _next_level_with_questions(db, skill, 0)
    db.add(attempt)
    db.commit()
    return attempt


# The column that keeps each skill's level. Speaking and writing are set by the learner, not by this test.
SKILL_COLUMN = {
    "listening": "level_listening",
    "reading": "level_reading",
    "grammar": "level_grammar",
}


def skill_levels(student: Student) -> dict[str, str]:
    return {
        "listening": student.level_listening or DEFAULT_LEVEL,
        "reading": student.level_reading or DEFAULT_LEVEL,
        "grammar": student.level_grammar or DEFAULT_LEVEL,
        "speaking_writing": student.level_speaking_writing or DEFAULT_LEVEL,
    }


def _finish(db: DBSession, student: Student, attempt: PlacementAttempt, level: str, status: str) -> None:
    attempt.status = status
    attempt.result_level = level
    attempt.finished_at = utcnow()
    setattr(student, SKILL_COLUMN[attempt.skill], level)
    db.commit()


def current_question(db: DBSession, attempt: PlacementAttempt) -> PlacementQuestion | None:
    if attempt.status != "in_progress":
        return None
    level = LEVELS[attempt.level_index]
    done = {a["question_id"] for a in _answers(attempt)}
    remaining = [q for q in bank_for(db, attempt.skill, level) if q.id not in done]
    return remaining[0] if remaining else None


def answer(db: DBSession, student: Student, attempt: PlacementAttempt, question_id: int, option: int) -> None:
    if attempt.status != "in_progress":
        raise ValueError("This part of the test is already finished")
    question = db.get(PlacementQuestion, question_id)
    current = current_question(db, attempt)
    if current is None or question is None or current.id != question.id:
        raise ValueError("This question is not the one to answer now")
    if not 0 <= option < len(json.loads(question.options)):
        raise ValueError("Choose one of the options")
    correct = option == question.answer
    entries = _answers(attempt)
    entries.append({"question_id": question.id, "option": option, "correct": correct, "level": LEVELS[attempt.level_index]})
    attempt.answers = json.dumps(entries)
    level = LEVELS[attempt.level_index]
    level_total = len(bank_for(db, attempt.skill, level))
    level_answers = [e for e in entries if e["level"] == level]
    if len(level_answers) < level_total:
        db.commit()
        return
    # The level is complete: pass it or stop here.
    correct_here = sum(1 for e in level_answers if e["correct"])
    if correct_here >= PASS_CORRECT:
        next_index = _next_level_with_questions(db, attempt.skill, attempt.level_index + 1)
        if next_index < len(LEVELS):
            attempt.level_index = next_index
            db.commit()
            return
        _finish(db, student, attempt, LEVELS[-1], "done")
        return
    result = LEVELS[attempt.level_index - 1] if attempt.level_index > 0 else DEFAULT_LEVEL
    _finish(db, student, attempt, result, "done")


def skip(db: DBSession, student: Student, attempt: PlacementAttempt) -> None:
    if attempt.status != "in_progress":
        raise ValueError("This part of the test is already finished")
    _finish(db, student, attempt, DEFAULT_LEVEL, "skipped")


def latest_attempt(db: DBSession, student: Student, skill: str) -> PlacementAttempt | None:
    return (
        db.query(PlacementAttempt)
        .filter(PlacementAttempt.student_id == student.id, PlacementAttempt.skill == skill)
        .order_by(PlacementAttempt.started_at.desc(), PlacementAttempt.id.desc())
        .first()
    )


def skill_view(db: DBSession, student: Student, skill: str) -> dict:
    attempt = latest_attempt(db, student, skill)
    view = {"skill": skill, "label": SKILLS[skill], "status": "new", "level": None, "question": None}
    if attempt is None:
        return view
    view["status"] = attempt.status
    if attempt.status in ("done", "skipped"):
        view["level"] = attempt.result_level
        return view
    question = current_question(db, attempt)
    if question is not None:
        view["question"] = {
            "id": question.id,
            "text": question.text,
            "options": json.loads(question.options),
            "level": question.level,
            "audio": question.audio_text if skill == "listening" else "",
            "number": len(_answers(attempt)) + 1,
        }
    return view


def placement_state(db: DBSession, student: Student) -> dict:
    return {
        "levels": skill_levels(student),
        "skills": [skill_view(db, student, skill) for skill in SKILLS],
    }
