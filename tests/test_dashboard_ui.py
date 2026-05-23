import pytest
from unittest.mock import MagicMock
from ui.components import NoScrollComboBox

def test_no_scroll_combobox_ignores_wheel_event():
    """
    Kullanıcının yanlışlıkla fare tekerleği ile mikrofon değiştirmesini önleyen
    NoScrollComboBox sınıfının tekerlek hareketini (wheel event) yuttuğunu doğrular.
    """
    combo = NoScrollComboBox()
    mock_event = MagicMock()
    
    combo.wheelEvent(mock_event)
    
    # QWheelEvent geldiğinde event.ignore() çağrılmış olmalı
    mock_event.ignore.assert_called_once()