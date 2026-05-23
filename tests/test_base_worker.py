"""
BaseWorker ve measure_time dekoratör testleri.
Zaman ölçümleri deterministik (kesin) olması için time.perf_counter mock'lanır.
"""
import pytest
from unittest.mock import patch
from PySide6.QtCore import QObject, Signal
from workers.base_worker import measure_time, BaseWorker


class DummyWorker(QObject):
    """measure_time dekoratörünü test etmek için sahte (dummy) worker sınıfı."""
    log_entry = Signal(str, str, str)

    @measure_time("TST", "Örnek İşlem")
    def do_work(self, return_value="Başarılı"):
        return return_value
        
    @measure_time("TST", "Hatalı İşlem")
    def crash_work(self):
        raise ValueError("Simüle edilmiş hata")


class TestMeasureTimeDecorator:
    
    def test_emits_prf_log_with_correct_format(self, qapp):
        worker = DummyWorker()
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        
        worker.do_work()
        
        assert len(logs) == 1
        level, component, message = logs[0]
        assert level == "OK"
        assert component == "TST"
        assert "[Örnek İşlem] completed:" in message

    def test_measures_elapsed_time_accurately(self, qapp):
        worker = DummyWorker()
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append((l, c, m)))
        
        # time.perf_counter() fonksiyonunu ardışık çağrılarda 1.000 ve 1.150 dönecek
        # şekilde mock'luyoruz (tam olarak 150ms geçmiş gibi simüle ediyoruz).
        with patch("workers.base_worker.time.perf_counter", side_effect=[1.000, 1.150]):
            worker.do_work()
            
        message = logs[0][2]
        # "150.0 ms" metninin loglandığından emin oluyoruz
        assert "150.0 ms" in message

    def test_preserves_function_return_value(self, qapp):
        worker = DummyWorker()
        
        # Dekoratörün asıl fonksiyonun dönüş değerini (return) yutmadığını doğrula
        result = worker.do_work(return_value="Beklenen Veri")
        assert result == "Beklenen Veri"

    def test_emits_time_even_on_exception(self, qapp):
        worker = DummyWorker()
        logs = []
        worker.log_entry.connect(lambda l, c, m: logs.append(m))
        
        # Fonksiyon exception (hata) fırlatsa bile finally bloğu sayesinde sürenin loglanması testi
        with patch("workers.base_worker.time.perf_counter", side_effect=[2.000, 2.050]):
            with pytest.raises(ValueError, match="Simüle edilmiş hata"):
                worker.crash_work()
                
        # Exception try-except'ten kaçsa bile log emitlenmiş olmalı
        assert len(logs) == 1
        assert "50.0 ms" in logs[0]