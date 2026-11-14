
import pyttsx3


# Initialize speech engine
engine = pyttsx3.init()


# Configure voice settings
engine.setProperty("rate", 175)
engine.setProperty("volume", 1.0)


# Get available voices
voices = engine.getProperty("voices")


# Select default voice
if voices:
    engine.setProperty("voice", voices[0].id)


def speak(text):

    """
    Convert text into spoken audio.
    """

    if not text:
        return

    try:
        engine.say(text)
        engine.runAndWait()

    except Exception as error:
        print("Voice output error:", error)


def set_voice_speed(speed):

    """
    Change speaking speed.
    """

    engine.setProperty("rate", speed)


def set_volume(volume):

    """
    Change speaking volume.
    """

    volume = max(0.0, min(1.0, volume))

    engine.setProperty("volume", volume)
