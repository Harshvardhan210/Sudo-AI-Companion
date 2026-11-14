import time

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from assistant.voice_input import listen_continuously
from assistant.command_handler import process_command
from assistant.voice_output import speak


class VoiceWorker(QThread):
    """Listens continuously in the background and reports "sudo ..." commands."""

    command_ready = Signal(str)
    listening_error = Signal(str)

    def __init__(self):
        super().__init__()
        self._paused = False
        self._ignore_until = 0.0

    def pause(self):
        """Stop picking up speech (while a command runs / the assistant talks)."""
        self._paused = True

    def resume(self):
        """Start listening again (with a short delay so the echo is ignored)."""
        self._ignore_until = time.time() + 0.8
        self._paused = False

    def _should_stop(self):
        return self.isInterruptionRequested()

    def _is_paused(self):
        return self._paused or time.time() < self._ignore_until

    def run(self):
        try:
            for command in listen_continuously(
                self._should_stop,
                self._is_paused
            ):
                # Stay silent until the assistant has finished answering.
                self._paused = True
                self.command_ready.emit(command)

        except OSError as error:
            print("Assistant: Microphone error.")
            print("Error:", error)
            self.listening_error.emit(f"Microphone error: {error}")

        except Exception as error:
            print("Assistant: Listening stopped unexpectedly.")
            print("Error:", error)
            self.listening_error.emit(f"Listening error: {error}")


class AssistantBridge(QObject):
    commandRecognized = Signal(str)
    assistantResponse = Signal(str)
    statusChanged = Signal(str)

    def __init__(self):
        super().__init__()
        self.voice_worker = None

    @Slot()
    def startListening(self):
        # Already listening continuously.
        if self.voice_worker and self.voice_worker.isRunning():
            return

        self.statusChanged.emit("LISTENING")

        self.voice_worker = VoiceWorker()
        self.voice_worker.command_ready.connect(
            self.handle_command
        )
        self.voice_worker.listening_error.connect(
            self.handle_listening_error
        )
        self.voice_worker.finished.connect(
            self.listening_finished
        )
        self.voice_worker.start()

    @Slot()
    def stopListening(self):
        if self.voice_worker and self.voice_worker.isRunning():
            self.voice_worker.requestInterruption()
            self.statusChanged.emit("STOPPING")

    @Slot(str)
    def handle_command(self, command):
        # Tell the page first so the working animation starts, then run the
        # command a moment later (lets the page update before we block).
        self.commandRecognized.emit(command)

        worker = self.voice_worker
        QTimer.singleShot(60, lambda: self._execute(command, worker))

    def _execute(self, command, worker):
        response = "Sorry, something went wrong."

        try:
            response = process_command(command)
            self.assistantResponse.emit(response)

        except Exception as error:
            print("Command error:", error)
            self.assistantResponse.emit(response)

        QTimer.singleShot(60, lambda: self._speak_response(response, worker))

    def _speak_response(self, response, worker):
        try:
            if "Found " in response:
                speak("I found matching files. Check your screen.")
            elif "\n" in response:
                speak("Please check the screen for the available commands.")
            else:
                speak(response)

        finally:
            # Listen for the next "sudo ..." command.
            if worker is not None and worker.isRunning():
                worker.resume()

    @Slot(str)
    def handle_listening_error(self, message):
        self.assistantResponse.emit(message)

    def listening_finished(self):
        self.statusChanged.emit("ONLINE")
        self.voice_worker = None