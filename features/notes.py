"""
Note taking for the assistant.

    "sudo add a note"   -> the robot asks what to write, then every sentence you
                           say becomes the next point (1, 2, 3 ... max 10)
    "sudo open notes"   -> opens the notes card
    "sudo save notes"   -> saves all points to notes/notes.txt in the project

While you are taking notes, anything you say WITHOUT "sudo" is written as a point.
Start with "sudo" to give a normal command (like "sudo what time is it").
These also work during a note: delete last point, delete point 3,
read notes, cancel notes, close notes.
"""

import json
import re
from datetime import datetime
from pathlib import Path


MAX_POINTS = 10
MAX_POINT_LENGTH = 300

# If nothing is said for this long, the robot goes back to waiting for "sudo".
NOTE_IDLE_SECONDS = 300

# <project>/notes/notes.txt   (this file lives in <project>/features/)
NOTES_FILE = Path(__file__).resolve().parent.parent / "notes" / "notes.txt"


class Reply(str):
    """
    A reply text that can also say what to speak:
        speech=None  -> speak the text (default)
        speech=""    -> stay silent (the notes card shows the result)
        speech="..." -> speak this instead of the text
    """

    def __new__(cls, text, speech=None):
        obj = super().__new__(cls, text)
        obj.speech = speech
        return obj


# ----------------------------------------------------------------------------
# Understanding commands
# ----------------------------------------------------------------------------

def _norm(text):
    text = re.sub(r"[^\w\s']", " ", text.lower())
    return " ".join(text.split())


_NOUN = r"(?:notes?|points?|notebook|note\s*card|note\s*taking)"
_DET = r"(?:(?:my|the|all|a|an|new)\s+)*"

_START_RE = re.compile(
    r"^(?:add|take|make|write|create|start|begin|new)\s+" + _DET + r"(?:note|notes|point|points|note\s*taking)$"
)
_START_INLINE_RE = re.compile(
    r"^(?:add|take|write|make)\s+(?:a\s+)?(?:note|point)\s+(?:that|saying)\s+(.+)$", re.I
)
_SAVE_RE = re.compile(r"^(?:save|store|finish|finalize|complete)\s+" + _DET + _NOUN + r"$")
_OPEN_RE = re.compile(r"^(?:open|show|view|display|see)\s+" + _DET + _NOUN + r"$")
_CLOSE_RE = re.compile(r"^(?:close|hide|dismiss)\s+" + _DET + _NOUN + r"$")
_READ_RE = re.compile(r"^read\s+" + _DET + r"(?:notes?|points?)(?:\s+back)?$")
_CANCEL_RE = re.compile(r"^(?:cancel|discard|abort)\s+" + _DET + _NOUN + r"$")
_DELETE_LAST_RE = re.compile(
    r"^(?:delete|remove|undo|erase)\s+(?:the\s+)?(?:last|previous)\s+(?:note|point|line|one)$|^undo$"
)
_DELETE_NUMBER_RE = re.compile(r"^(?:delete|remove|erase)\s+(?:note|point)\s+(\d+)$")

_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


# ----------------------------------------------------------------------------
# Notes manager
# ----------------------------------------------------------------------------

class NotesManager:

    def __init__(self, notes_file=NOTES_FILE):
        self.notes_file = Path(notes_file)
        self.active = False        # taking notes right now
        self.points = []           # unsaved points of the current note
        self.card_open = False     # is the notes card shown?
        self.version = 0           # increases whenever something changes
        self._saved_cache = None   # saved notes, read from the file once

    # ------------------------------------------------------------------
    # Entry point (called by command_handler.py)
    # ------------------------------------------------------------------

    def handle(self, original, heard_wake, rest):
        """
        original   - what the user said/typed
        heard_wake - the text started with "sudo"
        rest       - the text without the wake word
        Returns a Reply, or None if this is not about notes.
        """

        rest = rest.strip()
        lowered = _norm(rest)

        # Commands that work any time
        if _SAVE_RE.match(lowered):
            return self.save()

        if _OPEN_RE.match(lowered):
            return self.open_card()

        if _CLOSE_RE.match(lowered):
            return self.close_card()

        if _READ_RE.match(lowered):
            return self.read_notes()

        if _START_RE.match(lowered):
            return self.start_session()

        inline = _START_INLINE_RE.match(rest)
        if inline:
            return self.start_session(first_point=inline.group(1))

        if not self.active:
            return None

        # ---- inside a note-taking session ----

        if _CANCEL_RE.match(lowered):
            return self.cancel()

        if _DELETE_LAST_RE.match(lowered):
            return self.delete_point(len(self.points))

        match = _DELETE_NUMBER_RE.match(lowered)
        if match:
            return self.delete_point(int(match.group(1)))

        if heard_wake:
            return None          # a normal assistant command, keep the note open

        return self.add_point(original)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def start_session(self, first_point=None):
        if self.active:
            if first_point:
                return self.add_point(first_point)
            return Reply("I'm already taking notes. Go ahead.")

        self.active = True
        self.card_open = True
        self.version += 1

        if first_point:
            return self.add_point(first_point)

        return Reply("What do you want to write?")

    def add_point(self, text):
        text = " ".join(str(text).split())[:MAX_POINT_LENGTH]

        if not text:
            return Reply("", speech="")

        if len(self.points) >= MAX_POINTS:
            return Reply(
                f"You've reached the limit of {MAX_POINTS} points. "
                "Say save notes to save them."
            )

        text = text[0].upper() + text[1:]
        self.points.append(text)
        self.card_open = True
        self.version += 1

        number = len(self.points)

        if number == MAX_POINTS:
            return Reply(
                f"Point {number} added. That's the limit of {MAX_POINTS} points. "
                "Say save notes to save them."
            )

        # Silent: the card shows the new point.
        return Reply(f"Point {number} added: {text}", speech="")

    def delete_point(self, number):
        if not self.points:
            return Reply("There are no points to delete.")

        if number < 1 or number > len(self.points):
            return Reply(f"There is no point {number}.")

        removed = self.points.pop(number - 1)
        self.version += 1
        return Reply(f"Deleted point {number}: {removed}", speech=f"Deleted point {number}.")

    def cancel(self):
        count = len(self.points)
        self.points = []
        self.active = False
        self.card_open = False
        self.version += 1

        if count:
            return Reply(f"Discarded {count} point{'s' if count != 1 else ''}.")
        return Reply("Okay, I stopped taking notes.")

    def save(self):
        if not self.points:
            if self.active:
                return Reply("You haven't added any points yet.")
            return Reply("There's nothing to save. Say add a note to start.")

        count = len(self.points)
        stamp = datetime.now().strftime("%d %b %Y, %I:%M %p")
        block = f"=== {stamp} ===\n"
        block += "\n".join(f"{i}. {p}" for i, p in enumerate(self.points, 1))
        block += "\n\n"

        try:
            self.notes_file.parent.mkdir(parents=True, exist_ok=True)
            with self.notes_file.open("a", encoding="utf-8") as file:
                file.write(block)
        except OSError as error:
            return Reply(f"I couldn't save the notes: {error}")

        self.points = []
        self.active = False
        self.card_open = True      # show the saved notes
        self._saved_cache = None
        self.version += 1

        word = "point" if count == 1 else "points"
        return Reply(
            f"Saved {count} {word} to notes/{self.notes_file.name}.",
            speech=f"Saved {count} {word}."
        )

    def open_card(self):
        saved = self._load_saved()

        if not self.points and not saved and not self.active:
            return Reply("You don't have any notes yet. Say add a note to start.")

        self.card_open = True
        self.version += 1
        return Reply("Your notes:\n" + self._format_text(), speech="Here are your notes.")

    def close_card(self):
        self.card_open = False
        self.version += 1
        return Reply("Closed the notes.", speech="")

    def read_notes(self):
        points = self.points

        if not points:
            saved = self._load_saved()
            if not saved:
                return Reply("You don't have any notes yet.")
            points = saved[-1]["points"]

        speech = " ".join(f"Point {i}. {p}." for i, p in enumerate(points, 1))
        text = "\n".join(f"{i}. {p}" for i, p in enumerate(points, 1))
        return Reply(text, speech=speech)

    # ------------------------------------------------------------------
    # Saved notes (file)
    # ------------------------------------------------------------------

    def _load_saved(self):
        """Saved notes, oldest first: [{"title": ..., "points": [...]}]."""

        if self._saved_cache is not None:
            return self._saved_cache

        sheets = []

        try:
            lines = self.notes_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []

        current = None

        for line in lines:
            header = re.match(r"^===\s*(.+?)\s*===\s*$", line)
            point = re.match(r"^\s*\d+\.\s+(.*)$", line)

            if header:
                current = {"title": header.group(1), "points": []}
                sheets.append(current)
            elif point and current is not None:
                current["points"].append(point.group(1))

        self._saved_cache = [s for s in sheets if s["points"]]
        return self._saved_cache

    def _format_text(self, sheets=3):
        parts = []

        if self.points:
            parts.append("New note (not saved yet):")
            parts.extend(f"{i}. {p}" for i, p in enumerate(self.points, 1))

        for sheet in list(reversed(self._load_saved()))[:sheets]:
            parts.append(f"\nSaved {sheet['title']}:")
            parts.extend(f"{i}. {p}" for i, p in enumerate(sheet["points"], 1))

        return "\n".join(parts).strip()

    # ------------------------------------------------------------------
    # For the notes card in the page
    # ------------------------------------------------------------------

    def snapshot(self):
        saved = self._load_saved()

        return {
            "visible": self.card_open,
            "active": self.active,
            "max": MAX_POINTS,
            "draft": list(self.points),
            "saved": list(reversed(saved))[:5],     # newest first
            "saved_total": len(saved),
        }

    def snapshot_json(self):
        return json.dumps(self.snapshot())


# One shared manager used by the whole app
notes = NotesManager()