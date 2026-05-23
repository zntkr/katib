from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

def colorize_svg_icon(source: str, color_hex: str, size: int = 16) -> QIcon:
    """Belirtilen SVG dosyasını veya ham SVG metnini QPixmap olarak çizer ve belirtilen renkle doldurur."""
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon
    from PySide6.QtCore import Qt, QByteArray

    if source.strip().startswith("<svg"):
        # Prototipteki gibi {color} değişkeni varsa siyahla değiştir ki renderer çizebilsin.
        svg_data = source.replace("{color}", "#000000").encode('utf-8')
        renderer = QSvgRenderer(QByteArray(svg_data))
    else:
        renderer = QSvgRenderer(source)
        
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color_hex))
    painter.end()
    
    return QIcon(pixmap)

def qt_key_to_keyboard(qt_key: int) -> str | None:
    """Qt key kodunu keyboard kütüphanesinin anladığı isme çevirir."""
    from PySide6.QtCore import Qt as _Qt
    if _Qt.Key.Key_F1.value <= qt_key <= _Qt.Key.Key_F12.value:
        return f"f{qt_key - _Qt.Key.Key_F1.value + 1}"
    special = {
        _Qt.Key.Key_Space.value    : "space",
        _Qt.Key.Key_Tab.value      : "tab",
        _Qt.Key.Key_Return.value   : "enter",
        _Qt.Key.Key_Escape.value   : "esc",
        _Qt.Key.Key_Backspace.value: "backspace",
        _Qt.Key.Key_Delete.value   : "delete",
        _Qt.Key.Key_Insert.value   : "insert",
        _Qt.Key.Key_Home.value     : "home",
        _Qt.Key.Key_End.value      : "end",
        _Qt.Key.Key_PageUp.value   : "page up",
        _Qt.Key.Key_PageDown.value : "page down",
        _Qt.Key.Key_Up.value       : "up",
        _Qt.Key.Key_Down.value     : "down",
        _Qt.Key.Key_Left.value     : "left",
        _Qt.Key.Key_Right.value    : "right",
    }
    if qt_key in special:
        return special[qt_key]
    if 32 <= qt_key <= 126:
        return chr(qt_key).lower()
    return None

def _make_icon(color_hex: str | None = None) -> QIcon:
    """Testler ve placeholder'lar için düz renkli QIcon oluşturur."""
    from PySide6.QtGui import QPixmap, QColor
    from PySide6.QtCore import Qt
    px = QPixmap(16, 16)
    if color_hex:
        px.fill(QColor(color_hex))
    else:
        px.fill(Qt.GlobalColor.transparent)
    return QIcon(px)