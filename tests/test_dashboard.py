import pytest
from unittest.mock import MagicMock, call
from ui.dashboard import DashboardWindow

@pytest.fixture
def mock_dashboard():
    """DashboardWindow için izole bir sahte (mock) nesne oluşturur."""
    dashboard = MagicMock(spec=DashboardWindow)
    dashboard.mic_combo = MagicMock()
    dashboard.settings = MagicMock()
    dashboard.device_changed = MagicMock()
    dashboard.append_log_entry = MagicMock()
    return dashboard

def test_device_changed_selects_default(mock_dashboard):
    """Kullanıcı '(Varsayılan)' etiketli bir cihaz seçtiğinde takibe dönüldüğünü test eder."""
    mock_dashboard.mic_combo.itemData.return_value = 1
    mock_dashboard.mic_combo.itemText.return_value = "Logitech Mic (Varsayılan)"

    DashboardWindow._on_device_changed(mock_dashboard, 0)

    mock_dashboard.settings.set.assert_has_calls([
        call("device_index", -1),
        call("device_name", "")
    ])
    mock_dashboard.append_log_entry.assert_called_with("...", "MIC", "Dinamik varsayılan izleme moduna geçildi.")
    mock_dashboard.device_changed.emit.assert_called_once_with(1)

def test_device_changed_selects_specific_device(mock_dashboard):
    """Kullanıcı belirli bir cihaza tıkladığında cihazın mühürlendiğini test eder."""
    mock_dashboard.mic_combo.itemData.return_value = 2
    mock_dashboard.mic_combo.itemText.return_value = "Realtek Mic"

    DashboardWindow._on_device_changed(mock_dashboard, 1)

    mock_dashboard.settings.set.assert_has_calls([
        call("device_index", 2),
        call("device_name", "Realtek Mic")
    ])
    mock_dashboard.append_log_entry.assert_called_with("...", "MIC", "Mikrofon sabitlendi: Realtek Mic")
    mock_dashboard.device_changed.emit.assert_called_once_with(2)

def test_device_changed_none_data(mock_dashboard):
    """Geçersiz bir öğe (None data) seçildiğinde hiçbir işlemin yapılmadığını test eder."""
    mock_dashboard.mic_combo.itemData.return_value = None
    
    DashboardWindow._on_device_changed(mock_dashboard, 2)
    
    mock_dashboard.settings.set.assert_not_called()
    mock_dashboard.device_changed.emit.assert_not_called()