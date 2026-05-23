import sys
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QPushButton
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtSvg import QSvgRenderer

# Gruvbox Renk Paleti
COLOR_IDLE = "#bdae93"    # Soluk Bej (Bekleme Durumu)
COLOR_SETTING = "#83a598" # Mavi (Ayarlar)
COLOR_TERM = "#d79921"    # Sarı (Terminal)
COLOR_COPY = "#fe8019"    # Turuncu (Kopyala)

# SVG Ham Verileri (currentColor yerine dinamik renk basacağız)
SVG_SETTINGS = '<svg viewBox="0 0 24 24" stroke="{color}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>'
SVG_TERMINAL = '<svg viewBox="0 0 24 24" stroke="{color}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>'
SVG_COPY = '<svg viewBox="0 0 24 24" stroke="{color}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>'

def colorize_svg(svg_str, color) -> QIcon:
    """SVG metnindeki {color} değişkenine rengi basıp QIcon üretir."""
    colored_svg = svg_str.replace("{color}", color)
    renderer = QSvgRenderer(QByteArray(colored_svg.encode('utf-8')))
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)

class DynamicIconButton(QPushButton):
    def __init__(self, svg_str, hover_color):
        super().__init__()
        self.icon_idle = colorize_svg(svg_str, COLOR_IDLE)
        self.icon_hover = colorize_svg(svg_str, hover_color)
        
        self.setIcon(self.icon_idle)
        self.setFixedSize(32, 32)
        self.is_active = False
        
        # Zemin css'i (Katib'in orjinal zemin renkleri)
        self.setStyleSheet("""
            QPushButton { background-color: #3c3836; border: none; border-radius: 4px; }
            QPushButton:hover { background-color: #504945; }
            QPushButton:pressed { background-color: #1d2021; }
        """)

    def toggle_active(self):
        """Tıklanınca Aktif/Pasif durumunu değiştirir (Pencere açılması gibi)"""
        self.is_active = not self.is_active
        self.setIcon(self.icon_hover if self.is_active else self.icon_idle)

    def enterEvent(self, event):
        if not self.is_active:
            self.setIcon(self.icon_hover)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.is_active:
            self.setIcon(self.icon_idle)
        super().leaveEvent(event)

class PrototypeWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Katib SVG Hover Prototipi")
        self.setStyleSheet("background-color: #282828;") # Ana zemin
        self.setFixedSize(200, 80)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Butonları oluştur
        self.btn_copy = DynamicIconButton(SVG_COPY, COLOR_COPY)
        self.btn_term = DynamicIconButton(SVG_TERMINAL, COLOR_TERM)
        self.btn_set  = DynamicIconButton(SVG_SETTINGS, COLOR_SETTING)
        
        # Tıklama olayları
        self.btn_term.clicked.connect(self.btn_term.toggle_active)
        self.btn_set.clicked.connect(self.btn_set.toggle_active)
        
        layout.addWidget(self.btn_copy)
        layout.addWidget(self.btn_term)
        layout.addWidget(self.btn_set)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PrototypeWindow()
    window.show()
    sys.exit(app.exec())
