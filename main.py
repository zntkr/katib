import sys
import os
import io
import typing
import logging
from logging.handlers import RotatingFileHandler
import traceback
import pprint
from pathlib import Path
from PySide6.QtWidgets import QApplication
from core.settings import (
    APP_NAME, MSG_MODEL_NOT_FOUND, MSG_MIC_UNAVAILABLE,
    STATE_RECORDING, STATE_PROCESSING, STATE_LISTENING, STATE_READY,
)
import PySide6.QtSvg  # Svg plugin kaydı için gerekli
import warnings
import signal

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"  # Symlink uyarısını gizle
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"     # Konsol olmadığı için tqdm çökmelerini engelle
os.environ["CT2_VERBOSE"] = "-3"                     # CTranslate2 (C++) donanım uyarılarını tamamen kapat
warnings.filterwarnings("ignore", category=UserWarning) # Python (Whisper) uyarılarını yoksay

# ── Loglama Sistemi (Sektör Standardı) ────────────────────────────────
class StreamToLogger(io.TextIOBase):
    """Konsol çıktılarını (print, tqdm, kütüphane hataları) log dosyasına yönlendirir."""
    def __init__(self, logger: logging.Logger, level: int):
        super().__init__()
        self.logger = logger
        self.level = level

    def write(self, buf: str) -> int:
        for line in buf.rstrip().splitlines():
            if line.strip():
                self.logger.log(self.level, line.strip())
        return len(buf)

    def flush(self):
        pass

def setup_logging():
    local_app_data = os.environ.get("LOCALAPPDATA")
    base_dir = Path(local_app_data) if local_app_data else Path.home()
    log_dir = base_dir / APP_NAME / "Logs"
    log_file = log_dir / "katib.log"

    # Görev 3: Klasör oluşturma işlemi sıkı sistem iznine takılırsa uygulamanın Fatal Error verip çökmesini önlüyoruz.
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        
        handlers_list: list[logging.Handler] = [RotatingFileHandler(str(log_file), maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')]
        if sys.stdout is not None:
            handlers_list.append(logging.StreamHandler(sys.stdout))
            
        logging.basicConfig(
            handlers=handlers_list,
            level=logging.INFO,
            format="%(asctime)s.%(msecs)03d | %(levelname)-8s | PID:%(process)-5d | %(threadName)-22s | %(filename)s:%(lineno)-4d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    except Exception:
        # Dosya sistemine yazılmazsa fallback olarak basit (sadece stream) loglama konfigürasyonu
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    logger = logging.getLogger(APP_NAME)

    # --noconsole modunda stdout/stderr None olur. Kütüphanelerin write()
    # ile çökmelerini önlemek ve gizli hataları kaydetmek için devnull yerine logger'a bağlıyoruz.
    if sys.stdout is None:
        sys.stdout = typing.cast(typing.TextIO, StreamToLogger(logger, logging.INFO))
    if sys.stderr is None:
        sys.stderr = typing.cast(typing.TextIO, StreamToLogger(logger, logging.ERROR))

    # Yakalanamayan (unhandled) hataları global olarak logla
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            logger.info("Terminalden kesinti (KeyboardInterrupt) alındı.")
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        # Standart traceback metnini oluştur
        exception_list = traceback.format_exception(exc_type, exc_value, exc_traceback)
        exception_text = "".join(exception_list)

        # Log mesajına yerel değişkenleri ekle
        log_message = [
            "Yakalanamayan Hata (Unhandled Exception):\n",
            exception_text,
            "\n" + "="*20 + " YEREL DEĞİŞKENLER (LOCALS) " + "="*20 + "\n"
        ]

        tb = exc_traceback
        while tb is not None:
            frame = tb.tb_frame
            log_message.append(
                f"\n--- Dosya: {frame.f_code.co_filename}, Satır: {frame.f_lineno}, Fonksiyon: {frame.f_code.co_name} ---\n"
            )
            try:
                # pprint ile daha okunaklı hale getir, derinliği ve toplam boyutu limitle
                locals_str = pprint.pformat(frame.f_locals, indent=2, width=120, depth=3, compact=True)
                if len(locals_str) > 4096:
                    locals_str = locals_str[:4096] + "\n... (içerik çok uzun olduğu için kesildi)"
                log_message.append(locals_str)
            except Exception as e:
                log_message.append(f"<Yerel değişkenler okunurken hata: {e}>")
            
            log_message.append("\n")
            tb = tb.tb_next

        logger.error("".join(log_message))

    sys.excepthook = handle_exception
    return logger

global_logger = setup_logging()
global_logger.info("=== Katib Starting ===")

# ── QApplication ilk ve tek satırda yaratılır ──────────────────────────────
# Qt nesneleri (QPixmap, QIcon, QWidget vb.) ancak bundan SONRA var olabilir.
# Bu yüzden diğer tüm import'lar QApplication'dan SONRA gelir.


def _sigint_handler(signum, frame):
    global_logger.info("Terminalden kesinti (SIGINT) alındı, kapanıyor...")
    app = QApplication.instance()
    if app:
        app.quit()
    else:
        sys.exit(0)

def main():
    signal.signal(signal.SIGINT, _sigint_handler)
    # ── Tek örnek kilidi (Cross-Platform) ──────────────────────────────────
    # İkinci başlatma girişimini sessizce engeller; QSharedMemory süreç boyunca yaşar.
    from PySide6.QtCore import QSharedMemory
    _shared_memory = QSharedMemory("Katib_SingleInstance_Mutex")
    if not _shared_memory.create(1):
        global_logger.warning("Uygulama zaten çalışıyor. İkinci başlatma girişimi engellendi.")
        sys.exit(0)

    global_logger.info("QApplication başlatılıyor...")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Fusion stili bazen CSS renklerini ezebiliyor; devre dışı bırakıyoruz.

    # YENİ MİMARİ: Theme Manager'ı çağırıp tüm sistemi tek satırda boyuyoruz
    from ui.theme import theme_manager
    from core.settings import SettingsManager

    settings_manager = SettingsManager()
    from core.i18n import set_language as _i18n_set_language, t as _t, available_languages
    _lang = settings_manager.get("app_language") or ""
    if not _lang:
        import locale
        try:
            _sys_code = (locale.getdefaultlocale()[0] or "")[:2]
        except Exception:
            _sys_code = ""
        _available = {code for _, code in available_languages()}
        _lang = _sys_code if _sys_code in _available else "en"
        settings_manager.set("app_language", _lang)
    _i18n_set_language(_lang)
    for _k in (MSG_MODEL_NOT_FOUND, MSG_MIC_UNAVAILABLE,
               STATE_RECORDING, STATE_PROCESSING, STATE_LISTENING, STATE_READY):
        if _t(_k) == _k:
            global_logger.warning("i18n: STATUS key missing in catalog: '%s'", _k)
    theme_manager.apply_theme(app)
    global_logger.info("Tema ve ayarlar yüklendi.")

    # Qt ortamı hazır — sadece UI modülünü içe aktar.
    # Worker'lar event loop başladıktan sonra (deferred) import edilir.
    from ui.tray_app import TrayApp

    global_logger.info("Arayüz (Tray/Dashboard) oluşturuluyor...")
    tray = TrayApp(settings=settings_manager)
    app.setWindowIcon(tray._icon_idle)

    # ── Ertelenmiş başlatma ───────────────────────────────────────────────
    # show() kasıtlı olarak _deferred_init'in SONUNDA çağrılır.
    # Tüm ağır import'lar bitmeden show() çağrılırsa main thread bloke olur;
    # DWM'nin ilk beyaz frame'i WM_PAINT işlenene kadar ekranda kalır (flash).

    _workers = {}

    def _deferred_init():
        global_logger.info("Arka plan işlemleri (Deferred Init) başlatılıyor...")
        from workers.hotkey_worker import HotkeyWorker
        from workers.audio_worker import AudioWorker
        from workers.transcription_worker import TranscriptionWorker
        from workers.model_downloader_worker import ModelDownloaderWorker
        from ui.osd import MinimalOSD

        global_logger.info("Worker nesneleri oluşturuluyor...")
        hotkey_worker        = HotkeyWorker(settings=settings_manager, key=settings_manager.get("hotkey", "F9"))
        audio_worker         = AudioWorker(settings=settings_manager)
        transcription_worker = TranscriptionWorker(settings=settings_manager)
        downloader_worker    = ModelDownloaderWorker(settings=settings_manager)
        osd                  = MinimalOSD()

        _workers.update(hw=hotkey_worker, aw=audio_worker,
                        tw=transcription_worker, dw=downloader_worker)

        # Görev 1: TrayApp'e worker referanslarını veriyoruz. Böylece sinyaller çalışırken
        # UI manipülasyonları QObject üzerinden QueuedConnection ile güvenli Main Thread'e yönelecek.
        tray.transcription_worker = transcription_worker
        tray.audio_worker = audio_worker
        tray.osd = osd

        # ---------------------------------------------------- signal wiring
        global_logger.info("Sinyal kablolaması (Wiring) yapılıyor...")

        # 1 & 2) Tuşa basıldı/bırakıldı → Doğrudan TrayApp QObject slotlarını tetikler (Thread-Safe)
        hotkey_worker.hotkey_pressed.connect(tray.on_hotkey_pressed)
        hotkey_worker.hotkey_released.connect(tray.on_hotkey_released)

        # OSD Bağlantıları (Tek Operasyonel Görünürlük Kanalı)
        # setStateRecording artık on_hotkey_pressed içinden çağrılıyor (model guard sonrası)
        audio_worker.audio_failed.connect(osd.hide_osd)
        transcription_worker.transcription_started.connect(osd.setStateProcessing)
        transcription_worker.transcription_finished.connect(osd.hide_osd)

        # Mikrofon donanım hatası → Dashboard kalıcı durum + OSD geçici hata
        audio_worker.mic_unavailable.connect(tray.on_mic_unavailable)

        # Tüm worker hataları → OSD + tray balonu
        audio_worker.error_occurred.connect(lambda msg: osd.setStateError(msg))
        hotkey_worker.error_occurred.connect(lambda msg: osd.setStateError(msg))
        transcription_worker.error_occurred.connect(lambda msg: osd.setStateError(msg))
        transcription_worker.model_missing.connect(lambda: osd.setStateError(MSG_MODEL_NOT_FOUND))
        transcription_worker.model_missing.connect(tray.dashboard.show_model_missing_guidance)
        transcription_worker.model_loaded.connect(tray.dashboard.clear_model_missing_guidance)
        downloader_worker.error_occurred.connect(lambda msg: osd.setStateError(msg))

        # 3) Ham ses hazır → çeviri kuyruğuna ekle
        audio_worker.audio_ready.connect(transcription_worker.add_audio)

        # 4) Çeviri tamamlandı → Main thread'de (TrayApp slot'u üzerinden) metni fırlat
        transcription_worker.text_ready.connect(tray.on_text_ready)

        # 5) Ses seviyesi → progress bar
        audio_worker.level_changed.connect(tray.dashboard.update_level)
        transcription_worker.status_changed.connect(tray.dashboard.set_status)
        transcription_worker.loading_state_changed.connect(tray.dashboard.set_loading_indicator)

        # 6) Log mesajları → dashboard
        audio_worker.log_entry.connect(tray.dashboard.append_log_entry)
        transcription_worker.log_entry.connect(tray.dashboard.append_log_entry)
        hotkey_worker.log_entry.connect(tray.dashboard.append_log_entry)

        # UI loglarını da endüstri standardı olan disk loguna köprüle
        def _file_log_bridge(lvl, cat, msg):
            log_str = f"[{cat}] {msg}"
            if lvl in ("ERR", "WRN"):
                global_logger.error(log_str)
            else:
                global_logger.info(log_str)

        audio_worker.log_entry.connect(_file_log_bridge)
        transcription_worker.log_entry.connect(_file_log_bridge)
        hotkey_worker.log_entry.connect(_file_log_bridge)
        downloader_worker.log_entry.connect(_file_log_bridge)

        # WRN logları → OSD (3 sn, kullanıcıya anlamlı kategoriler)
        _OSD_WRN_CATS = {"MIC", "STT", "KEY"}
        def _wrn_to_osd(lvl, cat, msg):
            if lvl == "WRN" and cat in _OSD_WRN_CATS:
                osd.setStateError(msg)

        audio_worker.log_entry.connect(_wrn_to_osd)
        transcription_worker.log_entry.connect(_wrn_to_osd)
        hotkey_worker.log_entry.connect(_wrn_to_osd)


        # 8) Mikrofon değişimi → audio worker + hata bayrağını sıfırla
        tray.dashboard.device_changed.connect(audio_worker.set_device)
        tray.dashboard.device_changed.connect(lambda _: tray.on_mic_available())

        # 9) Kısayol değişimi → hotkey worker
        tray.dashboard.hotkey_changed.connect(hotkey_worker.set_key)
        # Kısayol yakalama modunda hotkey worker duraklatılır → yanlış tıkta kayıt tetiklenmez
        tray.dashboard.hotkey_capture_mode.connect(
            lambda capturing: hotkey_worker.pause() if capturing else hotkey_worker.resume()
        )

        # 10) Model klasörü veya hesaplama ayarı değişimi → transcription worker modeli baştan yükler
        tray.dashboard.model_dir_changed.connect(transcription_worker.reload_model)
        tray.dashboard.model_reload_requested.connect(transcription_worker.reload_model)

        # 11) Cihaz listesi: UI ister → AudioWorker sorgular → UI doldurur
        tray.dashboard.refresh_devices_requested.connect(audio_worker.refresh_devices)
        audio_worker.devices_ready.connect(tray.dashboard.populate_devices)
        audio_worker.refresh_devices()   # başlangıçta combo'yu doldur
        # dashboard.populate_devices seçilen mikrofonu bulup device_changed sinyaliyle set_device çağırır.

        # 13) Model indirici: UI → downloader → dashboard + transcription
        tray.dashboard.download_model_requested.connect(downloader_worker.start_download)
        downloader_worker.log_entry.connect(tray.dashboard.append_log_entry)
        downloader_worker.error_occurred.connect(lambda _: tray.dashboard.set_loading_indicator(False))
        downloader_worker.error_occurred.connect(lambda _: tray.dashboard.set_download_state(False))
        downloader_worker.status_changed.connect(tray.dashboard.set_status)
        downloader_worker.download_state_changed.connect(tray.dashboard.set_download_state)
        downloader_worker.download_finished.connect(tray.dashboard.on_download_complete)

        # ---------------------------------------------------- start workers
        global_logger.info("Worker thread'leri başlatılıyor...")
        transcription_worker.start()
        audio_worker.start()
        hotkey_worker.start()

        tray.dashboard.show()
        tray.dashboard.raise_()
        tray.dashboard.append_log_entry("OK", "APP", _t("app.started").format(key=settings_manager.get('hotkey', 'F9').upper()))
        global_logger.info("Sistem hazır ve dinlemede.")

    # ----------------------------------------------------- graceful shutdown
    def shutdown():
        global_logger.info("=== Kapanış (Shutdown) Başlatıldı ===")
        tray.dashboard.append_log_entry("...", "APP", _t("app.shutting_down"))
        
        # Event loop bittikten sonra C++ tarafında çizim (QBackingStore) hatalarını önlemek için pencereleri gizle
        for window in QApplication.topLevelWidgets():
            window.hide()
        if hasattr(tray, 'tray'):
            tray.tray.hide()

        # Arayüzü dondurmamak ve GIL Deadlock riskini sıfırlamak için
        # iş parçacıklarına sadece yumuşak dur sinyali gönderiyoruz (wait yok).
        if 'hw' in _workers:
            global_logger.info("Arka plan Worker thread'leri durduruluyor...")
            _workers['hw'].stop()
            _workers['aw'].stop()
            _workers['tw'].stop()
            

    app.aboutToQuit.connect(shutdown)

    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, _deferred_init)

    # C++ Event Loop'un (app.exec) Python sinyallerini (Ctrl+C) bloke etmesini
    # önlemek için Python yorumlayıcısını periyodik olarak uyandıran dummy timer.
    signal_timer = QTimer()
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start(500)

    app.exec()

    # Event loop (app.exec) bittikten sonra QTimer çalışmaz. 
    # Worker'ların kapanması için gereken 250ms gecikmeyi burada veriyoruz.
    # C++ seviyesinde çalışan QThread'leri Python içinde beklemek (wait) veya
    # zorla öldürmek (terminate) kalıcı donmalara yol açtığı için 
    # işlemi İşletim Sistemi seviyesinde (OS level) anında sonlandırıyoruz.
    import time
    time.sleep(0.25)
    global_logger.info("Sistem temiz şekilde kapatıldı (os._exit).")
    logging.shutdown()
    os._exit(0)


if __name__ == "__main__":
    main()
