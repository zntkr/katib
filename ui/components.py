import os
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QHBoxLayout, QWidget, QComboBox, QSizePolicy, QListView, QPushButton
from PySide6.QtCore import Qt, QEvent

from ui.theme import G_1, FONT_SIZE_SM
from ui.utils import colorize_svg_icon

class NoScrollComboBox(QComboBox):
    """Swallows scroll events to prevent accidental value changes (and parent scroll area sticking)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Width is driven by the layout, not by content, to avoid breaking the UI.
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(1)
        self.setMinimumWidth(50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Cap visible items at 8 to keep the dropdown compact.
        self.setMaxVisibleItems(8)

        # Long text is elided on the right so it never breaks the layout.
        view = self.view()
        if view:
            view.setTextElideMode(Qt.TextElideMode.ElideRight)
            if isinstance(view, QListView):
                view.setWordWrap(False)

        # Event filter suppresses tooltips when the text already fits.
        self.installEventFilter(self)
        if self.view():
            self.view().viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.ToolTip:
            if obj == self:
                if self.fontMetrics().horizontalAdvance(self.currentText()) <= self.width() - 32:
                    return True  # text fits in combo box — suppress tooltip
            elif self.view() and obj == self.view().viewport():
                if hasattr(event, "pos"):
                    index = self.view().indexAt(event.pos())
                    if index.isValid():
                        rect = self.view().visualRect(index)
                        if self.view().fontMetrics().horizontalAdvance(self.itemText(index.row())) <= rect.width() - 16:
                            return True  # text fits in menu item — suppress tooltip
        return super().eventFilter(obj, event)

    # --- Automatic Tooltip Injection ---
    def addItem(self, *args, **kwargs):
        super().addItem(*args, **kwargs)
        idx = self.count() - 1
        self.setItemData(idx, self.itemText(idx), Qt.ItemDataRole.ToolTipRole)

    def insertItem(self, index, *args, **kwargs):
        super().insertItem(index, *args, **kwargs)
        self.setItemData(index, self.itemText(index), Qt.ItemDataRole.ToolTipRole)
        
    def setItemText(self, index, text):
        super().setItemText(index, text)
        self.setItemData(index, text, Qt.ItemDataRole.ToolTipRole)

    def showPopup(self):
        # Lock the dropdown list to the same width as the combo box shell on open.
        # This forces long text to be elided to a single line rather than overflowing the screen.
        if self.view():
            self.view().setMinimumWidth(self.width())
            self.view().setMaximumWidth(self.width())
        super().showPopup()

    def wheelEvent(self, event):
        event.ignore()

class SettingGroup(QFrame):
    """HUD-style grouping card."""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("settingCard")
        self.group_layout = QVBoxLayout(self)
        self.group_layout.setContentsMargins(G_1, G_1, G_1, G_1)
        self.group_layout.setSpacing(G_1)

        from ui.theme import theme_manager
        self.title_label = QLabel(title.upper())
        self.title_label.setMinimumWidth(10)
        self.group_layout.addWidget(self.title_label)

        self.title_label.setObjectName("settingCardTitle")

    def add_widget_row(self, label_text: str, widget: QWidget, full_width: bool = False, widget_width: int | None = 136):
        from ui.theme import G_1, theme_manager
        p = theme_manager.palette
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"color: {p['CLR_TEXT_MUTED']};")
        lbl.setWordWrap(True)
        lbl.setMinimumWidth(10)  # allow label to shrink and wrap to the next line
        if full_width:
            self.group_layout.addWidget(lbl)
            self.group_layout.addWidget(widget)
        else:
            lay = QHBoxLayout()
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(G_1)  # 8-pt grid spacing
            lay.addWidget(lbl, stretch=1)
            if widget_width is not None:
                widget.setFixedWidth(widget_width)
            lay.addWidget(widget)
            self.group_layout.addLayout(lay)

class DynamicIconButton(QPushButton):
    """SVG icon button: muted at rest, brighter on hover, coloured when pressed/active."""
    def __init__(self, svg_path_or_str: str, action_color: str, fallback_text: str = "", parent=None, idle_color: str | None = None, disabled_color: str | None = None, hover_color: str | None = None):
        super().__init__(parent)
        self.setProperty("isIconBtn", True)

        from ui.theme import theme_manager
        p = theme_manager.palette
        self.idle_color = idle_color if idle_color else p["CLR_IDLE"]  # default muted beige
        self.hover_color = hover_color if hover_color else p["CLR_TEXT"]  # bright cream on hover
        self.action_color = action_color          # identity colour when pressed/active
        self.disabled_color = disabled_color if disabled_color else p["CLR_BG"]  # sunken dark when disabled
        
        is_raw_svg = svg_path_or_str.strip().startswith("<svg")
        if is_raw_svg or os.path.exists(svg_path_or_str):
            self.icon_idle = colorize_svg_icon(svg_path_or_str, self.idle_color)
            self.icon_hover = colorize_svg_icon(svg_path_or_str, self.hover_color)
            self.icon_action = colorize_svg_icon(svg_path_or_str, self.action_color)
            self.icon_disabled = colorize_svg_icon(svg_path_or_str, self.disabled_color)
            self.setIcon(self.icon_idle)
            from PySide6.QtCore import QSize
            self.setIconSize(QSize(16, 16))
            self._has_svg = True
        else:
            self._has_svg = False
            from PySide6.QtGui import QFont
            from ui.theme import FONT_SIZE_LG
            icon_font = QFont()
            icon_font.setFamilies(["Segoe Fluent Icons", "Segoe MDL2 Assets", "Segoe UI Symbol"])
            icon_font.setPointSize(FONT_SIZE_LG)
            self.setFont(icon_font)
            self.setText(fallback_text)
            
        self.is_active = False

    def set_active(self, active: bool):
        self.is_active = active
        self._update_icon()

    def _update_icon(self):
        if not self._has_svg:
            return
        if not self.isEnabled():
            self.setIcon(self.icon_disabled)
        elif self.isDown() or self.is_active:
            self.setIcon(self.icon_action)
        elif self.underMouse():
            self.setIcon(self.icon_hover)
        else:
            self.setIcon(self.icon_idle)

    def changeEvent(self, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.EnabledChange:
            self._update_icon()
        super().changeEvent(event)

    def enterEvent(self, event):
        super().enterEvent(event)
        self._update_icon()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._update_icon()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._update_icon()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._update_icon()
