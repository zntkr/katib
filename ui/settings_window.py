"""The one window Katib has (ADR-0012): what affects dictation on the first tab, with live
facts about the last recording and the model; app preferences; the live log.
Each tab is built by hand in its own _build_*_tab method; there is no generator."""
import html
import os
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget, QFrame,
    QFileDialog, QMessageBox, QTextEdit, QTextBrowser, QProgressBar, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QTimer, QDateTime
from PySide6.QtGui import QColor, QFont, QIcon, QKeyEvent, QPainter, QPaintEvent

from core.i18n import t, available_languages
from core.log import get_logger, OK
from core.settings import (
    APP_NAME, WHISPER_MODELS, DEFAULT_DOWNLOAD_PARENT, format_size,
    INJECTION_METHODS, SPEECH_LANGUAGES, DEFAULT_PROMPTS, get_log_dir,
)
from ui.components import NoScrollComboBox, DynamicIconButton
from ui.icons import ICN_TICK
from ui.theme import G_1, G_2, G_4, G_6, FONT_SIZE_SM, SETTINGS_WIDTH, SETTINGS_HEIGHT, theme_manager
from ui.utils import qt_key_to_keyboard
from ui.utils_win import apply_dark_mode_to_window

_log = get_logger("APP")
_log_mic = get_logger("MIC")

TABS = ("dictation", "app", "log")
LOG_LIMIT = 100

# Tags the log view receives (core.log) and the palette colour each one gets.
_LOG_COLOUR = {"OK": "CLR_OK", "ERR": "CLR_ERR", "WRN": "CLR_WARN", "...": "CLR_INFO"}
_LOG_LABEL = {"...": "INFO"}

# Model list entries that are not a known repository.
_BROWSE = "browse_custom"   # the "Browse..." action row
_CUSTOM = "custom:"         # prefix of a folder the user picked: "custom:<path>"


def _download_text(done: float, total: float, speed: float) -> str:
    """"1.3 / 3.1 GB · 6.1 MB/s". Decimal units, as the model list and the download site use;
    they read the same in every language, so there is no translation key."""
    if total >= 1e9:
        amount = f"{done / 1e9:.1f} / {format_size(total)}"
    else:
        amount = f"{done / 1e6:.0f} / {format_size(total)}"
    return f"{amount} · {speed / 1e6:.1f} MB/s"


class SettingsWindow(QWidget):
    device_changed            = Signal(int)
    hotkey_changed            = Signal(str)
    hotkey_capture_mode       = Signal(bool)  # True while the window waits for the new hotkey
    model_dir_changed         = Signal(str)
    download_model_requested  = Signal(str, str)
    language_change_requested = Signal(str)
    help_requested            = Signal()

    def __init__(self, settings, model_provider, icon: QIcon, parent: QWidget | None = None):
        flags = (
            Qt.WindowType.Window |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        super().__init__(parent, flags)
        self.setObjectName("SettingsWindow")
        self.settings = settings
        self.model_provider = model_provider
        self.setWindowIcon(icon)
        self.setFixedSize(SETTINGS_WIDTH, SETTINGS_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # White-flash prevention: DWM starts the buffer transparent and paintEvent fills it,
        # so the user never sees a white window before the first paint.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._capturing_hotkey = False
        self._placed = False                       # centred on the screen on first show
        self._tray_available = True
        self._last_model_index = 0
        # What the workers reported last; kept here so a rebuild can show it again.
        self._devices: list | None = None          # AudioWorker.devices_ready
        self._log_entries: list[tuple[str, str, str, str, str]] = []
        self._last_recording: tuple[float, float, float, str] | None = None
        self._model_info: tuple[str, str, str] | None = None
        self._last_dictation: tuple[float, float] | None = None
        self._downloading_repo: str | None = None  # the download this window asked for
        self._download_text: str | None = None     # ModelDownloaderWorker.download_progress

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(G_1, G_1, G_1, G_1)
        self._build_tabs()

    # ------------------------------------------------------------------ build
    def _build_tabs(self) -> None:
        self.setWindowTitle(f"{APP_NAME} - {t('settings.title')}")
        self.tabs = QTabWidget()
        builders = {
            "dictation": ("settings.tab_dictation", self._build_dictation_tab),
            "app": ("settings.tab_app", self._build_app_tab),
            "log": ("settings.group_log", self._build_log_tab),
        }
        for name in TABS:
            title_key, build = builders[name]
            self.tabs.addTab(build(), t(title_key))
        self._outer.addWidget(self.tabs)

    @staticmethod
    def _column() -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(G_1)
        return layout

    @staticmethod
    def _combo(choices) -> NoScrollComboBox:
        combo = NoScrollComboBox()
        for label, value in choices:
            combo.addItem(label, userData=value)
        return combo

    @staticmethod
    def _info_label() -> QLabel:
        """Small muted text for live facts; selectable so it can be copied into a bug report."""
        label = QLabel()
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setMinimumWidth(10)
        label.setStyleSheet(f"color: {theme_manager.palette['CLR_TEXT_MUTED']}; font-size: {FONT_SIZE_SM}pt;")
        return label

    def _build_dictation_tab(self) -> QWidget:
        """Everything that affects a dictation: what is heard (left) and what transcribes it (right)."""
        tab = QWidget()
        columns = QHBoxLayout(tab)
        columns.setContentsMargins(G_2, G_2, G_2, G_2)
        columns.setSpacing(G_2)
        columns.addLayout(self._build_voice_column(), 1)
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet(f"background-color: {theme_manager.palette['CLR_BORDER_LIGHT']}; border: none;")
        columns.addWidget(divider)
        columns.addLayout(self._build_model_column(), 1)
        return tab

    def _build_voice_column(self) -> QVBoxLayout:
        layout = self._column()

        self.btn_hotkey = QPushButton()
        self.btn_hotkey.setProperty("isIconBtn", True)
        self.btn_hotkey.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hotkey.setFixedHeight(G_4)
        self.btn_hotkey.setMinimumWidth(G_4)
        self.btn_hotkey.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.btn_hotkey.clicked.connect(self._start_hotkey_capture)
        hotkey_row = QHBoxLayout()
        hotkey_row.addWidget(QLabel(t("settings.hotkey_label")), 1)
        hotkey_row.addWidget(self.btn_hotkey)
        layout.addLayout(hotkey_row)

        self.speech_language_combo = self._combo(SPEECH_LANGUAGES)
        self.speech_language_combo.currentIndexChanged.connect(self._on_speech_language_changed)
        layout.addWidget(QLabel(t("settings.speech_language_label")))
        layout.addWidget(self.speech_language_combo)

        self.mic_combo = NoScrollComboBox()
        self.mic_combo.currentIndexChanged.connect(self._on_device_changed)
        layout.addWidget(QLabel(t("settings.microphone_label")))
        layout.addWidget(self.mic_combo)

        # Input level of the current dictation; flat when nothing is being recorded.
        self.level_bar = QProgressBar()
        self.level_bar.setObjectName("level_bar")
        self.level_bar.setRange(0, 100)
        self.level_bar.setTextVisible(False)
        self.level_bar.setFixedHeight(8)
        self._level_colour: str | None = None
        layout.addWidget(self.level_bar)

        self.lbl_recording = self._info_label()
        layout.addWidget(self.lbl_recording)
        self._render_recording_info()
        layout.addStretch(1)
        return layout

    def _build_model_column(self) -> QVBoxLayout:
        layout = self._column()
        p = theme_manager.palette

        # One list, one job: closed, it names the model in use (or asks for one). Each row says
        # its state; _refresh_model_rows writes the texts. There is no download button: picking
        # a model that is not installed asks to download it (CONTEXT.md, anti-pattern 8).
        self.model_combo = NoScrollComboBox()
        self.model_combo.setPlaceholderText(t("settings.model_pick"))
        self._models: dict[str, tuple[str, int]] = {}   # repo id -> (name, bytes to download)
        for key, info in WHISPER_MODELS.items():
            self._models[info["repo_id"]] = (key.capitalize(), info["bytes"])
            self.model_combo.addItem(key.capitalize(), userData=info["repo_id"])
        self.model_combo.addItem(t("settings.browse"), userData=_BROWSE)
        italic = QFont()
        italic.setItalic(True)
        self.model_combo.setItemData(self.model_combo.count() - 1, italic, Qt.ItemDataRole.FontRole)
        self.model_combo.currentIndexChanged.connect(self._on_model_index_changed)

        layout.addWidget(QLabel(t("settings.ai_model_label")))
        layout.addWidget(self.model_combo)

        # Busy while a model is loading or downloading.
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setFixedHeight(8)
        self.loading_bar.hide()
        layout.addWidget(self.loading_bar)

        self.lbl_model_info = self._info_label()
        layout.addWidget(self.lbl_model_info)
        self._render_model_info()

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMinimumHeight(G_6)
        self.prompt_edit.setAcceptRichText(False)
        self.prompt_edit.setToolTip(t("settings.ai_prompt_tooltip"))
        self.prompt_edit.textChanged.connect(self._on_prompt_edited)
        self.btn_save_prompt = DynamicIconButton(ICN_TICK, p["CLR_ACCENT"])
        self.btn_save_prompt.setEnabled(False)
        self.btn_save_prompt.clicked.connect(self._save_prompt)
        prompt_row = QHBoxLayout()
        prompt_row.setSpacing(G_1)
        prompt_row.addWidget(self.prompt_edit)
        prompt_row.addWidget(self.btn_save_prompt, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(QLabel(t("settings.ai_prompt_label")))
        layout.addLayout(prompt_row, 1)
        return layout

    def _build_app_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(G_2, G_2, G_2, G_2)
        layout.setSpacing(G_1)

        self.app_language_combo = self._combo(available_languages())
        self.app_language_combo.currentIndexChanged.connect(self._on_app_language_changed)
        self.injection_combo = self._combo(INJECTION_METHODS)
        self.injection_combo.currentIndexChanged.connect(
            lambda _idx: self.settings.set("injection_method", self.injection_combo.currentData())
        )
        for label_key, combo in (
            ("settings.app_language_label", self.app_language_combo),
            ("settings.injection_method_label", self.injection_combo),
        ):
            row = QHBoxLayout()
            row.setSpacing(G_2)
            row.addWidget(QLabel(t(label_key)), 1)
            row.addWidget(combo, 1)
            layout.addLayout(row)

        layout.addStretch(1)
        buttons = QHBoxLayout()
        buttons.setSpacing(G_1)
        btn_help = QPushButton(t("settings.user_guide"))
        btn_help.clicked.connect(self.help_requested)
        buttons.addWidget(btn_help)
        # Shown only when Windows offers no tray: then this window is the only place to quit from.
        self.btn_quit = QPushButton(t("tray.menu.quit"))
        app = QApplication.instance()
        if app:
            self.btn_quit.clicked.connect(app.quit)
        self.btn_quit.setVisible(not self._tray_available)
        buttons.addWidget(self.btn_quit)
        layout.addLayout(buttons)
        return tab

    def _build_log_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(G_1, G_1, G_1, G_1)
        layout.setSpacing(G_1)
        self.log_box = QTextBrowser()
        self.log_box.setObjectName("log_box")
        self.log_box.setOpenExternalLinks(False)
        self.log_box.setFont(QFont("Consolas", FONT_SIZE_SM))
        self.log_box.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.log_box.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        self.log_box.document().setMaximumBlockCount(LOG_LIMIT)
        layout.addWidget(self.log_box, 1)

        btn_logs = QPushButton(t("settings.open_log_folder"))
        btn_logs.clicked.connect(self._open_log_folder)
        layout.addWidget(btn_logs)
        self._render_log()
        return tab

    # ---------------------------------------------------------- window events
    def paintEvent(self, event: QPaintEvent) -> None:
        """Fills the window background: WA_TranslucentBackground keeps QSS from reaching it."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme_manager.palette["CLR_BG_DEEP"]))
        painter.end()
        super().paintEvent(event)

    def show(self) -> None:
        self._refresh_values()
        try:
            apply_dark_mode_to_window(int(self.winId()))
        except Exception:
            pass
        if not self._placed:
            self._placed = True
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.center().x() - self.width() // 2, screen.center().y() - self.height() // 2)
        super().show()
        self.raise_()
        self.activateWindow()

    def show_tab(self, name: str) -> None:
        self.tabs.setCurrentIndex(TABS.index(name))

    def set_tray_available(self, available: bool) -> None:
        """Without a tray icon this window is the only way to quit, so it offers a Quit button."""
        self._tray_available = available
        self.btn_quit.setVisible(not available)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._capturing_hotkey:
            if event.key() == Qt.Key.Key_Escape:
                self._end_hotkey_capture(self.settings.get("hotkey", "F9"))
                return
            key_name = qt_key_to_keyboard(event.key())
            if not key_name:
                return  # a bare modifier: keep waiting for the key itself
            parts = [name for modifier, name in (
                (Qt.KeyboardModifier.ControlModifier, "ctrl"),
                (Qt.KeyboardModifier.ShiftModifier, "shift"),
                (Qt.KeyboardModifier.AltModifier, "alt"),
            ) if event.modifiers() & modifier]
            new_key = "+".join(parts + [key_name])
            self.settings.set("hotkey", new_key)
            self.hotkey_changed.emit(new_key)
            self._end_hotkey_capture(new_key)
            return
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        for timer in self.findChildren(QTimer):
            if timer.isActive():
                timer.stop()
        super().closeEvent(event)

    def rebuild(self) -> None:
        """Builds the tabs again in the current language. The window object stays,
        so every signal wired in main.py stays connected."""
        if self._capturing_hotkey:
            self._end_hotkey_capture(self.settings.get("hotkey", "F9"))
        current = self.tabs.currentIndex()
        self._outer.removeWidget(self.tabs)
        self.tabs.hide()
        self.tabs.deleteLater()  # deferred: the widget that asked for the rebuild is inside it
        self._build_tabs()
        self.tabs.setCurrentIndex(current)
        self._refresh_values()
        self._fill_mic_combo(self._devices or [])

    # ------------------------------------------------------------------ voice
    def _start_hotkey_capture(self) -> None:
        self._capturing_hotkey = True
        self.btn_hotkey.setText(t("settings.hotkey_capture"))
        colour = theme_manager.palette["CLR_INFO"]
        self.btn_hotkey.setStyleSheet(f"border-color: {colour}; color: {colour}; font-weight: bold;")
        self.setFocus()
        self.hotkey_capture_mode.emit(True)

    def _end_hotkey_capture(self, key: str) -> None:
        self._capturing_hotkey = False
        self.btn_hotkey.setText(key.upper())
        self.btn_hotkey.setStyleSheet("")
        self.hotkey_capture_mode.emit(False)

    def _on_speech_language_changed(self, _idx: int) -> None:
        language = self.speech_language_combo.currentData()
        self.settings.set("language", language)
        self._load_prompt_for_language(language)

    def populate_devices(self, items: list[tuple[str, int, bool]]) -> None:
        """AudioWorker.devices_ready: shows the list and reports which microphone is in use."""
        if self._devices == items:
            return
        self._devices = items
        selected = self._fill_mic_combo(items)
        if not items:
            self.append_log_entry("WRN", "MIC", "", "settings.no_mic_found")
        elif selected is not None:
            index, name, reason = selected
            _log_mic.info(f"Auto-selected: {name} ({reason})")
            # The choice is not saved here; only the user picking a device saves it.
            self.device_changed.emit(index)

    def _fill_mic_combo(self, items) -> tuple[int, str, str] | None:
        """Fills the list and selects the saved microphone, else the system default, else the
        first one. Returns (device index, name, why it was chosen); None when there is none."""
        combo = self.mic_combo
        saved_index = self.settings.get("device_index")
        saved_name = self.settings.get("device_name")
        preferred = default = -1
        combo.blockSignals(True)
        combo.clear()
        for row, (label, index, is_default) in enumerate(items):
            # Some Windows driver names carry stray line breaks.
            label = label.replace("\r", "").replace("\n", " ").strip()
            combo.addItem(label, userData=index)
            if saved_name:
                if label.replace(" (Default)", "") == saved_name:
                    preferred = row
            elif index == saved_index:
                preferred = row
            if is_default:
                default = row
        chosen = preferred if preferred != -1 else default
        if chosen == -1 and items:
            chosen = 0
        combo.setCurrentIndex(chosen)
        combo.setPlaceholderText("" if items else t("settings.no_mic_found"))
        combo.setEnabled(bool(items))
        combo.blockSignals(False)
        if chosen == -1 or combo.itemData(chosen) is None:
            return None
        reason = "Saved Preference" if preferred != -1 else "System Default"
        return combo.itemData(chosen), combo.itemText(chosen).replace(" (Default)", ""), reason

    def _on_device_changed(self, row: int) -> None:
        index = self.mic_combo.itemData(row)
        if index is None:
            return
        text = self.mic_combo.itemText(row)
        if " (Default)" in text:
            # Picking the entry marked as default means "follow the system default" (ADR-0005).
            self.settings.set("device_index", -1)
            self.settings.set("device_name", "")
            _log_mic.info("Switched to dynamic default tracking.")
        else:
            name = text.replace(" (Default)", "")
            self.settings.set("device_index", index)
            self.settings.set("device_name", name)
            _log_mic.info(f"Microphone locked: {name}")
        self.device_changed.emit(index)

    def update_level(self, value: float) -> None:
        percent = max(0, min(100, int(value * 100)))
        self.level_bar.setValue(percent)
        p = theme_manager.palette
        if percent < 25:
            colour = p["CLR_INFO"]
        elif percent < 50:
            colour = p["CLR_OK"]
        elif percent < 75:
            colour = p["CLR_WARN"]
        else:
            colour = p["CLR_ERR"]
        # The global stylesheet cannot colour ::chunk by value, hence this inline override.
        if self._level_colour != colour:
            self._level_colour = colour
            self.level_bar.setStyleSheet(
                f"QProgressBar::chunk {{ background-color: {colour}; border-radius: 2px; }}"
            )

    def show_last_recording(self, seconds: float, speech_db: float, noise_db: float, problem: str) -> None:
        """AudioWorker.recording_analysed: how loud the last recording was and, when it was
        dropped, why (problem is the i18n key of the reason; "" when it went on)."""
        self._last_recording = (seconds, speech_db, noise_db, problem)
        self._render_recording_info()

    def _render_recording_info(self) -> None:
        if self._last_recording is None:
            self.lbl_recording.setText("")
            return
        seconds, speech_db, noise_db, problem = self._last_recording
        text = html.escape(t("settings.last_recording").format(
            seconds=f"{seconds:.1f}", speech=f"{speech_db:.0f}", noise=f"{noise_db:.0f}"))
        text = text.replace(" · ", "<br>", 1)  # the length on its own line, the two levels below
        if problem:
            colour = theme_manager.palette["CLR_WARN"]
            text += f"<br><span style='color:{colour}'>{html.escape(t(problem))}</span>"
        self.lbl_recording.setText(text)

    # ------------------------------------------------------------------ model
    def set_loading_indicator(self, visible: bool) -> None:
        self.loading_bar.setVisible(visible)

    def set_download_state(self, active: bool) -> None:
        """ModelDownloaderWorker.download_state_changed; False also when a download failed."""
        # Sliding until the first progress report, and again for the model load that follows.
        self.loading_bar.setRange(0, 0)
        self._download_text = None
        if not active:
            self._downloading_repo = None
        self.set_loading_indicator(active)
        self._refresh_model_rows()
        self._render_model_info()

    def show_download_progress(self, done: float, total: float, speed: float) -> None:
        """ModelDownloaderWorker.download_progress: fills the bar and says how much and how fast."""
        if self._downloading_repo is not None:
            # The size the row promised. The library learns the total file by file and never
            # counts the small text files (measured: 76 of the tiny model's 78 MB).
            total = self._models[self._downloading_repo][1]
        if total <= 0:
            return  # size not known: the bar keeps sliding
        done = min(done, total)
        self.loading_bar.setRange(0, 1000)
        self.loading_bar.setValue(int(done / total * 1000))
        self._download_text = _download_text(done, total, speed)
        self._render_model_info()

    def on_download_complete(self, model_dir: str) -> None:
        """The downloaded model becomes the one in use, now and after a restart."""
        self.settings.set("model_dir", model_dir)
        self.model_dir_changed.emit(model_dir)   # main.py tells the provider before the rows are read
        self._sync_model_combo(model_dir)

    def on_model_loaded(self, device: str, compute_type: str, gpu_note: str) -> None:
        """TranscriptionWorker.model_loaded: where the model runs; gpu_note says why not on the GPU."""
        self._model_info = (device, compute_type, gpu_note)
        self._last_dictation = None  # timed with the previous model
        self._refresh_model_rows()
        self._render_model_info()

    def show_last_dictation(self, audio_seconds: float, elapsed_seconds: float) -> None:
        """TranscriptionWorker.dictation_timed."""
        self._last_dictation = (audio_seconds, elapsed_seconds)
        self._render_model_info()

    def _render_model_info(self) -> None:
        lines = []
        # The download first: it is what the bar right above is about. The facts after it are
        # those of the model in use, and a GPU note there must not read as a download error.
        if self._downloading_repo is not None:
            line = f"{self._models[self._downloading_repo][0]} · {t('settings.model_downloading')}"
            if self._download_text is not None:
                line += f" · {self._download_text}"
            lines.append(html.escape(line))
        if self._model_info is not None:
            device, compute_type, gpu_note = self._model_info
            line = f"{'GPU' if device == 'cuda' else 'CPU'} · {compute_type}"
            if gpu_note:
                line += f" · {gpu_note}"
            lines.append(html.escape(line))
        if self._last_dictation is not None:
            audio, elapsed = self._last_dictation
            lines.append(html.escape(t("settings.last_dictation").format(
                audio=f"{audio:.1f}", elapsed=f"{elapsed:.1f}")))
        self.lbl_model_info.setText("<br>".join(lines))
        self.lbl_model_info.setToolTip(self.model_provider.get_active_model_path() or "")

    def show_model_missing_guidance(self) -> None:
        """No usable model: say so in the log and open the window where one can be chosen."""
        self.append_log_entry("...", "STT", "", "settings.model_missing_guidance")
        self.show_tab("dictation")
        self.show()
        QTimer.singleShot(50, self.model_combo, self.model_combo.setFocus)

    def _on_model_index_changed(self, row: int) -> None:
        data = self.model_combo.currentData()
        if data == _BROWSE:
            self._browse_model_dir()
            return
        target = self._selected_model_path()
        if target is None or self.model_provider.resolve_model_dir(str(target)) is None:
            # Not installed: the list goes back to the model in use and offers the download.
            self._revert_model_combo()
            if data in self._models:
                self._ask_to_download(data)
            return
        # A model that is already installed is applied as soon as it is picked.
        self._last_model_index = row
        if self.settings.get("model_dir") != str(target):
            self.settings.set("model_dir", str(target))
            self.model_dir_changed.emit(str(target))
            name = "Custom Folder" if str(data).startswith(_CUSTOM) else target.name
            _log.log(OK, f"Switched to model: {name}")
        self._refresh_model_rows()

    def _ask_to_download(self, repo: str) -> None:
        if self._downloading_repo is not None:
            return  # one download at a time; the row of the running one says so
        reply = QMessageBox.question(
            self, t("settings.download_confirm_title"),
            t("settings.download_confirm_msg").format(model=self._models[repo][0]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        self.model_combo.setFocus()
        if reply == QMessageBox.StandardButton.Yes:
            self._downloading_repo = repo
            self._refresh_model_rows()
            self._render_model_info()
            self.download_model_requested.emit(str(DEFAULT_DOWNLOAD_PARENT), repo)

    def _revert_model_combo(self) -> None:
        self.model_combo.blockSignals(True)
        self.model_combo.setCurrentIndex(self._last_model_index)
        self.model_combo.blockSignals(False)

    def _browse_model_dir(self) -> None:
        start_dir = self.settings.get("model_dir") or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, t("settings.select_folder_dialog"), start_dir)
        resolved = self.model_provider.resolve_model_dir(folder) if folder else None
        if not folder:
            self._revert_model_combo()
        elif resolved:
            self.settings.set("model_dir", resolved)
            _log.info(f"Model folder → {resolved}")
            self.model_dir_changed.emit(resolved)
            self._sync_model_combo(resolved)
        else:
            QMessageBox.warning(self, t("settings.invalid_folder_title"), t("settings.invalid_folder_msg"))
            self._revert_model_combo()

    def _sync_model_combo(self, model_dir: str | None) -> None:
        """Selects the list entry for the given model folder; a folder that is not a known
        model gets its own "Custom" entry above "Browse...". Without a folder no row is
        selected and the list shows its "choose a model" text. Changes no setting."""
        combo = self.model_combo
        row = -1
        if model_dir:
            folder_name = Path(model_dir).name
            row = next((i for i in range(combo.count())
                        if str(combo.itemData(i)).split("/")[-1] == folder_name
                        and combo.itemData(i) in self._models), -1)
            if row == -1:
                custom = f"{_CUSTOM}{model_dir}"
                row = combo.findData(custom)
                if row == -1:
                    row = combo.count() - 1  # above "Browse..."
                    combo.blockSignals(True)
                    combo.insertItem(row, "", userData=custom)   # text: _refresh_model_rows
                    combo.blockSignals(False)
        combo.blockSignals(True)
        combo.setCurrentIndex(row)
        combo.blockSignals(False)
        self._last_model_index = row
        self._refresh_model_rows()

    def _selected_model_path(self) -> Path | None:
        repo = self.model_combo.currentData()
        if not repo or repo == _BROWSE:
            return None
        if str(repo).startswith(_CUSTOM):
            return Path(str(repo).split(":", 1)[1])
        return DEFAULT_DOWNLOAD_PARENT / repo.split("/")[-1]

    def _refresh_model_rows(self) -> None:
        """Writes every row's text: the model's name and its state. The model in use is bold."""
        active = self.model_provider.get_active_model_path()
        active_name = Path(active).name if active else None
        bold, normal = QFont(), QFont()
        bold.setBold(True)
        combo = self.model_combo
        combo.blockSignals(True)
        for row in range(combo.count()):
            repo = combo.itemData(row)
            if repo in self._models:
                name, size = self._models[repo]
                folder_name = repo.split("/")[-1]
                is_active = active_name == folder_name
                if is_active:
                    state = t("settings.model_in_use")
                elif repo == self._downloading_repo:
                    state = t("settings.model_downloading")
                elif self.model_provider.resolve_model_dir(str(DEFAULT_DOWNLOAD_PARENT / folder_name)) is not None:
                    state = t("settings.model_installed")
                else:
                    state = t("settings.model_get").format(size=format_size(size))
                text = f"{name} · {state}"
            elif str(repo).startswith(_CUSTOM):
                folder = Path(str(repo).split(":", 1)[1])
                is_active = active is not None and Path(active) == folder
                text = t("settings.custom_folder").format(name=folder.name)
                if is_active:
                    text += f" · {t('settings.model_in_use')}"
            else:
                continue   # "Browse..."
            combo.setItemData(row, bold if is_active else normal, Qt.ItemDataRole.FontRole)
            combo.setItemText(row, text)
        combo.blockSignals(False)

    def _load_prompt_for_language(self, language: str) -> None:
        """Shows the prompt that belongs to the speech language: the one the user saved for it,
        else a stock sentence in that language. Automatic detection uses no prompt."""
        if language == "auto":
            prompt = ""
        else:
            saved = (self.settings.get("initial_prompts") or {}).get(language)
            prompt = saved if saved is not None else DEFAULT_PROMPTS.get(language, "")
        self.prompt_edit.blockSignals(True)
        self.prompt_edit.setPlainText(prompt)
        self.prompt_edit.blockSignals(False)
        self.settings.set("initial_prompt", prompt)
        self._set_prompt_unsaved(False)

    def _on_prompt_edited(self) -> None:
        self._set_prompt_unsaved(self.prompt_edit.toPlainText() != self.settings.get("initial_prompt", ""))

    def _set_prompt_unsaved(self, unsaved: bool) -> None:
        self.btn_save_prompt.setEnabled(unsaved)
        self.btn_save_prompt.set_active(unsaved)

    def _save_prompt(self) -> None:
        text = self.prompt_edit.toPlainText()
        self.settings.set("initial_prompt", text)
        language = self.speech_language_combo.currentData()
        if language != "auto":  # prompts are remembered per speech language
            prompts = dict(self.settings.get("initial_prompts") or {})
            prompts[language] = text
            self.settings.set("initial_prompts", prompts)
        self._set_prompt_unsaved(False)

    # -------------------------------------------------------------------- app
    def _on_app_language_changed(self, _idx: int) -> None:
        code = self.app_language_combo.currentData()
        if code:
            self.settings.set("app_language", code)
            self.language_change_requested.emit(code)

    # -------------------------------------------------------------------- log
    def append_log_entry(self, level: str, component: str, message: str, i18n_key: str = "") -> None:
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self._log_entries.append((level, component, message, i18n_key, timestamp))
        del self._log_entries[:-LOG_LIMIT]
        self._append_log_line(*self._log_entries[-1])

    def _render_log(self) -> None:
        self.log_box.document().clear()
        for entry in self._log_entries:
            self._append_log_line(*entry)

    def _append_log_line(self, level: str, component: str, message: str, i18n_key: str, timestamp: str) -> None:
        p = theme_manager.palette
        tag = _LOG_LABEL.get(level, level)[:4].ljust(4).replace(" ", "&nbsp;")
        name = component.strip()[:3].ljust(3).replace(" ", "&nbsp;")
        text = html.escape(t(i18n_key) if i18n_key else message)
        colour = p[_LOG_COLOUR.get(level, "CLR_TEXT")]
        self.log_box.append(
            f"<span style='color:{p['CLR_TEXT_FAINT']}'>[{timestamp}]</span>&nbsp;&nbsp;"
            f"<span style='color:{colour};font-weight:bold'>{tag}</span>&nbsp;&nbsp;"
            f"<span style='color:{p['CLR_TEXT_MUTED']}'>{name}</span>&nbsp;&nbsp;"
            f"<span style='color:{p['CLR_TEXT']}'>{text}</span>"
        )
        scrollbar = self.log_box.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _open_log_folder(self) -> None:
        log_dir = str(get_log_dir())
        if os.path.exists(log_dir):
            os.startfile(log_dir)
        else:
            _log.warning(t("settings.log_folder_missing"))

    # ----------------------------------------------------------------- values
    def _refresh_values(self) -> None:
        """Puts the stored settings into the widgets, without firing their change handlers."""
        self.btn_hotkey.setText(self.settings.get("hotkey", "F9").upper())
        for combo, value in (
            (self.speech_language_combo, self.settings.get("language") or "auto"),
            (self.app_language_combo, self.settings.get("app_language") or "en"),
            (self.injection_combo, self.settings.get("injection_method")),
        ):
            row = combo.findData(value)
            if row >= 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(row)
                combo.blockSignals(False)

        # The model list shows the model actually in use (the provider's answer), which is
        # not always the stored model_dir: the default model_dir is just the models folder.
        self._sync_model_combo(self.model_provider.get_active_model_path())
        self._render_model_info()
        self._load_prompt_for_language(self.speech_language_combo.currentData())
