from PySide6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout
from PySide6.QtCore import Qt, QRect, QEvent, QPointF
from PySide6.QtGui import QPaintEvent, QIcon, QEnterEvent
from unittest.mock import patch

from ui.components import SettingGroup, NoScrollComboBox, DynamicIconButton


class TestNoScrollComboBox:
    def test_addItem_injects_tooltip(self, qapp):
        combo = NoScrollComboBox()
        combo.addItem("Test Item", "data")
        assert combo.itemData(0, Qt.ItemDataRole.ToolTipRole) == "Test Item"

    def test_insertItem_injects_tooltip(self, qapp):
        combo = NoScrollComboBox()
        combo.addItem("Item 1")
        combo.insertItem(0, "Inserted Item", "data")
        assert combo.itemData(0, Qt.ItemDataRole.ToolTipRole) == "Inserted Item"

    def test_setItemText_updates_tooltip(self, qapp):
        combo = NoScrollComboBox()
        combo.addItem("Item 1")
        combo.setItemText(0, "Updated Item")
        assert combo.itemData(0, Qt.ItemDataRole.ToolTipRole) == "Updated Item"

    def test_showPopup_sets_view_width(self, qapp):
        combo = NoScrollComboBox()
        combo.resize(200, 30)
        combo.showPopup()
        view = combo.view()
        assert view.minimumWidth() == 200
        assert view.maximumWidth() == 200


class TestSettingGroup:
    def test_title_label_is_uppercased(self, qapp):
        """title_label text must always be converted to upper case."""
        group = SettingGroup("ses ayarlari")
        assert group.title_label.text() == "SES AYARLARI"

    def test_add_widget_row_inline(self, qapp):
        """full_width=False: widget must be placed inside a QHBoxLayout."""
        group = SettingGroup("test")
        widget = QLabel("w")
        group.add_widget_row("Label", widget, full_width=False)
        # The last item in group_layout must be a QHBoxLayout
        count = group.group_layout.count()
        last_item = group.group_layout.itemAt(count - 1)
        assert last_item is not None
        assert isinstance(last_item.layout(), QHBoxLayout)

    def test_add_widget_row_full_width(self, qapp):
        """full_width=True: label and widget must be added directly to group_layout."""
        group = SettingGroup("test")
        widget = QLabel("w")
        before = group.group_layout.count()
        group.add_widget_row("Label", widget, full_width=True)
        # count must increase by 2 because two widgets (label + widget) are added
        assert group.group_layout.count() == before + 2


def _make_enter_event():
    """PySide6 QEnterEvent require localPos, windowPos, globalPos parameters."""
    return QEnterEvent(QPointF(0, 0), QPointF(0, 0), QPointF(0, 0))

class TestDynamicIconButton:
    @patch("os.path.exists", return_value=True)
    @patch("ui.components.colorize_svg_icon", side_effect=lambda p, c: QIcon())
    def test_enter_leave_events_change_icon(self, mock_colorize, mock_exists, qapp):
        btn = DynamicIconButton("fake.svg", "#ff0000")
        assert btn._has_svg is True

        with patch.object(btn, "setIcon") as mock_set:
            with patch.object(btn, "underMouse", return_value=True):
                btn.enterEvent(_make_enter_event())
                mock_set.assert_called_once_with(btn.icon_hover)

        with patch.object(btn, "setIcon") as mock_set:
            with patch.object(btn, "underMouse", return_value=False):
                btn.leaveEvent(QEvent(QEvent.Type.Leave))
                mock_set.assert_called_once_with(btn.icon_idle)

    @patch("os.path.exists", return_value=True)
    @patch("ui.components.colorize_svg_icon", side_effect=lambda p, c: QIcon())
    def test_events_ignored_when_active(self, mock_colorize, mock_exists, qapp):
        btn = DynamicIconButton("fake.svg", "#ff0000")
        btn.set_active(True)
        with patch.object(btn, "setIcon") as mock_set:
            btn.enterEvent(_make_enter_event())
            btn.leaveEvent(QEvent(QEvent.Type.Leave))
            assert mock_set.call_count == 2
            mock_set.assert_called_with(btn.icon_action)

    @patch("os.path.exists", return_value=True)
    @patch("ui.components.colorize_svg_icon", side_effect=lambda p, c: QIcon())
    def test_events_ignored_when_disabled(self, mock_colorize, mock_exists, qapp):
        btn = DynamicIconButton("fake.svg", "#ff0000")
        btn.setEnabled(False)
        with patch.object(btn, "setIcon") as mock_set:
            btn.enterEvent(_make_enter_event())
            btn.leaveEvent(QEvent(QEvent.Type.Leave))
            assert mock_set.call_count == 2
            mock_set.assert_called_with(btn.icon_disabled)

    @patch("os.path.exists", return_value=False)
    def test_events_ignored_when_no_svg(self, mock_exists, qapp):
        btn = DynamicIconButton("fake.svg", "#ff0000", fallback_text="X")
        assert btn._has_svg is False
        with patch.object(btn, "setIcon") as mock_set:
            btn.enterEvent(_make_enter_event())
            btn.leaveEvent(QEvent(QEvent.Type.Leave))
            mock_set.assert_not_called()
