# The numbers and rules the administrator sets for the conversation partner (docs/conversation-partner.md, section 15.3).
# Each value is stored as one AppSetting row. An empty or missing row gives the default below.
from sqlalchemy.orm import Session as DBSession

from zaban.services.settings_store import get_setting, set_setting

from zaban.services.partner_policy import LEVEL_CODES, parse_override

RHYTHM_MODES = [
    "conversation", "translation", "review", "summary", "shadowing", "pronunciation",
    "task", "functions", "phrases", "casual", "listening", "story", "poetry", "repeat",
]

SHARED_RULES_DEFAULT = (
    "فارسی فقط برای رفع ابهام و در یک جمله‌ی کوتاه؛ زبان‌آموز حدود ۷۰٪ زمان صحبت کند؛ "
    "فقط روی تمرین انگلیسی بماند؛ از دفترچه‌ی معلم استفاده کند."
)

# kind: choice, int, int_list (comma separated numbers), pairs (LEVEL:number), rhythm (mode:percent), text.
PARTNER_SETTINGS = [
    {"key": "partner_engine", "label": "روال درس", "kind": "choice", "choices": ["old", "new"], "default": "old",
     "help": "قدیم: روال فعلی درس. جدید: گفتگوی شریک. تا فاز ۳ روی «قدیم» بماند."},
    {"key": "partner_mastery_count", "label": "تعداد گفتگوی تسلط عبارت", "kind": "int", "min": 1, "max": 10, "default": "2",
     "help": "عبارت وقتی تسلط می‌گیرد که در این تعداد گفتگوی جدا، بدون کمک به کار رود."},
    {"key": "partner_review_intervals", "label": "فاصله‌های مرور (روز)", "kind": "int_list", "min": 1, "max": 365, "default": "3,7,14,30",
     "help": "فاصله‌ها به ترتیب. بعد از آخرین فاصله، عبارت متسلط با همان فاصله ادامه می‌یابد."},
    {"key": "partner_level_up_sessions", "label": "جلسه‌ی متوالی برای ارتقای سطح", "kind": "int", "min": 1, "max": 10, "default": "2"},
    {"key": "partner_level_down_sessions", "label": "جلسه‌ی متوالی برای پایین‌آوردن سطح", "kind": "int", "min": 1, "max": 10, "default": "3"},
    {"key": "partner_phrases_per_prompt", "label": "تعداد عبارت در هر پرامپت", "kind": "int", "min": 0, "max": 10, "default": "3"},
    {"key": "partner_errors_per_prompt", "label": "تعداد خطای هدف در هر پرامپت", "kind": "int", "min": 0, "max": 5, "default": "1"},
    {"key": "partner_error_window_sessions", "label": "تعداد جلسه‌ی اخیر برای خطای هدف", "kind": "int", "min": 1, "max": 50, "default": "3"},
    {"key": "partner_memory_max_words", "label": "سقف دفترچه‌ی معلم (کلمه)", "kind": "int", "min": 100, "max": 5000, "default": "800"},
    {"key": "partner_token_reserve", "label": "ذخیره‌ی توکن برای پایان جلسه", "kind": "int", "min": 0, "max": 1000000, "default": "5000",
     "help": "توکنی که از اشتراک زبان‌آموز برای خلاصه و دفترچه کنار گذاشته می‌شود."},
    {"key": "partner_token_warn_percents", "label": "آستانه‌های هشدار مصرف توکن (٪)", "kind": "int_list", "min": 1, "max": 99, "default": "80,90"},
    {"key": "partner_expiry_warn_days", "label": "هشدار انقضای پلن (روز مانده)", "kind": "int", "min": 0, "max": 30, "default": "3"},
    {"key": "partner_min_messages_eval", "label": "کمترین پیام زبان‌آموز برای ارزیابی", "kind": "int", "min": 1, "max": 100, "default": "3",
     "help": "جلسه‌ی کوتاه‌تر از این، بدون ارزیابی ثبت می‌شود."},
    {"key": "partner_translation_seconds", "label": "زمان هر جمله در ترجمه‌ی ذهنی (ثانیه)", "kind": "pairs", "default": "A1:20,A2:15,B1:10,B2:7",
     "help": "بر اساس سطح روانی. مثلاً A1:20 یعنی برای A1 بیست ثانیه."},
    {"key": "partner_default_rhythm", "label": "ریتم پیش‌فرض جلسه (درصد)", "kind": "rhythm",
     "default": "conversation:60,translation:20,review:10,summary:10", "help": "جمع درصدها باید ۱۰۰ باشد."},
    {"key": "partner_shared_rules", "label": "قواعد مشترک", "kind": "text", "default": SHARED_RULES_DEFAULT},
    {"key": "partner_mode_rules", "label": "قواعد هر حالت درس", "kind": "text", "default": "",
     "help": "برای همه‌ی حالت‌های ریتم درس (گفتگو، ترجمه، مرور، جمع‌بندی)."},
    {"key": "partner_free_rules", "label": "قواعد گفتگوی آزاد", "kind": "text", "default": "",
     "help": "فقط برای گفتگوی آزاد. مثلاً لحن یا موضوع‌های ترجیحی."},
    {"key": "partner_level_policy", "label": "جدول سیاست سطح", "kind": "policy", "default": "",
     "help": "هر خط: سطح | جمله | واژگان | پرسش | اصلاح | نوبت (به انگلیسی، چون در پرامپت می‌رود). خالی یعنی جدول پیش‌فرض."},
]

SPEC_BY_KEY = {spec["key"]: spec for spec in PARTNER_SETTINGS}
TEXT_MAX_LENGTH = 4000


def partner_value(db: DBSession, key: str) -> str:
    return get_setting(db, key, SPEC_BY_KEY[key]["default"])


def normalize(spec: dict, raw: str) -> str:
    # Returns the value in the stored form, or raises ValueError with a short English reason.
    value = raw.strip()
    kind = spec["kind"]
    if kind == "policy":
        try:
            parse_override(value)
        except ValueError as error:
            raise ValueError(f"{spec['key']}: {error}") from error
        return value
    if kind == "text":
        if len(value) > TEXT_MAX_LENGTH:
            raise ValueError(f"{spec['key']} is longer than {TEXT_MAX_LENGTH} characters")
        return value
    if kind == "choice":
        if value not in spec["choices"]:
            raise ValueError(f"{spec['key']} must be one of {', '.join(spec['choices'])}")
        return value
    if kind == "int":
        if not value.isdigit() or not spec["min"] <= int(value) <= spec["max"]:
            raise ValueError(f"{spec['key']} must be a whole number from {spec['min']} to {spec['max']}")
        return str(int(value))
    if kind == "int_list":
        parts = [p.strip() for p in value.split(",") if p.strip()]
        if not parts or not all(p.isdigit() and spec["min"] <= int(p) <= spec["max"] for p in parts):
            raise ValueError(f"{spec['key']} must be numbers from {spec['min']} to {spec['max']} separated by commas")
        return ",".join(str(int(p)) for p in parts)
    if kind == "pairs":
        pairs = []
        for part in value.split(","):
            code, _, seconds = part.strip().partition(":")
            if code.strip() not in LEVEL_CODES or not seconds.strip().isdigit() or not 1 <= int(seconds) <= 300:
                raise ValueError(f"{spec['key']} must look like A1:20,A2:15 with levels from A1 to C2")
            pairs.append(f"{code.strip()}:{int(seconds)}")
        return ",".join(pairs)
    if kind == "rhythm":
        shares = {}
        for part in value.split(","):
            mode, _, percent = part.strip().partition(":")
            if mode.strip() not in RHYTHM_MODES or not percent.strip().isdigit() or not 0 <= int(percent) <= 100:
                raise ValueError(f"{spec['key']} must look like conversation:60,translation:40 with modes from {', '.join(RHYTHM_MODES)}")
            shares[mode.strip()] = int(percent)
        if sum(shares.values()) != 100:
            raise ValueError(f"{spec['key']} percentages must add up to 100")
        return ",".join(f"{mode}:{percent}" for mode, percent in shares.items())
    raise ValueError(f"unknown kind {kind}")


def settings_view(db: DBSession) -> list[dict]:
    # One entry per setting: its current value, its default, and what the panel needs to draw the field.
    return [
        {**spec, "value": partner_value(db, spec["key"]), "is_default": get_setting(db, spec["key"]) == ""}
        for spec in PARTNER_SETTINGS
    ]


def save_settings(db: DBSession, values: dict[str, str]) -> None:
    # All values are checked before any is written, so a bad value saves nothing.
    checked = {}
    for key, raw in values.items():
        if key not in SPEC_BY_KEY:
            raise ValueError(f"unknown setting {key}")
        checked[key] = normalize(SPEC_BY_KEY[key], raw)
    for key, value in checked.items():
        set_setting(db, key, value)
