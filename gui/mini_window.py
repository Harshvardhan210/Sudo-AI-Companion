import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QFile, QObject, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
from PySide6.QtWebChannel import QWebChannel

from gui.assistant_bridge import AssistantBridge


# ---------------- Window settings (change these if you like) ----------------
ZOOM = 0.32                 # smaller = lower number (0.25 tiny, 0.4 medium)
DESIGN_WIDTH = 380          # size of the design in the HTML (don't change)
DESIGN_HEIGHT = 540
WINDOW_WIDTH = int(DESIGN_WIDTH * ZOOM)
WINDOW_HEIGHT = int(DESIGN_HEIGHT * ZOOM)
# Text command mode (search bar) uses a bigger, normal-size window
TEXT_ZOOM = 1.0
TEXT_WIDTH = 400
TEXT_HEIGHT = 260
SCREEN_MARGIN = 12          # gap from the right edge of the screen
# Notes card (opens on the left of the robot): extra window size while it is open
NOTES_CARD_WIDTH = 284
NOTES_CARD_HEIGHT = 440
VERTICAL_POSITION = "center"  # "center", "top" or "bottom"
# ----------------------------------------------------------------------------


def compute_layout(text_mode, notes_open):
    """Return (zoom, width, height) of the window for the current mode."""

    if text_mode:
        return TEXT_ZOOM, TEXT_WIDTH, TEXT_HEIGHT

    width, height = WINDOW_WIDTH, WINDOW_HEIGHT

    if notes_open:
        width += NOTES_CARD_WIDTH
        height = max(height, NOTES_CARD_HEIGHT)

    return ZOOM, width, height


class DebugPage(QWebEnginePage):
    """Prints JavaScript console messages (errors, warnings, logs) to the terminal."""

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        print(f"JS [{level.name}]: {message} (line {line_number}, {source_id})")


class WindowController(QObject):
    """Lets the HTML move/close the frameless window (no title bar)."""

    def __init__(self, window):
        super().__init__(window)
        self._window = window

    @Slot()
    def startMove(self):
        handle = self._window.windowHandle()
        if handle is not None:
            handle.startSystemMove()

    @Slot(bool)
    def setTextMode(self, enabled):
        self._window.set_text_mode(enabled)

    @Slot(bool)
    def setNotesCard(self, is_open):
        self._window.set_notes_card(is_open)

    @Slot()
    def closeApp(self):
        QApplication.quit()


class MiniAssistantWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.html_file = (
            Path(__file__).resolve().parent.parent
            / "frontend"
            / "code.html"
        )

        self.setWindowTitle("Desktop Assistant")

        # Frameless, always-on-top, transparent window.
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")

        self.current_zoom = ZOOM
        self.text_mode = False
        self.notes_open = False
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.move_to_right_side()

        # Web view with a transparent background.
        self.web_view = QWebEngineView(self)
        self.web_view.setPage(DebugPage(self.web_view))
        self.web_view.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.web_view.setStyleSheet("background: transparent;")
        self.web_view.page().setBackgroundColor(QColor(0, 0, 0, 0))
        self.web_view.setZoomFactor(self.current_zoom)
        self.setCentralWidget(self.web_view)

        settings = self.web_view.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled, True
        )
        # Lets the local HTML load Tailwind, Google Fonts and Material Symbols.
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

        # Python <-> JavaScript bridge.
        self.bridge = AssistantBridge()
        self.window_controller = WindowController(self)
        self.channel = QWebChannel(self.web_view.page())
        self.channel.registerObject("assistantBridge", self.bridge)
        self.channel.registerObject("windowController", self.window_controller)
        self.web_view.page().setWebChannel(self.channel)

        self.web_view.loadFinished.connect(self.on_load_finished)

        self.load_frontend()

    def on_load_finished(self, success):
        print("HTML loaded:", success)
        self.web_view.setZoomFactor(self.current_zoom)  # keep the chosen size after loading
        self.update_page_scale()

    def update_page_scale(self):
        """Tell the page the zoom, so the notes card text stays readable."""
        self.web_view.page().runJavaScript(
            f"if (window.setUiScale) setUiScale({self.current_zoom});"
        )

    def set_text_mode(self, enabled):
        """Switch between the small robot window and the bigger search-bar window."""
        self.text_mode = bool(enabled)
        self.apply_layout()

        if enabled:
            self.activateWindow()
            self.raise_()
            self.web_view.setFocus()

    def set_notes_card(self, is_open):
        """Make the window wider (to the left) while the notes card is open."""
        self.notes_open = bool(is_open)
        self.apply_layout()

    def apply_layout(self):
        """Resize for the current mode, keeping the right edge and middle in place."""
        geo = self.geometry()
        right_edge = geo.x() + geo.width()
        center_y = geo.y() + geo.height() // 2

        zoom, width, height = compute_layout(self.text_mode, self.notes_open)

        self.current_zoom = zoom
        self.web_view.setZoomFactor(zoom)
        self.resize(width, height)

        # Stay inside the screen.
        area = QApplication.primaryScreen().availableGeometry()
        x = max(area.left(), min(right_edge - width, area.right() - width + 1))
        y = max(area.top(), min(center_y - height // 2, area.bottom() - height + 1))
        self.move(x, y)

        self.update_page_scale()

    def move_to_right_side(self):
        """Place the window on the right edge of the primary screen."""
        area = QApplication.primaryScreen().availableGeometry()

        x = area.right() - WINDOW_WIDTH - SCREEN_MARGIN + 1

        if VERTICAL_POSITION == "top":
            y = area.top() + SCREEN_MARGIN
        elif VERTICAL_POSITION == "bottom":
            y = area.bottom() - WINDOW_HEIGHT - SCREEN_MARGIN + 1
        else:
            y = area.top() + (area.height() - WINDOW_HEIGHT) // 2

        self.move(x, y)

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