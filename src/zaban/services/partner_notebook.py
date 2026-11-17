# The teacher notebook of one learner (docs/conversation-partner.md, section 14). The learner never sees it.
import re
from datetime import datetime

from sqlalchemy.orm import Session as DBSession

from zaban.models import LearnerMemory, LearnerMemoryVersion, Student

# The fixed headings, in order (section 14.2).
NOTEBOOK_HEADINGS = [
    "خلاصه",
    "شخصیت و سبک حرف زدن",
    "چه چیزی جواب می‌دهد",
    "تسلط و نقاط قوت",
    "نقاط ضعف و الگوهای خطا",
    "موضوع‌هایی که صحبت شده",
    "موضوع‌های پیشنهادی بعدی",
    "موضوع‌های باز و قول‌ها",
    "آزمون‌ها",
    "تاریخچه‌ی کوتاه",
]

# The writing rules sent with each update (section 14.4). The administrator may change them later.
NOTEBOOK_RULES = (
    "You keep a teacher's notebook about one adult English learner.\n"
    "Update the notebook with the new event. Keep every heading, in this order, each as a line starting with '## ':\n"
    + "\n".join(f"## {heading}" for heading in NOTEBOOK_HEADINGS)
    + "\nWrite in Persian. Keep it under {max_words} words.\n"
    "Keep what is still true. Change what the event shows is no longer true. Remove what is old and unimportant.\n"
    "Write observations with short real examples from the learner's own sentences.\n"
    "Never write full names, phone numbers, emails, addresses, passwords or IDs.\n"
    "Do not copy numbers the system already stores (levels, error counts). Describe what they mean in practice.\n"
    "Return only the full notebook."
)


def notebook_problems(text: str, max_words: int, display_name: str = "") -> list[str]:
    # The checks of section 14.4 step 3. An empty list means the notebook can be saved.
    problems = []
    for heading in NOTEBOOK_HEADINGS:
        if not re.search(rf"^##\s*{re.escape(heading)}\s*$", text, re.MULTILINE):
            problems.append(f"missing heading: {heading}")
    if len(text.split()) > max_words:
        problems.append(f"longer than {max_words} words")
    if re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text):
        problems.append("contains an email address")
    if re.search(r"\d{7,}", text):
        problems.append("contains a long number")
    if re.search(r"https?://|www\.", text, re.IGNORECASE):
        problems.append("contains a link")
    name = display_name.strip()
    if len(name) >= 3 and name in text:
        problems.append("contains the learner's name")
    return problems


def current_notebook(db: DBSession, student: Student) -> str:
    row = db.get(LearnerMemory, student.id)
    return row.text if row else ""


def save_notebook(db: DBSession, student: Student, text: str, event: str, now: datetime) -> None:
    # The notebook and its new version are written together. The caller decides when to commit.
    row = db.get(LearnerMemory, student.id)
    if row is None:
        db.add(LearnerMemory(student_id=student.id, text=text, updated_at=now))
    else:
        row.text = text
        row.updated_at = now
    db.add(LearnerMemoryVersion(student_id=student.id, text=text, event=event, created_at=now))
