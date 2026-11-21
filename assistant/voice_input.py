import re
import time

import speech_recognition as sr

from assistant import wake_mode


# ---------------------------------------------------------------------------
# Wake word settings
# ---------------------------------------------------------------------------
# Speech recognition often mishears "sudo", so common variants are accepted.
# Add more here if you notice your accent produces a different spelling.
WAKE_WORDS = {
    "sudo", "sodo", "pseudo", "sudoh", "sudu", "sudoo",
    "suedo", "soodoo", "sudho", "sado",
    "सूडो", "सुडो", "सुदो", "सूदो", "सुडू", "सूडू",     # said in Hindi
}
WAKE_PHRASES = {          # when it is heard as two separate words
    "su do", "sue do", "soo do", "sue doo", "soo doo", "sue dough",
}

# After saying only "sudo", the next phrase is accepted as the command
# for this many seconds.
FOLLOW_UP_SECONDS = 6

# Speech languages: English (India) first, then Hindi if the first result is not a command
LANGUAGES = ("en-IN", "hi-IN")

# Only try the second language for sounds at least this long (seconds)
SECOND_PASS_MIN_SECONDS = 0.6

# Punctuation to remove. Devanagari letters and vowel signs are kept.
_PUNCTUATION = re.compile(r"[^\w\s'\u0900-\u097F]|[\u0964\u0965]")


def extract_wake_command(text):
    """
    Check whether the text starts with the wake word.

    Returns (heard_wake_word, command)
    "sudo open notepad" -> (True, "open notepad")
    "sudo"              -> (True, "")
    "open notepad"      -> (False, "")
    """

    cleaned = _PUNCTUATION.sub(" ", text.lower())
    words = cleaned.split()

    if not words:
        return False, ""

    if words[0] in WAKE_WORDS:
        return True, " ".join(words[1:]).strip()

    if len(words) >= 2 and " ".join(words[:2]) in WAKE_PHRASES:
        return True, " ".join(words[2:]).strip()

    return False, ""


def strip_wake_word(text):
    """
    Like extract_wake_command, but keeps the rest of the text exactly as typed
    or spoken (capital letters and punctuation).

    "Sudo, save notes" -> (True, "save notes")
    "buy milk"         -> (False, "buy milk")
    """

    words = text.strip().split()

    if not words:
        return False, ""

    first = _PUNCTUATION.sub("", words[0].lower())

    if first in WAKE_WORDS:
        return True, " ".join(words[1:]).strip()

    if len(words) >= 2:
        two = _PUNCTUATION.sub("", " ".join(words[:2]).lower())
        if two in WAKE_PHRASES:
            return True, " ".join(words[2:]).strip()

    return False, text.strip()


def clean_command(text):
    """Lowercase and remove punctuation so the command handler can match it."""

    cleaned = _PUNCTUATION.sub(" ", text.lower())
    return " ".join(cleaned.split())


def _transcripts(recognizer, audio, language):
    """All guesses Google gives for the audio in one language (best first)."""

    result = recognizer.recognize_google(audio, language=language, show_all=True)

    guesses = []

    if isinstance(result, dict):
        for item in result.get("alternative", []):
            transcript = item.get("transcript")
            if transcript:
                guesses.append(transcript)

    return guesses


def _audio_seconds(audio):
    try:
        return len(audio.frame_data) / (audio.sample_rate * audio.sample_width)
    except Exception:
        return 99.0


def recognize_phrase(recognizer, audio, expecting, follow_up_active):
    """
    Turn the audio into text.

    English is tried first. If nothing in it is a command (and Hindi is on), the
    same audio is tried as Hindi. While the assistant expects an answer (a note
    point, a reminder name) the first guess is used as it is.
    Returns the text, or None if nothing was understood.
    """

    def usable(text):
        heard_wake, _ = strip_wake_word(text)

        if heard_wake or follow_up_active:
            return True

        if wake_mode.wake_required():
            return False

        return wake_mode.looks_like_command(text)

    first = _transcripts(recognizer, audio, LANGUAGES[0])

    if expecting:
        if first:
            return first[0]
    else:
        for guess in first:
            if usable(guess):
                return guess

    hindi = []

    if (wake_mode.hindi_enabled() and len(LANGUAGES) > 1
            and _audio_seconds(audio) >= SECOND_PASS_MIN_SECONDS):
        hindi = _transcripts(recognizer, audio, LANGUAGES[1])

        if expecting:
            return hindi[0] if hindi and not first else (first[0] if first else None)

        for guess in hindi:
            if usable(guess):
                return guess

    # Nothing looked like a command: return the best guess (it will be ignored)
    if first:
        return first[0]

    return hindi[0] if hindi else None


def listen_continuously(
    should_stop,
    is_paused,
    is_expecting_answer=None,
    device_index=None,
    on_fallback=None,
):
    """
    Keep the microphone open and yield a command every time the user says
    one that starts with the wake word ("sudo ...").

    should_stop() -> True when listening must end (Stop button)
    is_paused()   -> True while the assistant is busy or speaking, so it
                     does not hear its own voice
    is_expecting_answer() -> True while the assistant has asked a question
                     (like a reminder name). The next phrase is then taken
                     as the answer, without needing the wake word.
    device_index  -> which microphone to use (None = the system default).
                     If that microphone fails or is unplugged, the default
                     microphone is used instead.
    on_fallback() -> called when it switched to the default microphone
    """

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8

    candidates = [device_index] if device_index is None else [device_index, None]

    for position, index in enumerate(candidates):

        try:
            with sr.Microphone(device_index=index) as source:
                yield from _listen_loop(
                    recognizer, source, should_stop, is_paused, is_expecting_answer
                )
            return

        except OSError as error:
            # No microphone at all (or the last choice failed): tell the caller.
            if position == len(candidates) - 1:
                raise

            print("Assistant: That microphone is not available, using the default one.")
            print("Error:", error)

            if on_fallback:
                on_fallback()

            if should_stop():
                return


def _listen_loop(recognizer, source, should_stop, is_paused, is_expecting_answer):
    """Listen on an open microphone and yield commands."""

    follow_up_until = 0.0

    print("\nAssistant: Calibrating microphone...")
    recognizer.adjust_for_ambient_noise(source, duration=1)

    if wake_mode.wake_required():
        print('Assistant: Listening continuously. Say "sudo <command>".')
    else:
        print('Assistant: Listening continuously. "sudo" is optional (English or Hindi).')

    while not should_stop():

        if is_paused():
            time.sleep(0.1)
            continue

        # A short timeout lets us check the Stop button every second.
        try:
            audio = recognizer.listen(
                source,
                timeout=1,
                phrase_time_limit=8
            )
        except sr.WaitTimeoutError:
            continue

        # Throw away audio captured while stopped or while the
        # assistant was busy/speaking.
        if should_stop():
            break

        if is_paused():
            continue

        expecting = bool(is_expecting_answer and is_expecting_answer())

        try:
            text = recognize_phrase(
                recognizer,
                audio,
                expecting,
                follow_up_active=time.time() < follow_up_until,
            )

        except sr.UnknownValueError:
            continue

        except sr.RequestError as error:
            print("Assistant: Speech recognition service unavailable.")
            print("Error:", error)
            time.sleep(1)
            continue

        if not text:
            continue

        if should_stop():
            break

        print("Heard:", text)

        heard_wake, command = extract_wake_command(text)

        # The assistant asked a question (reminder name) or is taking
        # notes: this phrase is the answer. The wake word is kept in the
        # text, so "sudo save notes" can be told apart from a note point.
        if is_expecting_answer and is_expecting_answer():
            if heard_wake and not command:
                continue            # just "sudo": ignore

            answer = clean_command(text)
            if answer:
                follow_up_until = 0.0
                yield answer
            continue

        if heard_wake and command:
            follow_up_until = 0.0
            yield command

        elif heard_wake:
            # Only "sudo" was said: wait for the command in the next phrase.
            follow_up_until = time.time() + FOLLOW_UP_SECONDS
            print("Assistant: Yes? Say your command.")

        elif time.time() < follow_up_until:
            follow_up_until = 0.0
            command = clean_command(text)

            if command:
                yield command

        # No "sudo", but it clearly is a command (English or Hindi)
        elif not wake_mode.wake_required() and wake_mode.looks_like_command(text):
            command = clean_command(text)

            if command:
                yield command

        # Anything else is ignored (normal conversation).


def listen_for_command():
    """Old single-command listener (kept for compatibility)."""

    recognizer = sr.Recognizer()

    try:
        with sr.Microphone() as source:

            print("\nAssistant: Listening...")

            recognizer.adjust_for_ambient_noise(
                source,
                duration=0.5
            )

            print("Speak your command now...")

            audio = recognizer.listen(
                source,
                timeout=5,
                phrase_time_limit=7
            )

        print("Assistant: Recognizing speech...")

        command = recognizer.recognize_google(
            audio,
            language="en-IN"
        )

        command = command.lower().strip()

        print("You said:", command)

        return command

    except sr.WaitTimeoutError:

        print("Assistant: No speech detected.")
        return None

    except sr.UnknownValueError:

        print("Assistant: Sorry, I couldn't understand you.")
        return None

    except sr.RequestError as error:

        print("Assistant: Speech recognition service unavailable.")
        print("Error:", error)
        return None

    except OSError as error:

        print("Assistant: Microphone error.")
        print("Error:", error)
        return None