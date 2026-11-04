from datetime import datetime

from zaban.models import Plan, TutorSession

MIN_SESSIONS_FOR_STATUS = 3
CEFR_BANDS = [(20, "A1"), (40, "A2"), (60, "B1"), (80, "B2"), (101, "C1")]


def cefr_from_score(score: int) -> str:
    for upper_bound, level in CEFR_BANDS:
        if score < upper_bound:
            return level
    return "C1"


def build_milestones(months: int) -> list[dict]:
    return [{"month": month, "target_percent": round(100 * month / months)} for month in range(1, months + 1)]


def planned_percent(plan: Plan, now: datetime) -> float:
    total = (plan.end_date - plan.start_date).total_seconds()
    if total <= 0:
        return 100.0
    elapsed = (now - plan.start_date).total_seconds()
    return round(min(100.0, max(0.0, elapsed / total * 100)), 1)


def actual_percent(sessions: list[TutorSession]) -> float | None:
    # MVP placeholder: average lesson score. Replace with the real progress model later.
    scores = [s.score for s in sessions if s.status == "completed" and s.score is not None]
    if len(scores) < MIN_SESSIONS_FOR_STATUS:
        return None
    return round(sum(scores) / len(scores), 1)


def progress_status(planned: float, actual: float | None) -> str:
    if actual is None:
        return "insufficient_data"
    difference = actual - planned
    if difference >= 10:
        return "ahead"
    if difference > -10:
        return "on_track"
    if difference > -25:
        return "behind"
    return "well_behind"
