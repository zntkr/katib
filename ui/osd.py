from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QGraphicsOpacityEffect, QFrame
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QPalette, QPainter, QPaintEvent, QColor

from ui.theme import theme_manager, G_1, G_2, FONT_SIZE_MD, FONT_SIZE_LG, PANEL_WIDTH, OSD_BOTTOM_MARGIN
from core.settings import STATE_RECORDING, STATE_PROCESSING, STATE_READY
from core.i18n import t, try_t
from ui.icons import ICN_DOT
from ui.utils import colorize_svg_icon

# --- OSD Sabitleri ---
OSD_HEIGHT = 56
FADE_DURATION_MS = 250
PULSE_INTERVAL_MS = 50
ERROR_DISPLAY_MS = 3000
ICON_SIZE = 14

class MinimalOSD(QWidget):
    """
    Katib esnasında sağ altta beliren, etkileşimsiz (click-through) ve minimalist durum göstergesi.
    """
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        
        # --- Pencere Bayrakları (Flags) ---
        # WindowStaysOnTopHint: Diğer pencerelerin üstünde kalır.
        # FramelessWindowHint: Çerçevesiz (Mühendislik estetiği).
        # Tool: Görev çubuğunda gözükmez.
        # WindowTransparentForInput: Fare tıklamalarını arkasındaki pencereye geçirir.
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # --- Şeffaflık ---
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.transparent)
        self.setPalette(pal)
        
        self.setFixedSize(PANEL_WIDTH, OSD_HEIGHT)
        
        self._error_active = False
        self._error_timer = QTimer(self)
        self._error_timer.setSingleShot(True)
        self._error_timer.timeout.connect(self._hide_after_error)
        self._build_ui()
        self._setup_animations()

    def paintEvent(self, event: QPaintEvent) -> None:
        """
        Hap tasarımını (border-radius) QSS motoruna bırakmak yerine 
        doğrudan native Qt grafik motoruyla (QPainter) çiziyoruz.
        Bu, Intel GPU veya RDP gibi DWM saydamlık sorunu yaşanan
        sistemlerde siyah köşe oluşumunu kökünden çözer.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        p = theme_manager.palette
        color = QColor(p['CLR_BG_DEEP'])
        bg_alpha = 235 if theme_manager.is_dark else 245
        color.setAlpha(bg_alpha)
        
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 28, 28)
        painter.end()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        
        self.container = QFrame()
        self.container.setObjectName("OSDContainer")
        self._update_colors() # İlk renkleri uygula
        
        c_layout = QHBoxLayout(self.container)
        c_layout.setContentsMargins(G_2, 0, G_2, 0)
        c_layout.setSpacing(4)
        c_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Status Icon (sol tarafta, tıpkı dashboard badge gibi)
        self.icon_label = QLabel()
        self.icon_label.setFixedWidth(ICON_SIZE)

        # İkon için Opacity Effect (Pulsing için)
        self.icon_opacity = QGraphicsOpacityEffect(self.icon_label)
        self.icon_label.setGraphicsEffect(self.icon_opacity)
        c_layout.addWidget(self.icon_label)
        
        # Status Text
        self.text_label = QLabel(t(STATE_READY).upper())
        self.text_label.setFont(QFont("Segoe UI Variable Display", FONT_SIZE_LG, QFont.Weight.Bold))
        c_layout.addWidget(self.text_label)
        
        root.addWidget(self.container)

    def _setup_animations(self):
        # Fade In/Out
        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(FADE_DURATION_MS)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_anim.finished.connect(self._on_hide_finished)

        # Pulse (Kayıt esnasında)
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._pulse_effect)
        self._pulse_val = 1.0
        self._pulse_dir = -0.06

    def _pulse_effect(self):
        self._pulse_val += self._pulse_dir
        if self._pulse_val <= 0.3 or self._pulse_val >= 1.0:
            self._pulse_dir *= -1
        self.icon_opacity.setOpacity(self._pulse_val)

    def _update_colors(self, *args):
        p = theme_manager.palette
        # Arka plan native QPainter ile çizildiği için QSS sadece metinleri yönetir.
        self.container.setStyleSheet(f"""
            #OSDContainer {{ background: transparent; border: none; }}
            QLabel {{ color: {p['CLR_TEXT']}; background: transparent; }}
        """)
        if hasattr(self, 'text_label'):
            self.text_label.setStyleSheet(f"color: {p['CLR_TEXT_STATUS']};")
        self.update() # Tema değişirse paintEvent'i yeniden tetikle

    # --- Public API (Durum Yönetimi) ---
    def setStateRecording(self):
        p = theme_manager.palette
        self.text_label.setText(t(STATE_RECORDING))
        self.text_label.setStyleSheet(f"color: {p['CLR_TEXT_STATUS']};")
        self.icon_label.setPixmap(colorize_svg_icon(ICN_DOT, p['CLR_ERR']).pixmap(ICON_SIZE, ICON_SIZE))
        self.pulse_timer.start(PULSE_INTERVAL_MS)
        self.show_osd()

    def setStateProcessing(self):
        p = theme_manager.palette
        self.text_label.setText(t(STATE_PROCESSING))
        self.text_label.setStyleSheet(f"color: {p['CLR_TEXT_STATUS']};")
        self.icon_label.setPixmap(colorize_svg_icon(ICN_DOT, p['CLR_INFO']).pixmap(ICON_SIZE, ICON_SIZE))
        self.pulse_timer.stop()
        self.icon_opacity.setOpacity(1.0)
        self.show_osd()

    def setStateError(self, msg: str):
        p = theme_manager.palette
        text = try_t(msg).upper()[:60]
        self.text_label.setText(text)
        self.text_label.setStyleSheet(f"color: {p['CLR_TEXT_STATUS']};")
        self.icon_label.setPixmap(colorize_svg_icon(ICN_DOT, p['CLR_WARN']).pixmap(ICON_SIZE, ICON_SIZE))
        self.pulse_timer.stop()
        self.icon_opacity.setOpacity(1.0)
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
            self.pulse_timer.stop()

    def position_osd(self):
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = screen.height() - self.height() - OSD_BOTTOM_MARGIN
        self.move(x, y)

    def closeEvent(self, event) -> None:
        """Teardown/kapanış sırasında QTimer ve animasyonların memory leak yaratmasını önler."""
        self.pulse_timer.stop()
        self._error_timer.stop()
        self.fade_anim.stop()
        for timer in self.findChildren(QTimer):
            if timer.isActive():
                timer.stop()
        super().closeEvent(event)
