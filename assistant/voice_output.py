"""
Text-to-speech for the assistant.

Two voices are available:

  1. "edge"    - natural, human-like neural voices (Microsoft Edge voices).
                 Free, needs internet and:  pip install edge-tts
  2. offline   - the Windows voice through pyttsx3 (the robotic one).
                 Used automatically if the neural voice is not available.

Change the voice by speaking/typing:
    change voice / male voice / female voice / speak faster / speak slower
The choice is saved in voice_settings.json and kept after a restart.
"""

import asyncio
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

try:
    import edge_tts
except ImportError:
    edge_tts = None


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# Voices the "change voice" command cycles through: (voice id, name, gender)
VOICES = [
    ("en-IN-NeerjaNeural", "Neerja, Indian English", "female"),
    ("en-IN-PrabhatNeural", "Prabhat, Indian English", "male"),
    ("en-US-AriaNeural", "Aria, American English", "female"),
    ("en-US-GuyNeural", "Guy, American English", "male"),
    ("en-GB-SoniaNeural", "Sonia, British English", "female"),
    ("en-GB-RyanNeural", "Ryan, British English", "male"),
]

# Text written in Devanagari is spoken with a Hindi voice (the English voices skip it)
HINDI_VOICES = {"female": "hi-IN-SwaraNeural", "male": "hi-IN-MadhurNeural"}

SETTINGS_FILE = Path(__file__).with_name("voice_settings.json")
CACHE_DIR = Path(tempfile.gettempdir()) / "sudo_assistant_tts"

DEFAULT_SETTINGS = {
    "voice": VOICES[0][0],   # default voice
    "rate": 0,               # speaking speed in percent (-40 .. +40)
    "pitch": 0,              # voice pitch in Hz (-20 .. +20)
    "offline_rate": 165,     # speed of the offline voice (words per minute)
    "volume": 1.0,           # 0.0 .. 1.0
}

# The neural voice is played with the Windows media player (MCI).
_NEURAL_PLAYBACK_SUPPORTED = sys.platform == "win32"


def _load_settings():
    settings = dict(DEFAULT_SETTINGS)

    try:
        saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        settings.update({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
    except (OSError, ValueError):
        pass

    return settings


def _save_settings():
    try:
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError as error:
        print("Could not save voice settings:", error)


settings = _load_settings()


# ---------------------------------------------------------------------------
# Neural (human-like) voice
# ---------------------------------------------------------------------------

def _clean_old_cache(max_age_days=3):
    try:
        limit = time.time() - max_age_days * 86400
        for file in CACHE_DIR.glob("*.mp3"):
            if file.stat().st_mtime < limit:
                file.unlink()
    except OSError:
        pass


def _voice_for(text):
    """The voice to use for this text: Hindi voice for Devanagari, otherwise your choice."""

    letters = [c for c in text if c.isalpha()]
    devanagari = sum(1 for c in letters if "\u0900" <= c <= "\u097F")

    if letters and devanagari / len(letters) > 0.3:
        gender = next((v[2] for v in VOICES if v[0] == settings["voice"]), "female")
        return HINDI_VOICES.get(gender, HINDI_VOICES["female"])

    return settings["voice"]


def _audio_path(text):
    key = f"{_voice_for(text)}|{settings['rate']}|{settings['pitch']}|{text}"
    name = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{name}.mp3"


async def _generate(text, path):
    communicate = edge_tts.Communicate(
        text,
        _voice_for(text),
        rate=f"{int(settings['rate']):+d}%",
        pitch=f"{int(settings['pitch']):+d}Hz",
    )
    await asyncio.wait_for(communicate.save(str(path)), timeout=10)


def _neural_audio(text):
    """Return an mp3 file for the text (the same sentence is only generated once)."""

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _audio_path(text)

    if path.exists() and path.stat().st_size > 0:
        return path

    partial = path.with_suffix(".part")

    try:
        asyncio.run(_generate(text, partial))
        os.replace(partial, path)
    finally:
        if partial.exists():
            try:
                partial.unlink()
            except OSError:
                pass

    return path


def _play_mp3(path):
    """Play an mp3 and wait until it finishes (Windows)."""

    import ctypes

    mci = ctypes.windll.winmm.mciSendStringW
    alias = "sudo_tts"

    mci(f"close {alias}", None, 0, 0)

    error = mci(f'open "{path}" type mpegvideo alias {alias}', None, 0, 0)
    if error:
        raise RuntimeError(f"Could not open audio (MCI error {error})")

    try:
        mci(f"setaudio {alias} volume to {int(settings['volume'] * 1000)}", None, 0, 0)
        mci(f"play {alias} wait", None, 0, 0)
    finally:
        mci(f"close {alias}", None, 0, 0)


# ---------------------------------------------------------------------------
# Offline (robotic) voice - backup
# ---------------------------------------------------------------------------

_offline_engine = None
_PREFERRED_OFFLINE_VOICES = ("heera", "zira", "hazel", "sonia", "susan")


def _get_offline_engine():
    global _offline_engine

    if _offline_engine is None:
        import pyttsx3

        engine = pyttsx3.init()
        voices = engine.getProperty("voices")

        if voices:
            chosen = voices[0]
            for wanted in _PREFERRED_OFFLINE_VOICES:
                match = next((v for v in voices if wanted in v.name.lower()), None)
                if match:
                    chosen = match
                    break
            engine.setProperty("voice", chosen.id)

        _offline_engine = engine

    engine = _offline_engine
    engine.setProperty("rate", settings["offline_rate"])
    engine.setProperty("volume", settings["volume"])
    return engine


def _speak_offline(text):
    try:
        engine = _get_offline_engine()
        engine.say(text)
        engine.runAndWait()
    except Exception as error:
        print("Voice output error:", error)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

_warned_missing = False


def speak(text):
    """Convert text into spoken audio."""

    global _warned_missing

    if not text:
        return

    text = " ".join(str(text).split())[:600]

    if edge_tts is None and not _warned_missing:
        _warned_missing = True
        print("Tip: install the natural voice with:  pip install edge-tts")

    if edge_tts is not None and _NEURAL_PLAYBACK_SUPPORTED:
        try:
            _play_mp3(_neural_audio(text))
            return
        except Exception as error:
            # No internet, service problem, ... -> use the offline voice.
            print("Natural voice failed, using offline voice:", error)

    _speak_offline(text)


def set_voice_speed(speed):
    """Change the speed of the offline voice (words per minute)."""

    settings["offline_rate"] = int(speed)
    _save_settings()


def set_volume(volume):
    """Change speaking volume (0.0 to 1.0)."""

    settings["volume"] = max(0.0, min(1.0, float(volume)))
    _save_settings()


# --- voice commands ---------------------------------------------------------

def _voice_index():
    for index, (voice_id, _, _) in enumerate(VOICES):
        if voice_id == settings["voice"]:
            return index
    return 0


def _use_voice(index):
    voice_id, name, _ = VOICES[index]
    settings["voice"] = voice_id
    _save_settings()
    return name


def current_voice_name():
    return VOICES[_voice_index()][1]


def next_voice():
    name = _use_voice((_voice_index() + 1) % len(VOICES))
    return f"Okay, I'm now using the {name} voice. How does this sound?"


def set_voice_gender(gender):
    current = _voice_index()

    if VOICES[current][2] == gender:
        # Already that gender: move to the next voice of that gender.
        options = [i for i, v in enumerate(VOICES) if v[2] == gender]
        index = options[(options.index(current) + 1) % len(options)]
    else:
        index = next(i for i, v in enumerate(VOICES) if v[2] == gender)

    name = _use_voice(index)
    return f"Okay, I'm now using the {name} voice. How does this sound?"


def change_speed(step):
    """step is in percent: +10 faster, -10 slower."""

    new_rate = max(-40, min(40, int(settings["rate"]) + step))

    if new_rate == settings["rate"]:
        return "I can't go any " + ("faster." if step > 0 else "slower.")

    settings["rate"] = new_rate
    settings["offline_rate"] = max(100, min(260, settings["offline_rate"] + step * 2))
    _save_settings()

    return "Okay, I'll speak faster." if step > 0 else "Okay, I'll speak slower."


_clean_old_cache()