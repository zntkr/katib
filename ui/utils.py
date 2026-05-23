from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

def colorize_svg_icon(source: str, color_hex: str, size: int = 16) -> QIcon:
    """Renders the given SVG file or raw SVG string as a QPixmap and fills it with the specified colour."""
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon
    from PySide6.QtCore import Qt, QByteArray

    if source.strip().startswith("<svg"):
        # Replace the {color} placeholder with black so the renderer can draw the shape.
        svg_data = source.replace("{color}", "#000000").encode('utf-8')
        renderer = QSvgRenderer(QByteArray(svg_data))
    else:
        renderer = QSvgRenderer(source)
        
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QRectF
    dpr = QApplication.primaryScreen().devicePixelRatio() if QApplication.instance() else 1.0
    physical_size = int(size * dpr)

    pixmap = QPixmap(physical_size, physical_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(dpr)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))

    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(QRectF(0, 0, size, size), QColor(color_hex))
    painter.end()

    return QIcon(pixmap)

def qt_key_to_keyboard(qt_key: int) -> str | None:
    """Converts a Qt key code to the name understood by the keyboard library."""
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
    """Creates a solid-colour QIcon for tests and placeholders."""
    from PySide6.QtGui import QPixmap, QColor
    from PySide6.QtCore import Qt
    px = QPixmap(16, 16)
    if color_hex:
        px.fill(QColor(color_hex))
    else:
        px.fill(Qt.GlobalColor.transparent)
    return QIcon(px)