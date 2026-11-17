"""
To-do list for the assistant. Tasks are saved automatically in todo/todo.txt.

    "sudo add task buy milk"          -> adds a task
    "sudo add a task"                 -> the robot asks "What's the task?"
    "sudo show my tasks"              -> opens the to-do card (and says how many are left)
    "sudo read my tasks"              -> reads the tasks that are not done
    "sudo mark task 2 as done"        -> ticks it (also: "complete task 2", "complete buy milk")
    "sudo undo task 2"                -> un-ticks it
    "sudo delete task 3"              -> deletes it (also: "delete buy milk from my to do list")
    "sudo clear completed tasks"      -> removes all ticked tasks
    "sudo clear all tasks"            -> asks you to say "confirm clear tasks"
    "sudo close tasks"                -> closes the card
"""

import json
import re
import time
from pathlib import Path

from features.notes import Reply


MAX_TASKS = 30
MAX_TASK_LENGTH = 200

# Seconds the robot waits for the task after "add a task"
PENDING_SECONDS = 20

# The card closes by itself after this long, unless you opened it with "show my tasks"
CARD_AUTO_HIDE_SECONDS = 8

# <project>/todo/todo.txt   (this file lives in <project>/features/)
TODO_FILE = Path(__file__).resolve().parent.parent / "todo" / "todo.txt"

_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

_NUM = r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
_LIST = r"(?:to[\s-]?do(?:s)?(?:\s+list)?|tasks?(?:\s+list)?)"
_ITEM = r"(?:task|to[\s-]?do|todo)"
_FLAGS = re.I

_ADD_BARE = re.compile(rf"^(?:add|create|new|make)\s+(?:a\s+|an\s+|the\s+)?(?:new\s+)?{_ITEM}$", _FLAGS)
_ADD_INLINE = re.compile(
    rf"^(?:add|create|new|make|put)\s+(?:a\s+|an\s+|the\s+)?(?:new\s+)?{_ITEM}"
    rf"(?:\s+(?:to|that|called|named|saying|for))?[:,]?\s+(.+)$", _FLAGS)
_ADD_TO_LIST = re.compile(rf"^(?:add|put)\s+(.+?)\s+(?:to|on|in)\s+(?:my\s+|the\s+)?{_LIST}$", _FLAGS)
_ADD_TODO_PREFIX = re.compile(r"^todo[:,]?\s+(.+)$", _FLAGS)

_SHOW = [
    re.compile(rf"^(?:open|show|view|display|see|list)\s+(?:me\s+)?(?:(?:my|the|all)\s+)*{_LIST}$", _FLAGS),
    re.compile(r"^what(?:'s|s| is| are)\s+(?:on\s+)?(?:my\s+)?(?:to[\s-]?do|tasks?)(?:\s+list)?(?:\s+today)?$", _FLAGS),
    re.compile(r"^what\s+do\s+i\s+(?:need|have)\s+to\s+do(?:\s+today)?$", _FLAGS),
]
_READ = re.compile(rf"^read\s+(?:(?:my|the|out)\s+)*{_LIST}$", _FLAGS)
_CLOSE = re.compile(rf"^(?:close|hide|dismiss)\s+(?:(?:my|the)\s+)*{_LIST}$", _FLAGS)

_COMPLETE_NUM = [
    re.compile(rf"^(?:mark|set)\s+(?:(?:task|todo|to do|number|no)\s+)?{_NUM}\s+(?:as\s+)?(?:done|complete|completed|finished)$", _FLAGS),
    re.compile(rf"^(?:complete|finish|tick|check off|cross off|done)\s+(?:(?:task|todo|number|no)\s+)?{_NUM}$", _FLAGS),
]
_REOPEN_NUM = [
    re.compile(rf"^(?:mark|set)\s+(?:(?:task|todo|number)\s+)?{_NUM}\s+(?:as\s+)?(?:not\s+done|incomplete|pending|undone|not\s+complete)$", _FLAGS),
    re.compile(rf"^(?:undo|reopen|uncheck|untick|restore)\s+(?:(?:task|todo|number)\s+)?{_NUM}$", _FLAGS),
]
_COMPLETE_NAME = [
    re.compile(r"^(?:mark|set)\s+(?:task\s+)?(.+?)\s+(?:as\s+)?(?:done|complete|completed|finished)$", _FLAGS),
    re.compile(r"^(?:complete|finish|tick off|cross off|check off)\s+(?:the\s+)?(?:task\s+)?(.+)$", _FLAGS),
]
_DELETE_NUM = re.compile(rf"^(?:delete|remove|erase)\s+(?:task|to[\s-]?do|todo|number)\s+{_NUM}$", _FLAGS)
_DELETE_LAST = re.compile(rf"^(?:delete|remove|erase)\s+(?:the\s+)?last\s+{_ITEM}$", _FLAGS)
_DELETE_NAME = [
    re.compile(rf"^(?:delete|remove|erase)\s+(?:the\s+)?{_ITEM}\s+(.+)$", _FLAGS),
    re.compile(rf"^(?:delete|remove)\s+(.+?)\s+(?:from|off)\s+(?:my\s+|the\s+)?{_LIST}$", _FLAGS),
]
_CLEAR_DONE = [
    re.compile(r"^(?:clear|delete|remove)\s+(?:all\s+)?(?:the\s+)?(?:completed|done|finished)\s+(?:tasks?|todos?|items?)$", _FLAGS),
    re.compile(r"^clear\s+(?:completed|done|finished)$", _FLAGS),
]
_CLEAR_ALL = re.compile(rf"^(?:clear|delete|remove|empty)\s+(?:all\s+)?(?:(?:my|the)\s+)*{_LIST}$", _FLAGS)
_CONFIRM_CLEAR = re.compile(rf"^confirm\s+clear(?:\s+all)?(?:\s+{_LIST})?$", _FLAGS)

_CANCEL_WORDS = {"cancel", "never mind", "nevermind", "forget it", "stop"}


def _norm(text):
    text = re.sub(r"[^\w\s']", " ", text.lower())
    return " ".join(text.split())


def _number(token):
    token = token.lower()
    return int(token) if token.isdigit() else _NUMBER_WORDS[token]


class TodoManager:

    def __init__(self, todo_file=TODO_FILE):
        self.todo_file = Path(todo_file)
        self.tasks = self._load()       # [{"text": str, "done": bool}]
        self.pending_until = 0.0        # waiting for the text of a new task
        self.confirm_clear_until = 0.0  # waiting for "confirm clear tasks"
        self.card_open = False
        self.sticky = False             # opened with "show my tasks" (stays open)
        self.last_activity = 0.0
        self.version = 0

    # ------------------------------------------------------------------
    # File
    # ------------------------------------------------------------------

    def _load(self):
        tasks = []

        try:
            lines = self.todo_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            return tasks

        for line in lines:
            match = re.match(r"^\[( |x|X)\]\s+(.*)$", line.strip())
            if match and match.group(2).strip():
                tasks.append({"text": match.group(2).strip(), "done": match.group(1).lower() == "x"})

        return tasks

    def _save(self):
        """Write the list to the file. Returns an error text, or None."""

        lines = ["# To-do list  ([ ] = to do, [x] = done)"]
        lines += [f"[{'x' if t['done'] else ' '}] {t['text']}" for t in self.tasks]

        try:
            self.todo_file.parent.mkdir(parents=True, exist_ok=True)
            self.todo_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as error:
            return str(error)

        return None

    def _changed(self, sticky=False):
        """Save, show the card and tell the page."""

        error = self._save()
        self.card_open = True
        self.sticky = self.sticky or sticky
        self.last_activity = time.time()
        self.version += 1
        return error

    # ------------------------------------------------------------------
    # Pending questions
    # ------------------------------------------------------------------

    def has_pending(self):
        return time.time() < self.pending_until

    def handle_pending(self, answer):
        """The reply to "What's the task?"."""

        self.pending_until = 0.0

        if _norm(answer) in _CANCEL_WORDS:
            return Reply("Okay, I cancelled that.")

        return self.add_task(answer)

    # ------------------------------------------------------------------
    # Entry point (called by command_handler.py)
    # ------------------------------------------------------------------

    def handle(self, original, heard_wake, rest):
        text = rest.strip().rstrip(".?!,").strip()

        if not text:
            return None

        # ----- add -----
        if _ADD_BARE.match(text):
            self.pending_until = time.time() + PENDING_SECONDS
            return Reply("What's the task?")

        # ----- show / read / close (checked before "todo <text>") -----
        if any(p.match(text) for p in _SHOW):
            return self.show()

        if _READ.match(text):
            return self.read()

        if _CLOSE.match(text):
            return self.close_card()

        # ----- add with text -----
        for pattern in (_ADD_INLINE, _ADD_TO_LIST, _ADD_TODO_PREFIX):
            match = pattern.match(text)
            if match:
                return self.add_task(match.group(1))

        # ----- complete / reopen / delete by number -----
        for pattern in _COMPLETE_NUM:
            match = pattern.match(text)
            if match:
                return self.set_done(_number(match.group(1)), True)

        for pattern in _REOPEN_NUM:
            match = pattern.match(text)
            if match:
                return self.set_done(_number(match.group(1)), False)

        match = _DELETE_NUM.match(text)
        if match:
            return self.delete(_number(match.group(1)))

        if _DELETE_LAST.match(text):
            return self.delete(len(self.tasks))

        # ----- clear -----
        if any(p.match(text) for p in _CLEAR_DONE):
            return self.clear_done()

        if _CONFIRM_CLEAR.match(text):
            return self.confirm_clear()

        if _CLEAR_ALL.match(text):
            return self.ask_clear_all()

        # ----- by task name -----
        for pattern in _DELETE_NAME:
            match = pattern.match(text)
            if match:
                index, problem = self._find(match.group(1))
                return problem or self.delete(index)

        for pattern in _COMPLETE_NAME:
            match = pattern.match(text)
            if match:
                index, problem = self._find(match.group(1))
                return problem or self.set_done(index, True)

        return None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _left(self):
        left = sum(1 for t in self.tasks if not t["done"])
        return left, len(self.tasks)

    def _left_phrase(self):
        left, total = self._left()
        if total == 0:
            return "Your list is empty."
        if left == 0:
            return "Everything is done."
        return f"{left} left to do."

    def _problem(self, error):
        return f" (I couldn't save the file: {error})" if error else ""

    def add_task(self, text):
        text = " ".join(str(text).split()).strip(" .,")[:MAX_TASK_LENGTH]

        if not text:
            return Reply("I didn't catch the task. Try again.")

        if len(self.tasks) >= MAX_TASKS:
            return Reply(f"Your to-do list is full ({MAX_TASKS} tasks). Delete or clear some first.")

        text = text[0].upper() + text[1:]
        self.tasks.append({"text": text, "done": False})
        error = self._changed()

        number = len(self.tasks)
        return Reply(f"Added task {number}: {text}{self._problem(error)}",
                     speech=f"Added task {number}: {text}.")

    def _find(self, query):
        """Find a task by (part of) its name. Returns (number, None) or (None, Reply)."""

        query = _norm(query)
        words = query.split()

        if not self.tasks:
            return None, Reply("Your to-do list is empty.")

        exact = [i for i, t in enumerate(self.tasks, 1) if _norm(t["text"]) == query]
        if len(exact) == 1:
            return exact[0], None

        matches = [
            i for i, t in enumerate(self.tasks, 1)
            if query in _norm(t["text"]) or all(w in _norm(t["text"]).split() for w in words)
        ]

        if len(matches) == 1:
            return matches[0], None

        if not matches:
            return None, Reply("I couldn't find a task like that.")

        numbers = ", ".join(str(i) for i in matches)
        return None, Reply(f"That matches tasks {numbers}. Please say the task number.")

    def _check_number(self, number):
        if 1 <= number <= len(self.tasks):
            return None

        if not self.tasks:
            return Reply("Your to-do list is empty.")

        return Reply(f"There is no task {number}. You have {len(self.tasks)} task{'s' if len(self.tasks) != 1 else ''}.")

    def set_done(self, number, done):
        problem = self._check_number(number)
        if problem:
            return problem

        task = self.tasks[number - 1]

        if task["done"] == done:
            state = "done" if done else "not done"
            return Reply(f"Task {number} is already {state}.")

        task["done"] = done
        error = self._changed()

        if done:
            return Reply(f"Marked task {number} as done: {task['text']}{self._problem(error)}",
                         speech=f"Done. Task {number} is complete. {self._left_phrase()}")

        return Reply(f"Task {number} is back on the list: {task['text']}{self._problem(error)}",
                     speech=f"Okay, task {number} is back on your list.")

    def toggle(self, number):
        """Clicking a task on the card."""

        if 1 <= number <= len(self.tasks):
            task = self.tasks[number - 1]
            task["done"] = not task["done"]
            self._changed()

    def delete(self, number):
        problem = self._check_number(number)
        if problem:
            return problem

        removed = self.tasks.pop(number - 1)
        error = self._changed()

        return Reply(f"Deleted task {number}: {removed['text']}{self._problem(error)}",
                     speech=f"Deleted task {number}.")

    def clear_done(self):
        done = [t for t in self.tasks if t["done"]]

        if not done:
            return Reply("There are no completed tasks to clear.")

        self.tasks = [t for t in self.tasks if not t["done"]]
        error = self._changed()

        word = "task" if len(done) == 1 else "tasks"
        return Reply(f"Cleared {len(done)} completed {word}.{self._problem(error)}",
                     speech=f"Cleared {len(done)} completed {word}.")

    def ask_clear_all(self):
        if not self.tasks:
            return Reply("Your to-do list is already empty.")

        self.confirm_clear_until = time.time() + 30
        message = f"This will delete all {len(self.tasks)} tasks. Say confirm clear tasks to continue."
        return Reply(message)

    def confirm_clear(self):
        if time.time() >= self.confirm_clear_until or not self.tasks:
            return Reply("There's nothing to confirm.")

        count = len(self.tasks)
        self.tasks = []
        self.confirm_clear_until = 0.0
        error = self._changed()

        return Reply(f"Cleared all {count} tasks.{self._problem(error)}", speech=f"Cleared all {count} tasks.")

    def _format_text(self):
        left, total = self._left()
        lines = [f"To-do list ({total - left} of {total} done):"]
        lines += [f"{i}. [{'x' if t['done'] else ' '}] {t['text']}" for i, t in enumerate(self.tasks, 1)]
        return "\n".join(lines)

    def show(self):
        self._changed(sticky=True)

        if not self.tasks:
            return Reply("Your to-do list is empty. Say add task, followed by the task.")

        left, total = self._left()
        word = "task" if total == 1 else "tasks"
        return Reply(self._format_text(), speech=f"You have {total} {word}. {self._left_phrase()}")

    def read(self):
        pending = [(i, t["text"]) for i, t in enumerate(self.tasks, 1) if not t["done"]]

        if not self.tasks:
            return Reply("Your to-do list is empty.")

        if not pending:
            return Reply("Everything on your list is done.")

        self._changed(sticky=True)

        speech = f"You have {len(pending)} left. " + " ".join(f"Task {i}: {t}." for i, t in pending)
        return Reply("\n".join(f"{i}. {t}" for i, t in pending), speech=speech)

    def close_card(self):
        self.card_open = False
        self.sticky = False
        self.version += 1
        return Reply("Closed the to-do list.", speech="")

    def auto_hide(self):
        """Hide the card a few seconds after a change (not if you opened it)."""

        if (self.card_open and not self.sticky
                and time.time() - self.last_activity > CARD_AUTO_HIDE_SECONDS):
            self.card_open = False
            self.version += 1
            return True

        return False

    # ------------------------------------------------------------------
    # For the to-do card in the page
    # ------------------------------------------------------------------

    def snapshot(self):
        left, total = self._left()

        return {
            "visible": self.card_open,
            "tasks": [dict(t) for t in self.tasks],
            "done": total - left,
            "total": total,
        }

    def snapshot_json(self):
        return json.dumps(self.snapshot())


# One shared manager used by the whole app
todos = TodoManager()