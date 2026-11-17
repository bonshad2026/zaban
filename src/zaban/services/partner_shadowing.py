# Shadowing (docs/conversation-partner.md, section 4.3), browser-only version (decision of phase 5).
# The browser turns the learner's speech into words. The server compares those words with the target sentence.
# This is a check of the words, not of the sound.
import re
from collections import Counter

WORD = re.compile(r"[a-z0-9']+")


def words(text: str) -> list[str]:
    return WORD.findall(text.lower().replace("’", "'"))


def compare(target: str, said: str) -> dict:
    # Order does not count here. A word missing from what was said is "missing"; a word said but not in the target is "extra".
    wanted, heard = Counter(words(target)), Counter(words(said))
    missing = sorted((wanted - heard).elements(), key=words(target).index)
    extra = sorted((heard - wanted).elements(), key=words(said).index)
    total = sum(wanted.values()) or 1
    return {
        "target": target,
        "missing": missing,
        "extra": extra,
        "score": round(100 * (total - len(missing)) / total),
    }
