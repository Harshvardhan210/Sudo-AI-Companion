"""
Reminder feature (no Qt code here, so it is easy to test).

Flow:
    "remind me in 5 minutes"            -> assistant asks for the reminder name
    "drink water"                       -> reminder is set, robot shows a countdown
    "remind me to call mom in 2 hours"  -> name is already known, no question asked
"""

import re
import time


# How long the assistant waits for the reminder name (seconds)
PENDING_SECONDS = 20

# Longest reminder allowed
MAX_SECONDS = 24 * 60 * 60

DEFAULT_NAME = "Reminder"

WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "ninety": 90, "a": 1, "an": 1,
}

UNIT_SECONDS = {
    "second": 1, "sec": 1,
    "minute": 60, "min": 60,
    "hour": 3600, "hr": 3600,
}

_NUM = r"\d+(?:\.\d+)?|" + "|".join(sorted(WORD_NUMBERS, key=len, reverse=True))
_UNIT = r"seconds?|secs?|minutes?|mins?|hours?|hrs?"

# "5 minutes", "an hour", "1 hour and a half"
_PART_NUMBER = rf"(?:{_NUM})\s*(?:and a half\s*)?(?:{_UNIT})"
# "half an hour", "half a minute"
_PART_HALF = r"half\s+(?:an?\s+)?(?:hour|hr|minute|min)"
# "an hour and a half", "2 hours and a half"
_PART_AND_HALF = rf"(?:{_NUM})\s*(?:{_UNIT})\s+and a half"
_PART = rf"(?:{_PART_AND_HALF}|{_PART_NUMBER}|{_PART_HALF})"

# Full time expression with its connecting words:
# "in 1 hour 30 minutes", "for 5 minutes", "after half an hour from now"
_DURATION_RE = re.compile(
    rf"(?:\b(?:in|after|for|within)\s+)?\b{_PART}(?:\s*(?:and\s+)?{_PART})*(?:\s+from now)?\b"
)
_PART_AND_HALF_RE = re.compile(rf"\b({_NUM})\s*({_UNIT})\s+and a half\b")
_PART_NUMBER_RE = re.compile(rf"\b({_NUM})\s*(and a half\s*)?({_UNIT})\b")
_PART_HALF_RE = re.compile(r"\bhalf\s+(?:an?\s+)?(hour|hr|minute|min)\b")

_REQUEST_RE = re.compile(
    r"^(?:please\s+)?(?:can you\s+)?"
    r"(?:set\s+(?:a\s+|an\s+|the\s+)?reminder|create\s+(?:a\s+)?reminder|"
    r"add\s+(?:a\s+)?reminder|remind\s+me|reminder)\b"
)

_CANCEL_RE = re.compile(
    r"^(?:cancel|stop|delete|remove|clear)\s+(?:all\s+|my\s+|the\s+)*reminders?$"
)

_CANCEL_NAME_WORDS = {"cancel", "never mind", "nevermind", "stop", "forget it"}


def _to_number(token):
    token = token.strip().lower()
    if token in WORD_NUMBERS:
        return WORD_NUMBERS[token]
    return float(token)


def _unit_seconds(unit):
    unit = unit.lower()
    for key, value in UNIT_SECONDS.items():
        if unit.startswith(key):
            return value
    return 0


def parse_duration(text):
    """Return seconds found in text, or None. "1 hour 30 minutes" -> 5400."""

    text = text.lower()
    total = 0.0
    found = False

    # Longer phrases first, and remove each from the text once counted so
    # "an hour and a half" / "half an hour" are not counted twice.
    for amount, unit in _PART_AND_HALF_RE.findall(text):
        total += (_to_number(amount) + 0.5) * _unit_seconds(unit)
        found = True
    text = _PART_AND_HALF_RE.sub(" ", text)

    for unit in _PART_HALF_RE.findall(text):
        total += 0.5 * _unit_seconds(unit)
        found = True
    text = _PART_HALF_RE.sub(" ", text)

    for amount, half, unit in _PART_NUMBER_RE.findall(text):
        value = _to_number(amount) + (0.5 if half else 0)
        total += value * _unit_seconds(unit)
        found = True

    if not found:
        return None

    return int(round(total))


def format_duration(seconds):
    """5400 -> "1 hour 30 minutes"."""

    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if secs:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")

    return " ".join(parts) or "0 seconds"


def _clean_name(text):
    text = re.sub(r"[^\w\s'&\-\u0900-\u097F]|[\u0964\u0965]", " ", text.lower())
    text = " ".join(text.split())

    # Remove joining words at the start/end: "to drink water" -> "drink water"
    while True:
        new = re.sub(r"^(?:to|that|about|called|named|for|as|and)\s+", "", text)
        new = re.sub(r"\s+(?:to|and|for|in|after)$", "", new)
        if new == text:
            break
        text = new

    return text.strip()


class ReminderManager:

    def __init__(self):
        self.pending = None      # {"seconds": int, "expires": float}
        self.active = {}         # id -> reminder dict
        self._next_id = 1
        self.version = 0         # increases every time the active list changes

    # ------------------------------------------------------------------
    # Understanding commands
    # ------------------------------------------------------------------

    def is_reminder_request(self, command):
        return bool(_REQUEST_RE.match(command.strip().lower()))

    def is_cancel_request(self, command):
        return bool(_CANCEL_RE.match(command.strip().lower()))

    def has_pending(self):
        if self.pending and time.time() > self.pending["expires"]:
            # Expired, but not yet announced: pop_expired_pending() handles it.
            return False
        return self.pending is not None

    # ------------------------------------------------------------------
    # Conversation
    # ------------------------------------------------------------------

    def start_request(self, command):
        """Handle "remind me in 5 minutes" (and variants)."""

        command = command.strip().lower()
        rest = _REQUEST_RE.sub("", command, count=1).strip()

        seconds = parse_duration(rest)

        if not seconds:
            return (
                "How long should I wait? "
                "For example, say: remind me in 5 minutes."
            )

        if seconds > MAX_SECONDS:
            return "I can set reminders up to 24 hours long."

        # Whatever is left after removing the time is the reminder name.
        name = _clean_name(_DURATION_RE.sub(" ", rest))

        if name:
            return self._create(name, seconds)

        self.pending = {
            "seconds": seconds,
            "expires": time.time() + PENDING_SECONDS,
        }
        return "What should I call this reminder?"

    def handle_name(self, answer):
        """The user's reply to "What should I call this reminder?"."""

        pending = self.pending
        self.pending = None

        lowered = answer.strip().lower()

        if lowered in _CANCEL_NAME_WORDS:
            return "Okay, I cancelled the reminder."

        name = _clean_name(answer) or DEFAULT_NAME.lower()
        return self._create(name, pending["seconds"])

    def pop_expired_pending(self):
        """
        Called regularly. If nobody answered in time, create the reminder with
        the default name and return it (otherwise return None).
        """

        if self.pending and time.time() > self.pending["expires"]:
            seconds = self.pending["seconds"]
            self.pending = None
            response = self._create(DEFAULT_NAME.lower(), seconds)
            return response

        return None

    # ------------------------------------------------------------------
    # Active reminders
    # ------------------------------------------------------------------

    def _create(self, name, seconds):
        reminder = {
            "id": self._next_id,
            "name": name,
            "total": seconds,
            "ends_at": time.time() + seconds,
        }
        self._next_id += 1
        self.active[reminder["id"]] = reminder
        self.version += 1

        return f"Reminder set: {name}, in {format_duration(seconds)}."

    def pop_due(self):
        """Return (and remove) reminders whose time is up."""

        now = time.time()
        due = [r for r in self.active.values() if r["ends_at"] <= now]

        for reminder in due:
            del self.active[reminder["id"]]

        if due:
            self.version += 1

        return sorted(due, key=lambda r: r["ends_at"])

    def cancel_all(self):
        had_pending = self.pending is not None
        count = len(self.active)

        self.pending = None
        self.active.clear()

        if count:
            self.version += 1

        if count:
            return f"Cancelled {count} reminder{'s' if count != 1 else ''}."
        if had_pending:
            return "Okay, I cancelled the reminder."
        return "You have no reminders."

    def snapshot(self):
        """Active reminders as plain data for the page (soonest first)."""

        return [
            {
                "id": r["id"],
                "name": r["name"],
                "total": r["total"],
                "ends_at_ms": int(r["ends_at"] * 1000),
            }
            for r in sorted(self.active.values(), key=lambda r: r["ends_at"])
        ]


# One shared manager used by the whole app
reminders = ReminderManager()