import sys
import math
import random
import time
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor

class PrototypeOSDPulse(QWidget):
    def __init__(self):
        super().__init__()
        # OSD Window settings
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(160, 160)
        
        self.current_level = 0.0
        self.displayed_radius = 15.0
        self.base_radius = 15.0
        self.max_radius = 45.0
        
        # 1. Fake Audio Level Generator (High frequency, e.g., 50 Hz -> 20ms)
        # Sinyal mikrofondan hızlıca gelir.
        self.audio_timer = QTimer(self)
        self.audio_timer.timeout.connect(self.simulate_audio)
        self.audio_timer.start(20) 
        
        # 2. UI Throttling Timer (15 FPS -> 66ms)
        # OSD'nin ekrana çizilme hızını sınırlar, CPU kullanımını korur.
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.update_ui)
        self.ui_timer.start(66)

    def simulate_audio(self):
        """Simulate real human speech envelope with sine waves and noise"""
        t = time.time() * 4
        # Create a speech-like bursty pattern
        burst = (math.sin(t) * math.sin(t * 0.5) + 1) / 2 
        noise = random.uniform(0, 0.2)
        if burst > 0.5:
            self.current_level = min(1.0, max(0.0, burst * 0.8 + noise))
        else:
            self.current_level = max(0.0, self.current_level - 0.1) # smooth decay

    def update_ui(self):
        """Throttle UI updates and interpolate scale (pulsing effect)"""
        target_radius = self.base_radius + (self.max_radius - self.base_radius) * self.current_level
        
        # LERP (Linear Interpolation) for smooth pulsing despite the low framerate
        self.displayed_radius += (target_radius - self.displayed_radius) * 0.3
        
        # Trigger repaint only 15 times a second
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. Draw OSD background (Pill shape)
        painter.setBrush(QColor(30, 30, 30, 220))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 20, 20)
        
        center_x = self.width() / 2
        center_y = self.height() / 2 - 10
        
        # 2. Draw Pulsing Shadow (Outer Ring)
        painter.setBrush(QColor(255, 60, 60, 100)) # Semi-transparent red
        painter.drawEllipse(
            QRectF(center_x - self.displayed_radius, center_y - self.displayed_radius, 
                   self.displayed_radius * 2, self.displayed_radius * 2)
        )
        
        # 3. Draw Solid Core Dot (Inner Ring)
        painter.setBrush(QColor(255, 40, 40, 255))
        painter.drawEllipse(
            QRectF(center_x - self.base_radius, center_y - self.base_radius, 
                   self.base_radius * 2, self.base_radius * 2)
        )
        
        # 4. Text
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(self.rect().adjusted(0, 0, 0, -20), 
                         Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, 
                         "15 FPS Pulse")

    def mousePressEvent(self, event):
        # Click to close
        self.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PrototypeOSDPulse()
    window.show()
    sys.exit(app.exec())
