import math

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QRectF, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QPalette, QPainter, QPaintEvent, QColor

from ui.theme import theme_manager, G_1, G_2, FONT_SIZE_OSD, PANEL_WIDTH, OSD_BOTTOM_MARGIN
from core.settings import STATE_LISTENING, STATE_PROCESSING, STATE_READY
from core.i18n import t, try_t, upper

# --- OSD Constants ---
OSD_HEIGHT = 56
FADE_DURATION_MS = 250
WAVE_FRAME_MS = 33   # ~30 frames per second

ERROR_DISPLAY_MS = 3000


def loudness(level: float) -> float:
    """The worker's level (rms × 5, capped at 1) as 0..1 on a dB scale: −60 dB is silence,
    −10 dB is full height. A linear scale would leave a quiet microphone looking dead."""
    rms = max(level / 5.0, 1e-6)
    return min(1.0, max(0.0, (20 * math.log10(rms) + 60) / 50))


class LevelWave(QWidget):
    """The strip of bars inside the pill. Three modes:
      level — the microphone level of the last moments, newest on the right (recording)
      busy  — a slow travelling wave (the model is working)
      dot   — a still dot (a message is shown)
    """
    BARS = 14
    BAR_WIDTH = 3
    GAP = 2
    HEIGHT = 24
    EASE = 0.35          # share of the remaining distance a bar covers per frame

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(self.BARS * (self.BAR_WIDTH + self.GAP) - self.GAP, self.HEIGHT)
        self.mode = "dot"
        self.colour = QColor(theme_manager.palette["CLR_TEXT_MUTED"])
        self.bars = [0.0] * self.BARS       # what is drawn, 0..1
        self._targets = [0.0] * self.BARS   # where each bar is heading
        self._phase = 0.0

    def set_mode(self, mode: str, colour: str) -> None:
        self.mode = mode
        self.colour = QColor(colour)
        self.bars = [0.0] * self.BARS
        self._targets = [0.0] * self.BARS
        self._phase = 0.0
        self.update()

    def push_level(self, level: float) -> None:
        """A new level from the microphone: everything moves one bar to the left."""
        if self.mode == "level":
            self._targets = self._targets[1:] + [loudness(level)]
            self.bars = self.bars[1:] + [self.bars[-1]]  # the new bar grows from its neighbour

    def advance(self) -> None:
        """One animation frame."""
        if self.mode == "busy":
            self._phase += 0.22
            self._targets = [0.35 + 0.25 * math.sin(self._phase - i * 0.6) for i in range(self.BARS)]
        self.bars = [bar + (target - bar) * self.EASE for bar, target in zip(self.bars, self._targets)]
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.colour)
        if self.mode == "dot":
            radius = 4
            painter.drawEllipse(QRectF(self.width() / 2 - radius, self.height() / 2 - radius, radius * 2, radius * 2))
        else:
            for i, bar in enumerate(self.bars):
                height = max(self.BAR_WIDTH, bar * self.HEIGHT)  # silence is a row of dots
                x = i * (self.BAR_WIDTH + self.GAP)
                painter.drawRoundedRect(QRectF(x, (self.HEIGHT - height) / 2, self.BAR_WIDTH, height),
                                        self.BAR_WIDTH / 2, self.BAR_WIDTH / 2)
        painter.end()


class MinimalOSD(QWidget):
    """
    Minimal, click-through status indicator shown at the bottom-center of the screen during dictation.
    """
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        # WindowStaysOnTopHint: floats above all other windows.
        # FramelessWindowHint: no window chrome.
        # Tool: hidden from the taskbar.
        # WindowTransparentForInput: mouse clicks pass through to the window behind.
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # --- Transparency ---
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.transparent)
        self.setPalette(pal)

        self.setFixedSize(PANEL_WIDTH, OSD_HEIGHT)

        self._error_active = False
        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.timeout.connect(self._hide_after_error)
        self._osd_state: str = "ready"
        self._osd_error_msg: str = ""
        self.current_level = 0.0
        self._build_ui()
        self._setup_animations()

    def paintEvent(self, event: QPaintEvent) -> None:
        """
        Draws the pill shape (border-radius) directly with QPainter instead of
        delegating to the QSS engine. This eliminates black-corner artefacts on
        systems with DWM transparency issues (Intel GPU, RDP, etc.).
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        p = theme_manager.palette
        color = QColor(p['CLR_BG_DEEP'])
        color.setAlpha(235)

        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 28, 28)
        painter.end()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.container = QFrame()
        self.container.setObjectName("OSDContainer")
        # The background is drawn in paintEvent, so the stylesheet only keeps the frame clear.
        self.container.setStyleSheet("#OSDContainer { background: transparent; border: none; }")

        c_layout = QHBoxLayout(self.container)
        c_layout.setContentsMargins(G_2, 0, G_2, 0)
        c_layout.setSpacing(G_1)
        c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Level wave — left side: bars while recording or working, a dot for a message.
        self.wave = LevelWave()
        c_layout.addWidget(self.wave)

        self.text_label = QLabel(upper(t(STATE_READY)))
        _osd_font = QFont("Segoe UI Variable Display", -1, QFont.Weight.Bold)
        _osd_font.setPixelSize(FONT_SIZE_OSD)
        self.text_label.setFont(_osd_font)
        c_layout.addWidget(self.text_label)

        root.addWidget(self.container)

    def _setup_animations(self):
        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(FADE_DURATION_MS)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_anim.finished.connect(self._on_hide_finished)

        # Drives the level wave while the pill is recording or working.
        self.wave_timer = QTimer(self)
        self.wave_timer.setInterval(WAVE_FRAME_MS)
        self.wave_timer.timeout.connect(self.wave.advance)

    def update_level(self, level: float):
        self.current_level = min(1.0, max(0.0, level))
        self.wave.push_level(self.current_level)  # ignored unless the wave shows the microphone

    # --- Public API (State Management) ---
    def refresh_language(self):
        if self._osd_state == "recording":
            self.text_label.setText(upper(t(STATE_LISTENING)))
        elif self._osd_state == "processing":
            self.text_label.setText(upper(t(STATE_PROCESSING)))
        elif self._osd_state == "error":
            self.text_label.setText(upper(try_t(self._osd_error_msg))[:60])

    def setStateRecording(self):
        self._osd_state = "recording"
        p = theme_manager.palette
        self.text_label.setText(upper(t(STATE_LISTENING)))
        self.text_label.setStyleSheet(f"color: {p['CLR_TEXT_STATUS']};")
        self.wave.set_mode("level", p['CLR_ERR'])
        self.wave_timer.start()
        self.show_osd()

    def setStateProcessing(self):
        self._osd_state = "processing"
        p = theme_manager.palette
        self.text_label.setText(upper(t(STATE_PROCESSING)))
        self.text_label.setStyleSheet(f"color: {p['CLR_TEXT_STATUS']};")
        self.wave.set_mode("busy", p['CLR_INFO'])
        self.wave_timer.start()
        self.show_osd()

    def setStateError(self, msg: str):
        self._osd_state = "error"
        self._osd_error_msg = msg
        p = theme_manager.palette
        text = upper(try_t(msg))[:60]
        self.text_label.setText(text)
        self.text_label.setStyleSheet(f"color: {p['CLR_TEXT_STATUS']};")
        self.wave.set_mode("dot", p['CLR_WARN'])
        self.wave_timer.stop()
        self._error_active = True
        self.show_osd()
        self._error_timer.stop()
        self._error_timer.start(ERROR_DISPLAY_MS)

    def show_osd(self):
        self.position_osd()
        if self.isVisible() and self.windowOpacity() > 0.9:
            return
        self.setWindowOpacity(0)
        self.show()
        self.fade_anim.stop()
        self.fade_anim.setStartValue(0)
        self.fade_anim.setEndValue(1)
        self.fade_anim.start()

    def _hide_after_error(self):
        self._error_active = False
        self.hide_osd()

    def hide_osd(self):
        if self._error_active:
            return
        self.fade_anim.stop()
        self.fade_anim.setStartValue(self.windowOpacity())
        self.fade_anim.setEndValue(0)
        self.fade_anim.start()

    def _on_hide_finished(self):
        if self.fade_anim.endValue() == 0:
            self.hide()
            self.wave_timer.stop()

    def position_osd(self):
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = screen.height() - self.height() - OSD_BOTTOM_MARGIN
        self.move(x, y)

    def closeEvent(self, event) -> None:
        """Stops timers and animations on teardown to prevent memory leaks."""
        self.wave_timer.stop()
        self._error_timer.stop()
        self.fade_anim.stop()
        for timer in self.findChildren(QTimer):
            if timer.isActive():
                timer.stop()
        super().closeEvent(event)
