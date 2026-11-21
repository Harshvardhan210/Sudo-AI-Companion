"""
Chooses which microphone the assistant listens with, so it can use your
earphones / headphones / headset when you wear them.

  auto      (default) headset microphone if one is connected, otherwise the
            normal microphone of the laptop
  headset   same as auto, and the robot tells you if no headset is found
  laptop    always the laptop microphone, even if a headset is connected

Say:  "use headphones" / "use laptop mic" / "use automatic audio" / "which mic are you using"

The robot's voice always plays through the Windows default sound output.
Windows switches that to your earphones when you connect them.

If your headset is not recognised by name, put a word from its name into
audio_settings.json ("input_keyword"), for example "hyperx".
"""

import json
from pathlib import Path


SETTINGS_FILE = Path(__file__).with_name("audio_settings.json")

# A microphone whose name contains one of these words counts as a headset
HEADSET_WORDS = (
    "headset", "headphone", "earphone", "earbud", "buds", "airpods", "hands-free",
    "hands free", "handsfree", "bluetooth", "jabra", "wh-", "wf-",
)

# ...unless it also contains one of these (virtual or built-in devices)
NOT_A_HEADSET_WORDS = (
    "stereo mix", "what u hear", "loopback", "virtual", "cable", "line in",
    "line-in", "array", "internal", "built-in", "built in",
)

DEFAULT_SETTINGS = {"mode": "auto", "input_keyword": ""}

MODES = ("auto", "headset", "laptop")


def _load_settings():
    settings = dict(DEFAULT_SETTINGS)

    try:
        saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        settings.update({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
    except (OSError, ValueError):
        pass

    if settings["mode"] not in MODES:
        settings["mode"] = "auto"

    return settings


settings = _load_settings()

# Increases when the mode changes, so the app knows to reopen the microphone
version = 0

# What the microphone loop is using right now (set by the listening thread)
current_input = {"name": "not listening yet", "kind": "none"}


def _save_settings():
    try:
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError as error:
        print("Could not save audio settings:", error)


# ---------------------------------------------------------------------------
# Finding microphones
# ---------------------------------------------------------------------------

def is_headset(name):
    """Does this microphone name look like earphones / headphones / a headset?"""

    lowered = name.lower()

    keyword = str(settings.get("input_keyword", "")).strip().lower()
    if keyword and keyword in lowered:
        return True

    if any(word in lowered for word in NOT_A_HEADSET_WORDS):
        return False

    return any(word in lowered for word in HEADSET_WORDS)


def _scan_inputs():
    """List the microphones: [{"index", "name", "default"}]. Needs PyAudio."""

    import pyaudio

    audio = pyaudio.PyAudio()

    try:
        try:
            host = audio.get_default_host_api_info()["index"]
        except Exception:
            host = None

        try:
            default_index = audio.get_default_input_device_info()["index"]
        except Exception:
            default_index = None

        devices = []

        for index in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(index)

            if info.get("maxInputChannels", 0) <= 0:
                continue

            if host is not None and info.get("hostApi") != host:
                continue

            devices.append({
                "index": index,
                "name": str(info.get("name", "")),
                "default": index == default_index,
            })

        return devices

    finally:
        audio.terminate()


def pick_input(devices=None):
    """
    Choose the microphone to use.
    Returns (device_index, name, kind). device_index None = system default.
    kind is "headset", "laptop" or "default".
    """

    if devices is None:
        try:
            devices = _scan_inputs()
        except Exception as error:
            print("Could not list microphones:", error)
            devices = []

    default = next((d for d in devices if d["default"]), None)
    default_name = default["name"] if default else "default microphone"

    headsets = [d for d in devices if is_headset(d["name"])]

    if settings["mode"] == "laptop":
        built_in = [d for d in devices if not is_headset(d["name"])]

        # Prefer the laptop's own microphone array, then the default if it is not a headset
        chosen = next((d for d in built_in if "array" in d["name"].lower()), None)
        if chosen is None and default and not is_headset(default["name"]):
            chosen = default
        if chosen is None and built_in:
            chosen = built_in[0]

        if chosen:
            return chosen["index"], chosen["name"], "laptop"

        return None, default_name, "default"

    if headsets:
        # If Windows already uses a headset as the default, keep that one
        chosen = next((d for d in headsets if d["default"]), headsets[0])
        return chosen["index"], chosen["name"], "headset"

    return None, default_name, "default"


def set_current_input(name, kind):
    current_input["name"] = name
    current_input["kind"] = kind


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def set_mode(mode):
    """Change the mode ("auto", "headset" or "laptop"). Returns a message."""

    global version

    if mode not in MODES:
        return "I don't know that audio mode."

    settings["mode"] = mode
    _save_settings()
    version += 1

    if mode == "laptop":
        return "Okay, I'll listen with the laptop microphone."

    if mode == "headset":
        return "Okay, I'll listen with your headset microphone when it is connected."

    return "Okay, I'll switch to your earphones automatically when they are connected."


def default_output_name():
    """Name of the sound output the robot's voice uses (the Windows default)."""

    try:
        from PySide6.QtMultimedia import QMediaDevices

        device = QMediaDevices.defaultAudioOutput()
        name = device.description()
        return name or None
    except Exception:
        return None


def status_text():
    """Which microphone and speaker are in use (for "which mic are you using")."""

    kinds = {
        "headset": "your headset",
        "laptop": "the laptop microphone",
        "default": "the default microphone",
    }

    inp = current_input
    if inp["kind"] == "none":
        lines = ["I'm not listening yet. Click the mic button first."]
    else:
        lines = [f"Microphone: {inp['name']} ({kinds.get(inp['kind'], inp['kind'])})."]

    output = default_output_name()
    if output:
        lines.append(f"Voice output: {output}.")
    else:
        lines.append("Voice output: the Windows default sound output.")

    lines.append(f"Audio mode: {settings['mode']}.")
    return "\n".join(lines)