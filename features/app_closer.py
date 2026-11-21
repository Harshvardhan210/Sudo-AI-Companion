"""
Close running applications by voice or text: "sudo close notepad".

- Normal close asks the app to close politely, so apps like Notepad can still
  ask "Do you want to save?" and nothing is lost.
- "force close" ends the app immediately (unsaved work is lost).
- The assistant never closes itself, the programs it is running inside,
  or important Windows system programs.

Needs the psutil package:  pip install psutil
"""

import os
import re
import subprocess
import sys
import time

try:
    import psutil
except ImportError:          # handled with a friendly message below
    psutil = None


# Spoken name -> process names (lowercase). Add your own apps here.
APP_ALIASES = {
    "notepad": ["notepad.exe"],
    "notepad++": ["notepad++.exe"],
    "calculator": ["calculatorapp.exe", "calculator.exe", "win32calc.exe", "calc.exe"],
    "calc": ["calculatorapp.exe", "calculator.exe", "win32calc.exe", "calc.exe"],
    "chrome": ["chrome.exe"],
    "google chrome": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "microsoft edge": ["msedge.exe"],
    "firefox": ["firefox.exe"],
    "brave": ["brave.exe"],
    "vs code": ["code.exe"],
    "vscode": ["code.exe"],
    "visual studio code": ["code.exe"],
    "code": ["code.exe"],
    "pycharm": ["pycharm64.exe", "pycharm.exe"],
    "intellij": ["idea64.exe"],
    "android studio": ["studio64.exe"],
    "postman": ["postman.exe"],
    "sublime": ["sublime_text.exe"],
    "word": ["winword.exe"],
    "ms word": ["winword.exe"],
    "microsoft word": ["winword.exe"],
    "excel": ["excel.exe"],
    "ms excel": ["excel.exe"],
    "powerpoint": ["powerpnt.exe"],
    "ppt": ["powerpnt.exe"],
    "outlook": ["outlook.exe", "olk.exe"],
    "onenote": ["onenote.exe"],
    "paint": ["mspaint.exe"],
    "snipping tool": ["snippingtool.exe", "screenclippinghost.exe"],
    "task manager": ["taskmgr.exe"],
    "settings": ["systemsettings.exe"],
    "media player": ["wmplayer.exe"],
    "vlc": ["vlc.exe"],
    "spotify": ["spotify.exe"],
    "discord": ["discord.exe"],
    "whatsapp": ["whatsapp.exe", "whatsapp.root.exe"],
    "telegram": ["telegram.exe"],
    "teams": ["teams.exe", "ms-teams.exe"],
    "microsoft teams": ["teams.exe", "ms-teams.exe"],
    "zoom": ["zoom.exe"],
    "slack": ["slack.exe"],
    "steam": ["steam.exe"],
    "obs": ["obs64.exe", "obs32.exe"],
}

# Never closed (system programs and the terminals/Python that may be running us)
PROTECTED = {
    "explorer", "winlogon", "csrss", "wininit", "services", "lsass", "svchost",
    "system", "smss", "dwm", "fontdrvhost", "sihost", "ctfmon", "taskhostw",
    "python", "pythonw", "py", "python3",
}

# Simple/modern apps with no "save your work" prompt: if a polite close does
# not work (they often ignore it), they are closed directly.
FORCE_IF_IGNORED = {
    "calculatorapp", "calculator", "win32calc", "calc", "systemsettings",
    "snippingtool", "screenclippinghost",
}

_CLOSE_RE = re.compile(
    r"^(?:please\s+)?(force\s+close|force\s+quit|force\s+exit|close|quit|exit|kill|terminate)\s+(.+)$"
)
_FILLER_WORDS = {
    "the", "app", "application", "program", "window", "windows", "please",
    "all", "my", "for", "me", "now", "software",
}


# ----------------------------------------------------------------------------
# Understanding the command
# ----------------------------------------------------------------------------

def parse_close_command(command):
    """
    "force close notepad" -> ("notepad", True)
    "close the chrome app" -> ("chrome", False)
    Returns None if the command is not a close command.
    """

    match = _CLOSE_RE.match(command.strip().lower())
    if not match:
        return None

    verb, target = match.groups()
    force = verb.startswith("force") or verb in ("kill", "terminate")

    words = [w for w in re.sub(r"[^\w\s+]", " ", target).split() if w not in _FILLER_WORDS]
    target = " ".join(words).strip()

    if not target:
        return None

    return target, force


def _compact(text):
    return re.sub(r"[^a-z0-9+]", "", text.lower())


_ALIASES_COMPACT = {_compact(name): exes for name, exes in APP_ALIASES.items()}


def _stem(process_name):
    return os.path.splitext(process_name.lower())[0]


# ----------------------------------------------------------------------------
# Finding the running processes
# ----------------------------------------------------------------------------

def _running_processes():
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = proc.info["name"]
            if name:
                yield proc, name.lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def _find_matches(target):
    """Return (list of matching processes, list of distinct app names matched)."""

    key = _compact(target)
    exe_names = _ALIASES_COMPACT.get(key)

    matches = []
    stems = set()

    for proc, name in _running_processes():
        if exe_names is not None:
            if name in exe_names:
                matches.append(proc)
                stems.add(_stem(name))
        else:
            stem = _compact(_stem(name))
            if stem == key or (len(key) >= 3 and stem.startswith(key)):
                matches.append(proc)
                stems.add(_stem(name))

    return matches, sorted(stems)


# ----------------------------------------------------------------------------
# Closing
# ----------------------------------------------------------------------------

def _request_close(pid, force):
    try:
        if sys.platform == "win32":
            command = ["taskkill", "/PID", str(pid)]
            if force:
                command.append("/F")

            subprocess.run(
                command,
                capture_output=True,
                timeout=8,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            process = psutil.Process(pid)
            process.kill() if force else process.terminate()

    except Exception as error:
        print("Close error:", error)


def _close_and_wait(processes, force):
    for proc in processes:
        _request_close(proc.pid, force)

    _, alive = psutil.wait_procs(processes, timeout=1.0 if force else 2.0)
    return alive


def close_application(target, force=False):
    """Close an application by its spoken name and return a message to say."""

    if psutil is None:
        return "Closing apps needs psutil. Please run: pip install psutil"

    display = target.strip().title()

    matches, stems = _find_matches(target)

    if not matches:
        return f"{display} doesn't seem to be open."

    if len(stems) > 1:
        return (
            f"That matches more than one app: {', '.join(stems)}. "
            "Please say the full name."
        )

    # Safety: never close system programs...
    if any(stem in PROTECTED for stem in stems):
        return f"I can't close {display}, it is a protected program."

    # ...or the program this assistant is running inside.
    own = {os.getpid()}
    try:
        own.update(parent.pid for parent in psutil.Process().parents())
    except psutil.Error:
        pass

    if any(proc.pid in own for proc in matches):
        return f"I'm running inside {display}, so I can't close it."

    alive = _close_and_wait(matches, force)

    if alive and not force and stems[0] in FORCE_IF_IGNORED:
        alive = _close_and_wait(alive, True)

    if not alive:
        return f"Closed {display}."

    if force:
        return f"I couldn't close {display}. It may need administrator rights."

    return (
        f"I asked {display} to close, but it is still open. "
        f"It may be asking to save your work. "
        f"Say force close {target} to close it anyway."
    )