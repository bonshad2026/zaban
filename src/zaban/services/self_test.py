import re
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session as DBSession

from zaban.models import SelfTest, SelfTestMessage, Student, Tenant, utcnow
from zaban.services.ai_gateway import complete
from zaban.services.curriculum import DEFAULT_LEVEL, band_code
from zaban.services.metering import ensure_quota, record_usage
from zaban.services.self_test_prompt import build_prompt

def choose_kind(kind: str, level: str) -> str:
    # "suggested" lets the system choose: beginners get plain questions, higher levels get a mix.
    if kind != "suggested":
        return kind
    return "qa" if level in ("A1", "A2") else "mixed"


def _system_prompt(db: DBSession, student: Student, kind_requested: str, skill: str, minutes: int, level: str) -> str:
    # The administrator's self-test template, filled for this test. See services/self_test_prompt.py.
    text, _ = build_prompt(db, student, kind_requested, choose_kind(kind_requested, level), skill, minutes, level)
    return text


def _history(test: SelfTest) -> list[dict]:
    return [{"role": m.role, "content": m.content} for m in test.messages]


def _is_expired(test: SelfTest) -> bool:
    return utcnow() >= test.ends_at


def _ask(db: DBSession, student: Student, test: SelfTest, system: str, messages: list[dict], max_tokens: int) -> str:
    tenant = db.get(Tenant, student.tenant_id)
    ensure_quota(tenant)
    result = complete(system, messages, max_tokens=max_tokens)
    record_usage(db, tenant, test.id, result.input_tokens, result.output_tokens)
    return result.text


def start_test(db: DBSession, student: Student, kind: str, skill: str, minutes: int) -> SelfTest:
    level = student.cefr_level or DEFAULT_LEVEL
    test = SelfTest(
        student_id=student.id,
        kind=kind,
        skill=skill,
        minutes=minutes,
        level_used=level,
        ends_at=utcnow() + timedelta(minutes=minutes),
    )
    db.add(test)
    db.flush()
    system = _system_prompt(db, student, kind, skill, minutes, level)
    opening = _ask(db, student, test, system, [{"role": "user", "content": "Start the test now."}], 300)
    db.add(SelfTestMessage(test_id=test.id, role="assistant", content=opening))
    db.commit()
    return test


def answer_test(db: DBSession, student: Student, test: SelfTest, content: str) -> SelfTest:
    if test.status != "active":
        raise HTTPException(status_code=409, detail="This test is finished")
    if _is_expired(test):
        finish_test(db, student, test)
        return test
    db.add(SelfTestMessage(test_id=test.id, role="user", content=content.strip()))
    db.flush()
    system = _system_prompt(db, student, test.kind, test.skill, test.minutes, test.level_used or DEFAULT_LEVEL)
    reply = _ask(db, student, test, system, _history(test), 300)
    db.add(SelfTestMessage(test_id=test.id, role="assistant", content=reply))
    db.commit()
    return test


SCORE_LINE = re.compile(r"^\s*SCORE:\s*(\d{1,3})\s*$", re.MULTILINE)


def split_score(text: str) -> tuple[str, float | None]:
    # The evaluation ends with a line "SCORE: <0 to 100>". The line is taken out of the text the learner reads.
    match = SCORE_LINE.search(text)
    if match is None:
        return text.strip(), None
    score = min(100, int(match.group(1)))
    return SCORE_LINE.sub("", text).strip(), float(score)


def finish_test(db: DBSession, student: Student, test: SelfTest) -> SelfTest:
    if test.status == "finished":
        return test
    level = test.level_used or DEFAULT_LEVEL
    system = _system_prompt(db, student, test.kind, test.skill, test.minutes, level)
    closing = _history(test) + [
        {
            "role": "user",
            "content": (
                "The test is over. Write a short evaluation: strengths, weak points, and next steps. "
                "Then add one last line exactly in this form: SCORE: <a whole number from 0 to 100>, "
                "judging the answers for the learner's level."
            ),
        }
    ]
    test.result, test.score = split_score(_ask(db, student, test, system, closing, 600))
    test.status = "finished"
    db.commit()
    return test


def owned_test(db: DBSession, student: Student, test_id: str) -> SelfTest:
    test = db.get(SelfTest, test_id)
    if test is None or test.student_id != student.id:
        raise HTTPException(status_code=404, detail="Not found")
    return test
