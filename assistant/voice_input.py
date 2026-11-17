import re
import time

import speech_recognition as sr


# ---------------------------------------------------------------------------
# Wake word settings
# ---------------------------------------------------------------------------
# Speech recognition often mishears "sudo", so common variants are accepted.
# Add more here if you notice your accent produces a different spelling.
WAKE_WORDS = {
    "sudo", "sodo", "pseudo", "sudoh", "sudu", "sudoo",
    "suedo", "soodoo", "sudho", "sado",
}
WAKE_PHRASES = {          # when it is heard as two separate words
    "su do", "sue do", "soo do", "sue doo", "soo doo", "sue dough",
}

# After saying only "sudo", the next phrase is accepted as the command
# for this many seconds.
FOLLOW_UP_SECONDS = 6


def extract_wake_command(text):
    """
    Check whether the text starts with the wake word.

    Returns (heard_wake_word, command)
    "sudo open notepad" -> (True, "open notepad")
    "sudo"              -> (True, "")
    "open notepad"      -> (False, "")
    """

    cleaned = re.sub(r"[^\w\s']", " ", text.lower())
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

    first = re.sub(r"[^\w]", "", words[0].lower())

    if first in WAKE_WORDS:
        return True, " ".join(words[1:]).strip()

    if len(words) >= 2:
        two = re.sub(r"[^\w\s]", "", " ".join(words[:2]).lower())
        if two in WAKE_PHRASES:
            return True, " ".join(words[2:]).strip()

    return False, text.strip()


def clean_command(text):
    """Lowercase and remove punctuation so the command handler can match it."""

    cleaned = re.sub(r"[^\w\s']", " ", text.lower())
    return " ".join(cleaned.split())


def listen_continuously(should_stop, is_paused, is_expecting_answer=None):
    """
    Keep the microphone open and yield a command every time the user says
    one that starts with the wake word ("sudo ...").

    should_stop() -> True when listening must end (Stop button)
    is_paused()   -> True while the assistant is busy or speaking, so it
                     does not hear its own voice
    is_expecting_answer() -> True while the assistant has asked a question
                     (like a reminder name). The next phrase is then taken
                     as the answer, without needing the wake word.
    """

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8

    follow_up_until = 0.0

    # OSError (no microphone) is raised to the caller on purpose.
    with sr.Microphone() as source:

        print("\nAssistant: Calibrating microphone...")
        recognizer.adjust_for_ambient_noise(source, duration=1)

        print('Assistant: Listening continuously. Say "sudo <command>".')

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

            try:
                text = recognizer.recognize_google(
                    audio,
                    language="en-IN"
                )

            except sr.UnknownValueError:
                continue

            except sr.RequestError as error:
                print("Assistant: Speech recognition service unavailable.")
                print("Error:", error)
                time.sleep(1)
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

            # Anything else is ignored (no wake word).


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