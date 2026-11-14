import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QFile
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
from PySide6.QtWebChannel import QWebChannel

from gui.assistant_bridge import AssistantBridge


class DebugPage(QWebEnginePage):
    """Prints JavaScript console messages (errors, warnings, logs) to the terminal."""

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        print(f"JS [{level.name}]: {message} (line {line_number}, {source_id})")


class MiniAssistantWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.html_file = (
            Path(__file__).resolve().parent.parent
            / "frontend"
            / "code.html"
        )

        self.setWindowTitle("Desktop Assistant")
        self.resize(420, 760)
        self.setMinimumSize(380, 640)

        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
        )

        # Web view with a debug page so JS errors show in the terminal.
        self.web_view = QWebEngineView(self)
        self.web_view.setPage(DebugPage(self.web_view))
        self.setCentralWidget(self.web_view)

        settings = self.web_view.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled, True
        )
        # IMPORTANT: lets the local HTML load Tailwind, Google Fonts and
        # Material Symbols from the internet.
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )

        # Copy Qt's WebChannel JavaScript into the frontend folder.
        self.webchannel_js = self.html_file.parent / "qwebchannel.js"

        if not self.webchannel_js.exists():
            copied = QFile.copy(
                ":/qtwebchannel/qwebchannel.js",
                str(self.webchannel_js)
            )
            print("WebChannel JS copied:", copied)

        print("WebChannel JS exists:", self.webchannel_js.exists())

        # Set up Python <-> JavaScript bridge.
        self.bridge = AssistantBridge()
        self.channel = QWebChannel(self.web_view.page())
        self.channel.registerObject("assistantBridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        self.web_view.loadFinished.connect(
            lambda success: print("HTML loaded:", success)
        )

        self.load_frontend()

    def load_frontend(self):

        if not self.html_file.exists():
            print("HTML file not found:", self.html_file)
            return

        print("Loading:", self.html_file)

        self.web_view.load(QUrl.fromLocalFile(str(self.html_file)))


def run_app():

    app = QApplication(sys.argv)

    window = MiniAssistantWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()