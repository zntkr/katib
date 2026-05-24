import pytest
from unittest.mock import MagicMock
from ui.components import NoScrollComboBox

def test_no_scroll_combobox_ignores_wheel_event():
    """
    Verifies that NoScrollComboBox swallows wheel events, preventing the user
    from accidentally changing the microphone with the scroll wheel.
    """
    combo = NoScrollComboBox()
    mock_event = MagicMock()

    combo.wheelEvent(mock_event)

    # event.ignore() must have been called when a QWheelEvent arrived
    mock_event.ignore.assert_called_once()