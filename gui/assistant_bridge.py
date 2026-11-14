
from PySide6.QtCore import QObject, QThread, Signal, Slot

from assistant.voice_input import listen_for_command
from assistant.command_handler import process_command
from assistant.voice_output import speak


class VoiceWorker(QThread):
    command_ready = Signal(str)

    def run(self):
        command = listen_for_command()

        # Ignore the result if Stop was pressed.
        if not self.isInterruptionRequested() and command:
            self.command_ready.emit(command)


class AssistantBridge(QObject):
    commandRecognized = Signal(str)
    assistantResponse = Signal(str)
    statusChanged = Signal(str)

    def __init__(self):
        super().__init__()
        self.voice_worker = None

    @Slot()
    def startListening(self):
        if self.voice_worker and self.voice_worker.isRunning():
            return

        self.statusChanged.emit("LISTENING")

        self.voice_worker = VoiceWorker()
        self.voice_worker.command_ready.connect(
            self.handle_command
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
        self.commandRecognized.emit(command)

        response = process_command(command)
        self.assistantResponse.emit(response)

        if "Found " in response:
            speak("I found matching files. Check your screen.")
        elif "\n" in response:
            speak("Please check the screen for the available commands.")
        else:
            speak(response)

    def listening_finished(self):
        self.statusChanged.emit("ONLINE")
        self.voice_worker = None
