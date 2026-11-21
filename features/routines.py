"""
Routines: a saved list of commands you can run with one phrase.

Create one:
    "sudo create routine"             -> "What is the name of this routine?"
    "work"                           -> "What do you want to do in this routine?"
    "sudo add open naukri, open youtube, open vs code"
    "sudo close work routine"        -> saves it (you can keep adding steps until then)

Use it:
    "sudo run work routine"          -> does every step, one after the other
    "sudo close work routine"        -> closes the apps that routine opened
                                        (websites are left open: close those tabs yourself)
    "sudo show routines" / "sudo show work routine"
    "sudo delete work routine"

While you are creating a routine, anything you say WITHOUT "sudo" is added as steps.
Routines are saved in routines/routines.json in your project.
"""

import json
import re
import time
from pathlib import Path

from features.notes import Reply
from features.app_closer import close_application
from features.web_tools import is_website


MAX_ROUTINES = 20
MAX_STEPS = 15
MAX_NAME_LENGTH = 30

NAME_SECONDS = 20            # time to say the routine name
IDLE_SECONDS = 300           # creating a routine: back to normal after this much silence
CARD_AUTO_HIDE_SECONDS = 8   # the card closes by itself (unless you opened it)

# <project>/routines/routines.json   (this file lives in <project>/features/)
ROUTINES_FILE = Path(__file__).resolve().parent.parent / "routines" / "routines.json"

_FLAGS = re.I

# A step must start with one of these words
STEP_VERBS = {
    "open", "launch", "start", "close", "quit", "play", "search", "google", "find",
    "look", "lookup", "go", "goto", "visit", "browse", "show", "volume", "increase",
    "decrease", "mute", "unmute", "lock", "remind", "add", "set", "what", "tell",
    "take", "read", "battery", "check", "change", "speak", "switch", "youtube",
}

# Never allowed inside a routine
BLOCKED_STEP = re.compile(
    r"\b(shut\s?down|restart|reboot|confirm|delete|remove|erase|clear|cancel|kill|"
    r"terminate|force|routine|routines|sudo)\b", _FLAGS
)

_SPLIT_VERBS = r"(?:open|launch|start|close|play|google|visit|browse)"
_FOLDERS = {"desktop", "documents", "downloads", "pictures", "music", "videos"}

_CREATE_BARE = re.compile(r"^(?:create|make|new|start|build)\s+(?:a\s+|an\s+)?(?:new\s+)?routine$", _FLAGS)
_CREATE_NAMED = [
    re.compile(r"^(?:create|make|new|build)\s+(?:a\s+|an\s+)?(?:new\s+)?routine\s+(?:called|named)\s+(.+)$", _FLAGS),
    re.compile(r"^(?:create|make|new|build)\s+(?:a\s+|an\s+)?(?:new\s+)?(.+?)\s+routine$", _FLAGS),
]
_LIST = re.compile(r"^(?:show|list|open|view|display|see)\s+(?:me\s+)?(?:(?:my|all|the)\s+)*routines$|^what\s+routines\s+do\s+i\s+have$", _FLAGS)
_CLOSE_CARD = re.compile(r"^(?:close|hide|dismiss)\s+(?:(?:my|the|all)\s+)*routines$", _FLAGS)
_SHOW_ONE = re.compile(r"^(?:show|view|see|read)\s+(?:the\s+|my\s+)?(.+?)\s+routine(?:\s+steps)?$", _FLAGS)
_RUN = [
    re.compile(r"^(?:run|start|execute|launch|begin|open)\s+(?:the\s+|my\s+)?(.+?)\s+routine$", _FLAGS),
    re.compile(r"^(?:run|start|execute)\s+routine\s+(.+)$", _FLAGS),
]
_CLOSE_ROUTINE = re.compile(r"^(?:close|end|stop|quit)\s+(?:the\s+|my\s+)?(?:(.+?)\s+)?routine$", _FLAGS)
_DELETE = [
    re.compile(r"^(?:delete|remove)\s+(?:the\s+|my\s+)?(.+?)\s+routine$", _FLAGS),
    re.compile(r"^(?:delete|remove)\s+routine\s+(.+)$", _FLAGS),
]

# While creating
_FINISH = re.compile(r"^(?:close|finish|save|end|complete)\s+(?:the\s+|my\s+)?(?:(.+?)\s+)?routine$", _FLAGS)
_CANCEL = re.compile(r"^(?:cancel|discard|abort)\s+(?:the\s+|my\s+)?(?:(.+?)\s+)?routine$", _FLAGS)
_ADD = re.compile(r"^(?:add|include)\s+(.+)$", _FLAGS)
_DELETE_LAST = re.compile(r"^(?:delete|remove|undo)\s+(?:the\s+)?last\s+(?:step|command|action)$", _FLAGS)

_CANCEL_WORDS = {"cancel", "never mind", "nevermind", "forget it"}


def _norm(text):
    text = re.sub(r"[^\w\s']", " ", text.lower())
    return " ".join(text.split())


def clean_name(text):
    """"call it Work Routine!" -> "work"."""

    text = re.sub(r"^(?:name it|call it|it's called|its called|the name is|name is|called|named)\s+", "", text.strip(), flags=_FLAGS)
    text = re.sub(r"\s+routine$", "", text, flags=_FLAGS)

    # A name said in Hindi: spell it with English letters
    if re.search(r"[\u0900-\u097F]", text):
        try:
            from assistant.hindi_commands import romanize_text
            text = romanize_text(text)
        except Exception:
            pass

    text = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    return " ".join(text.split())[:MAX_NAME_LENGTH].strip()


# ----------------------------------------------------------------------------
# Splitting "open naukri, open youtube and open vs code" into steps
# ----------------------------------------------------------------------------

def _starts_with_verb(text):
    words = text.strip().lower().split()
    return bool(words) and words[0] in STEP_VERBS


def split_steps(text):
    text = re.sub(r"[{}\[\]\"“”]", " ", text)
    text = " ".join(text.split())

    steps = []

    for part in re.split(r"\s*(?:,|;|\band then\b|\bthen\b|\balso\b)\s*", text, flags=_FLAGS):
        # "... and open vs code": a new step only if a command word follows "and"
        pieces = re.split(r"\s+and\s+", part, flags=_FLAGS)
        merged = [pieces[0]]

        for piece in pieces[1:]:
            if _starts_with_verb(piece):
                merged.append(piece)
            else:
                merged[-1] += " and " + piece

        for piece in merged:
            # Spoken without commas: "open naukri open youtube open vs code"
            if re.match(r"^(?:open|launch|start|close)\b", piece, flags=_FLAGS):
                steps.extend(re.split(rf"\s+(?=(?:{_SPLIT_VERBS})\s)", piece, flags=_FLAGS))
            else:
                steps.append(piece)

    cleaned = []
    for step in steps:
        step = re.sub(r"^(?:please|and)\s+", "", step.strip(" .,"), flags=_FLAGS).strip().lower()
        if step:
            cleaned.append(step)

    return cleaned


def _check_step(step):
    """Return None if the step is fine, or the reason it can't be added."""

    if BLOCKED_STEP.search(step):
        return "routines can't do that"

    if not _starts_with_verb(step):
        return "I don't know that command"

    return None


# ----------------------------------------------------------------------------
# Routine manager
# ----------------------------------------------------------------------------

class RoutineManager:

    def __init__(self, routines_file=ROUTINES_FILE):
        self.routines_file = Path(routines_file)
        self.routines = self._load()     # {"work": ["open naukri", ...]}

        self.stage = None                # None | "name" | "steps"
        self.stage_until = 0.0           # when the current question times out
        self.name = ""                   # routine being created
        self.steps = []

        self.card_open = False
        self.sticky = False
        self.last_activity = 0.0
        self.version = 0

    # ------------------------------------------------------------------
    # File
    # ------------------------------------------------------------------

    def _load(self):
        try:
            data = json.loads(self.routines_file.read_text(encoding="utf-8"))
            return {
                str(name): [str(s) for s in steps]
                for name, steps in data.items()
                if isinstance(steps, list) and steps
            }
        except (OSError, ValueError, AttributeError):
            return {}

    def _save(self):
        try:
            self.routines_file.parent.mkdir(parents=True, exist_ok=True)
            self.routines_file.write_text(
                json.dumps(self.routines, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as error:
            return str(error)
        return None

    def _touch(self, sticky=False):
        self.card_open = True
        self.sticky = sticky
        self.last_activity = time.time()
        self.version += 1

    # ------------------------------------------------------------------
    # State for the bridge / command handler
    # ------------------------------------------------------------------

    def _expire(self):
        if self.stage == "name" and time.time() > self.stage_until:
            self._reset()
            self.card_open = False      # nobody answered: close the card too

    def _reset(self):
        self.stage = None
        self.name = ""
        self.steps = []
        self.stage_until = 0.0
        self.version += 1

    def busy(self):
        """Creating a routine right now?"""
        self._expire()
        return self.stage is not None

    def expect_seconds(self):
        """How long the next spoken phrase counts as an answer (0 = not waiting)."""
        self._expire()
        if self.stage == "name":
            return NAME_SECONDS
        if self.stage == "steps":
            return IDLE_SECONDS
        return 0

    # ------------------------------------------------------------------
    # Entry point (called by command_handler.py)
    # ------------------------------------------------------------------

    def handle(self, original, heard_wake, rest, busy_with=None):
        """
        Returns a Reply, or None if this is not about routines.
        A Reply with .run_steps set means "run these commands now".
        """

        self._expire()
        text = rest.strip().rstrip(".?!").strip()

        if not text:
            return None

        # ---- waiting for the routine name ----
        if self.stage == "name":
            if _norm(text) in _CANCEL_WORDS or _CANCEL.match(text):
                self._reset()
                return Reply("Okay, I cancelled the routine.")
            return self._set_name(text)

        # ---- creating: collecting steps ----
        if self.stage == "steps":
            match = _FINISH.match(text)
            if match:
                return self.finish(match.group(1))

            match = _CANCEL.match(text)
            if match:
                return self.cancel()

            if _DELETE_LAST.match(text):
                return self.delete_last_step()

            match = _ADD.match(text)
            if match:
                return self.add_steps(match.group(1))

            if not heard_wake and not _LIST.match(text):
                return self.add_steps(text)      # spoken steps without "sudo"

        # ---- commands that work any time ----
        if _CREATE_BARE.match(text):
            return self.start_creating(busy_with=busy_with)

        for pattern in _CREATE_NAMED:
            match = pattern.match(text)
            if match and clean_name(match.group(1)) not in ("a", "new", ""):
                return self.start_creating(match.group(1), busy_with=busy_with)

        if _LIST.match(text):
            return self.show_all()

        if _CLOSE_CARD.match(text):
            return self.close_card()

        match = _SHOW_ONE.match(text)
        if match:
            return self.show_one(match.group(1))

        for pattern in _RUN:
            match = pattern.match(text)
            if match:
                return self.run(match.group(1))

        for pattern in _DELETE:
            match = pattern.match(text)
            if match:
                return self.delete(match.group(1))

        match = _CLOSE_ROUTINE.match(text)
        if match and match.group(1):
            return self.close_apps(match.group(1))

        return None

    # ------------------------------------------------------------------
    # Creating
    # ------------------------------------------------------------------

    def start_creating(self, name=None, busy_with=None):
        if self.stage is not None:
            return Reply("I'm already creating a routine. Say close, then its name, routine, to finish it.")

        if busy_with:
            return Reply(f"You're {busy_with}. Please finish that first.")

        if len(self.routines) >= MAX_ROUTINES:
            return Reply(f"You already have {MAX_ROUTINES} routines. Delete one first.")

        self.steps = []
        self.name = ""
        self.stage = "name"
        self.stage_until = time.time() + NAME_SECONDS
        self._touch(sticky=True)

        if name:
            return self._set_name(name)

        return Reply("What is the name of this routine?")

    def _set_name(self, text):
        name = clean_name(text)

        if not name:
            self.stage_until = time.time() + NAME_SECONDS
            return Reply("I didn't catch the name. What should I call this routine?")

        if name in self.routines:
            self.stage_until = time.time() + NAME_SECONDS
            return Reply(f"You already have a routine called {name}. Please say a different name.")

        self.name = name
        self.stage = "steps"
        self.stage_until = 0.0
        self._touch(sticky=True)

        return Reply("What do you want to do in this routine?")

    def add_steps(self, text):
        added, skipped = [], []

        for step in split_steps(text):
            if step in self.steps or step in added:
                continue

            problem = _check_step(step)
            if problem:
                skipped.append(f"{step} ({problem})")
            elif len(self.steps) + len(added) >= MAX_STEPS:
                skipped.append(f"{step} (a routine can have {MAX_STEPS} steps)")
            else:
                added.append(step)

        self.steps.extend(added)
        self._touch(sticky=True)

        if not added and not skipped:
            return Reply("I didn't catch any command to add. Try: add open chrome, open youtube.")

        parts = []
        if added:
            parts.append("Added: " + ", ".join(added) + ".")
        if skipped:
            parts.append("Skipped: " + "; ".join(skipped) + ".")

        speech = ""
        if added:
            speech = f"Added {len(added)} step{'s' if len(added) != 1 else ''}."
        if skipped:
            speech += f" I skipped {len(skipped)}."

        return Reply(" ".join(parts), speech=speech.strip())

    def delete_last_step(self):
        if not self.steps:
            return Reply("There are no steps to delete.")

        removed = self.steps.pop()
        self._touch(sticky=True)
        return Reply(f"Removed the last step: {removed}", speech="Removed the last step.")

    def finish(self, said_name):
        if said_name and clean_name(said_name) not in (self.name, ""):
            return Reply(f"You're creating the {self.name} routine. Say close {self.name} routine to finish it.")

        if not self.steps:
            return Reply("This routine has no steps yet. Add some, for example: add open chrome. Or say cancel routine.")

        name, steps = self.name, list(self.steps)
        self.routines[name] = steps
        error = self._save()

        self.stage = None
        self.name = ""
        self.steps = []
        self._touch(sticky=False)

        extra = f" (I couldn't save the file: {error})" if error else ""
        return Reply(
            f"Saved the {name} routine with {len(steps)} step{'s' if len(steps) != 1 else ''}.{extra}\n"
            f"Say run {name} routine to start it.",
            speech=f"The {name} routine is saved with {len(steps)} step{'s' if len(steps) != 1 else ''}."
        )

    def cancel(self):
        self._reset()
        self.card_open = False
        return Reply("Okay, I cancelled the routine.")

    # ------------------------------------------------------------------
    # Using saved routines
    # ------------------------------------------------------------------

    def _find(self, query):
        """Returns (name, None) or (None, Reply)."""

        if not self.routines:
            return None, Reply("You don't have any routines yet. Say create routine to make one.")

        key = clean_name(re.sub(r"^(?:my|the)\s+", "", query.strip(), flags=_FLAGS))

        if key in self.routines:
            return key, None

        matches = [n for n in self.routines if n.startswith(key) or key in n.split()] if key else []

        if len(matches) == 1:
            return matches[0], None

        names = ", ".join(self.routines)

        if len(matches) > 1:
            return None, Reply(f"That matches more than one routine: {', '.join(matches)}.")

        return None, Reply(f"I don't have a routine called {key}. Your routines: {names}.")

    def run(self, query):
        name, problem = self._find(query)
        if problem:
            return problem

        steps = list(self.routines[name])
        self._touch(sticky=False)

        reply = Reply(f"Running the {name} routine...", speech=f"Starting your {name} routine.")
        reply.run_steps = steps
        reply.run_name = name
        return reply

    def _app_target(self, step):
        """The app a step opens ("open vs code" -> "vs code"), or None for websites/folders."""

        match = re.match(r"^(?:open|launch|start)\s+(?:the\s+)?(.+)$", step, flags=_FLAGS)
        if not match:
            return None

        target = match.group(1).strip()

        if target in _FOLDERS or is_website(target):
            return None

        return target

    def close_apps(self, query):
        """"close work routine": close the apps this routine opened."""

        name, problem = self._find(query)
        if problem:
            return problem

        steps = self.routines[name]
        targets = [t for t in (self._app_target(s) for s in steps) if t]
        has_other = len(targets) < len(steps)

        if not targets:
            return Reply(
                f"The {name} routine only opens websites or folders, so there is no app to close. "
                "Close the browser tabs yourself.",
                speech=f"The {name} routine has no apps to close."
            )

        results = [close_application(target) for target in targets]
        self._touch(sticky=False)

        text = f"Closing the {name} routine:\n" + "\n".join(f"- {r}" for r in results)
        speech = f"Closed the apps from your {name} routine."

        if has_other:
            text += "\nWebsites stay open. Please close those tabs yourself."
            speech += " Websites stay open."

        return Reply(text, speech=speech)

    def delete(self, query):
        name, problem = self._find(query)
        if problem:
            return problem

        del self.routines[name]
        error = self._save()
        self._touch(sticky=False)

        extra = f" (I couldn't save the file: {error})" if error else ""
        return Reply(f"Deleted the {name} routine.{extra}", speech=f"Deleted the {name} routine.")

    def show_all(self):
        self._touch(sticky=True)

        if not self.routines:
            return Reply("You don't have any routines yet. Say create routine to make one.")

        lines = ["Your routines:"]
        for name, steps in self.routines.items():
            lines.append(f"- {name}: " + ", ".join(steps))

        return Reply("\n".join(lines), speech=f"You have {len(self.routines)} routine{'s' if len(self.routines) != 1 else ''}: {', '.join(self.routines)}.")

    def show_one(self, query):
        name, problem = self._find(query)
        if problem:
            return problem

        self._touch(sticky=True)
        steps = self.routines[name]
        lines = [f"{name} routine:"] + [f"{i}. {s}" for i, s in enumerate(steps, 1)]
        return Reply("\n".join(lines), speech=f"The {name} routine has {len(steps)} step{'s' if len(steps) != 1 else ''}.")

    def close_card(self):
        self.card_open = False
        self.sticky = False
        self.version += 1
        return Reply("Closed the routines.", speech="")

    def auto_hide(self):
        if (self.card_open and self.stage is None and not self.sticky
                and time.time() - self.last_activity > CARD_AUTO_HIDE_SECONDS):
            self.card_open = False
            self.version += 1
            return True
        return False

    # ------------------------------------------------------------------
    # For the routine card in the page
    # ------------------------------------------------------------------

    def snapshot(self):
        self._expire()
        return {
            "visible": self.card_open,
            "stage": self.stage,
            "max_steps": MAX_STEPS,
            "name": self.name,
            "steps": list(self.steps),
            "routines": [{"name": n, "steps": s} for n, s in self.routines.items()][:8],
        }

    def snapshot_json(self):
        return json.dumps(self.snapshot())


# One shared manager used by the whole app
routines = RoutineManager()