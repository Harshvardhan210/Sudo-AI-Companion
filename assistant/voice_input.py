
import speech_recognition as sr


def listen_for_command():

    recognizer = sr.Recognizer()

    try:
        with sr.Microphone() as source:

            print("\nAssistant: Listening...")
            
            # Adjust microphone for background noise
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

        # Convert speech into text
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
