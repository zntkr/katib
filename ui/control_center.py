from PySide6.QtWidgets import (
    QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QFrame, QFileDialog, QMessageBox, QLineEdit, QTextEdit,
    QSizePolicy, QTabWidget, QProgressBar, QTextBrowser, QScrollArea, QPlainTextEdit
)
from PySide6.QtCore import Qt, Signal, QTimer, Slot
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QKeyEvent, QFont

from ui.utils_win import apply_dark_mode_to_window
from ui.utils import qt_key_to_keyboard
from core.settings import (
    APP_NAME, WHISPER_MODELS,
    DEFAULT_DOWNLOAD_PARENT, COMPUTE_TYPE_OPTIONS_CPU,
    SETTINGS_SCHEMA
)
from ui.theme import G_1, G_2, G_4, G_6, FONT_SIZE_SM, FONT_SIZE_MD, SETTINGS_WIDTH, SETTINGS_HEIGHT, theme_manager
from ui.components import NoScrollComboBox, DynamicIconButton
from ui.icons import ICN_DOWNLOAD, ICN_TICK
from core.i18n import t, available_languages

class ModelItemWidget(QFrame):
    download_requested = Signal(str)
    select_requested = Signal(str)

    def __init__(self, model_id, model_info, is_installed, is_active, parent=None):
        super().__init__(parent)
        self.model_id = model_id
        self.model_info = model_info
        self.is_installed = is_installed
        self.is_active = is_active
        self.setStyleSheet("QFrame { border: 1px solid #444; border-radius: 6px; background: #222; } QFrame:hover { border-color: #666; }")
        self.setFixedHeight(70)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        left_layout = QVBoxLayout()
        name_lbl = QLabel(f"<b>{model_id.upper()}</b> <span style='color: #888; font-size: 9pt;'>({model_info.get('size', '')})</span>")
        name_lbl.setStyleSheet("border: none; background: transparent;")
        desc_lbl = QLabel(model_info.get('desc', ''))
        desc_lbl.setStyleSheet("color: #aaa; font-size: 9pt; border: none; background: transparent;")
        left_layout.addWidget(name_lbl)
        left_layout.addWidget(desc_lbl)
        layout.addLayout(left_layout)
        
        layout.addStretch()
        
        self.progress = QProgressBar()
        self.progress.setFixedWidth(100)
        self.progress.setFixedHeight(12)
        self.progress.hide()
        layout.addWidget(self.progress)
        
        self.btn_action = QPushButton()
        self.btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_action.setFixedWidth(80)
        layout.addWidget(self.btn_action)
        
        self.update_state(is_installed, is_active)
        self.btn_action.clicked.connect(self._on_action)

    def update_state(self, is_installed, is_active):
        self.is_installed = is_installed
        self.is_active = is_active
        if is_active:
            self.btn_action.setText("Aktif")
            self.btn_action.setStyleSheet("QPushButton { padding: 4px 12px; border-radius: 4px; background: #4CAF50; color: white; font-weight: bold; }")
            self.btn_action.setEnabled(False)
            self.setStyleSheet("QFrame { border: 1px solid #4CAF50; border-radius: 6px; background: #2a332a; }")
        elif is_installed:
            self.btn_action.setText("Seç")
            self.btn_action.setStyleSheet("QPushButton { padding: 4px 12px; border-radius: 4px; background: #333; color: white; font-weight: bold; } QPushButton:hover { background: #444; }")
            self.btn_action.setEnabled(True)
            self.setStyleSheet("QFrame { border: 1px solid #444; border-radius: 6px; background: #222; } QFrame:hover { border-color: #666; }")
        else:
            self.btn_action.setText("İndir")
            self.btn_action.setStyleSheet("QPushButton { padding: 4px 12px; border-radius: 4px; background: #FFC107; color: black; font-weight: bold; } QPushButton:hover { background: #FFB300; }")
            self.btn_action.setEnabled(True)
            self.setStyleSheet("QFrame { border: 1px solid #444; border-radius: 6px; background: #222; } QFrame:hover { border-color: #666; }")

    def set_downloading(self, downloading):
        if downloading:
            self.btn_action.hide()
            self.progress.show()
        else:
            self.btn_action.show()
            self.progress.hide()

    def _on_action(self):
        if self.is_installed:
            self.select_requested.emit(self.model_id)
        else:
            self.download_requested.emit(self.model_id)

class ControlCenterWindow(QDialog):
    _DEFAULT_PROMPTS: dict[str, str] = {
        "ar": "مرحباً. أقوم اليوم بتدوين ملاحظاتي بالصوت.",
        "de": "Hallo. Ich diktiere heute meine Notizen per Sprache.",
        "el": "Γεια σας. Σήμερα υπαγορεύω τις σημειώσεις μου φωνητικά.",
        "en": "Hello. I'm dictating my notes using voice today.",
        "es": "Hola. Hoy estoy dictando mis notas por voz.",
        "fa": "سلام. امروز یادداشت‌های خود را به صورت صوتی دیکته می‌کنم.",
        "fr": "Bonjour. Je dicte mes notes à voix haute aujourd'hui.",
        "hi": "नमस्ते। आज मैं अपने नोट्स आवाज़ से बोल रहा हूँ।",
        "id": "Halo. Hari ini saya mendiktekan catatan saya secara lisan.",
        "it": "Ciao. Oggi sto dettando le mie note a voce.",
        "ja": "こんにちは。今日は音声でメモを書き取っています。",
        "ko": "안녕하세요. 오늘 음성으로 메모를 받아쓰고 있습니다.",
        "pt": "Olá. Hoje estou ditando minhas anotações por voz.",
        "ru": "Привет. Сегодня я диктую свои заметки голосом.",
        "tr": "Merhaba. Bugün notlarımı sesli olarak dikte ediyorum.",
        "ur": "السلام علیکم۔ آج میں اپنے نوٹس آواز سے لکھوا رہا ہوں۔",
        "zh": "你好。今天我正在用语音记录我的笔记。",
    }

    hotkey_changed           = Signal(str)
    device_changed           = Signal(int)
    refresh_devices_requested= Signal()
    model_dir_changed        = Signal(str)
    model_reload_requested   = Signal()
    download_model_requested = Signal(str, str)
    log_entry                = Signal(str, str, str)
    capture_mode_changed     = Signal(bool)  # True=capture started, False=finished
    language_change_requested = Signal(str)
    theme_changed             = Signal(str)

    def __init__(self, settings, model_provider, parent: QWidget | None = None):
        flags = (
            Qt.WindowType.Window |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        super().__init__(parent, flags)
        self.settings = settings
        self.model_provider = model_provider
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowTitle(f"{APP_NAME} - Control Center")
        self.setFixedWidth(700)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._capturing_hotkey = False
        self._dynamic_widgets = {}
        self._last_devices = None
        self._build_ui()

    def paintEvent(self, event: QPaintEvent) -> None:
        from ui.theme import theme_manager
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(theme_manager.palette["CLR_BG_DEEP"]))
        painter.end()
        super().paintEvent(event)

    @Slot(str, str, str)
    def append_log_entry(self, level: str, category: str, message: str) -> None:
        """Appends a styled log entry to the log display."""
        import datetime
        from ui.theme import theme_manager
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        
        p = theme_manager.palette
        colors = {
            "ERR": p.get("CLR_ERR", "red"),
            "WRN": p.get("CLR_WARN", "orange"),
            "OK":  p.get("CLR_OK", "green"),
            "INFO": p.get("CLR_INFO", "cyan")
        }
        color = colors.get(level, p["CLR_TEXT_MUTED"])
        
        html = f'<span style="color: {p["CLR_TEXT_MUTED"]}">{time_str}</span> '
        html += f'<span style="color: {color}"><b>[{level}]</b></span> '
        html += f'<span style="color: {p.get("CLR_TEXT_FAINT", "#7c6f64")}">[{category}]</span> '
        html += f'<span style="color: {p.get("CLR_TEXT_MAIN", "#ebdbb2")}">{message}</span>'
        
        if hasattr(self, "log_display"):
            self.log_display.append(html)

        if hasattr(self, "_update_dashboard_log"):
            self._update_dashboard_log(level, category, message)

    @Slot(int, float, float)
    def set_download_progress(self, percent: int, downloaded_mb: float, total_mb: float) -> None:
        if hasattr(self, "dl_progress"):
            if self.dl_progress.isHidden():
                self.dl_progress.show()
                self.btn_download.hide()
            self.dl_progress.setValue(percent)
            self.dl_progress.setFormat(f"%p% ({downloaded_mb:.1f} MB / {total_mb:.1f} MB)")
            
    @Slot(bool)
    def set_download_state(self, active: bool) -> None:
        if hasattr(self, "dl_progress"):
            if active:
                self.dl_progress.setRange(0, 100)
                self.dl_progress.setValue(0)
                self.dl_progress.setFormat("İndiriliyor...")
                self.dl_progress.show()
                self.btn_download.hide()
            else:
                self.dl_progress.hide()
                self.btn_download.show()

    def show(self):
        self._refresh_values()
        try:
            apply_dark_mode_to_window(int(self.winId()))
        except Exception:
            pass
        super().show()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(0, self.btn_hotkey.setFocus)

    def _section_title(self, key: str) -> QLabel:
        p = theme_manager.palette
        lbl = QLabel(t(key).upper())
        lbl.setStyleSheet(
            f"color: {p['CLR_YELLOW']}; font-weight: bold; "
            f"font-size: {FONT_SIZE_SM}pt; letter-spacing: 1px;"
        )
        return lbl

    def _build_dashboard_tab(self):
        p = theme_manager.palette
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(G_4)
        
        self.dashboard_led = QLabel("●")
        self.dashboard_led.setStyleSheet(f"color: {p['CLR_TEXT_MUTED']}; font-size: 32pt;")
        self.dashboard_status = QLabel(t("status.idle"))
        self.dashboard_status.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {p['CLR_TEXT']};")
        
        status_layout = QHBoxLayout()
        status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.dashboard_led)
        status_layout.addWidget(self.dashboard_status)
        layout.addLayout(status_layout)
        
        self.dashboard_model = QLabel("Aktif Model: -")
        self.dashboard_model.setStyleSheet(f"color: {p['CLR_TEXT_MUTED']}; font-size: 10pt;")
        layout.addWidget(self.dashboard_model, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addSpacing(G_4)
        
        self.dashboard_log = QPlainTextEdit()
        self.dashboard_log.setReadOnly(True)
        self.dashboard_log.setFixedHeight(80)
        self.dashboard_log.setStyleSheet(
            f"background: {p['CLR_BG_ELEVATED']}; border: 1px solid {p['CLR_BORDER_LIGHT']}; "
            f"border-radius: 4px; font-family: Consolas, monospace; font-size: 9pt; color: {p['CLR_TEXT']};"
        )
        layout.addWidget(self.dashboard_log)
        
        self.tabs.addTab(tab, "Ana Ekran")

    def _update_dashboard_log(self, level, category, message):
        text = f"[{category}] {message}"
        self.dashboard_log.appendPlainText(text)
        # Keep only last 10 lines
        doc = self.dashboard_log.document()
        if doc.blockCount() > 10:
            cursor = self.dashboard_log.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()

    def _update_dashboard_status(self, state, status_type):
        p = theme_manager.palette
        self.dashboard_status.setText(t(state))
        color = p.get(f"CLR_{status_type}", p["CLR_TEXT"])
        if status_type == "OK": color = p["CLR_GREEN"]
        elif status_type == "ERR": color = p["CLR_RED"]
        elif status_type == "WARN": color = p["CLR_YELLOW"]
        elif status_type == "IDLE": color = p["CLR_TEXT_MUTED"]
        self.dashboard_led.setStyleSheet(f"color: {color}; font-size: 32pt;")

    def _handle_link(self, url):
        pass

    def _make_row(self, label_text: str, widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(G_1)
        lbl = QLabel(label_text)
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(lbl)
        row.addWidget(widget)
        return row

    def _build_ui(self):
        p = theme_manager.palette

        outer = QVBoxLayout(self)
        outer.setContentsMargins(G_2, G_2, G_2, G_2)
        outer.setSpacing(G_2)
        outer.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.West)
        self.tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid {p['CLR_BORDER_LIGHT']}; border-radius: 4px; background: transparent; }}"
            f"QTabBar::tab {{ padding: 12px 16px; margin-bottom: 2px; font-weight: bold; font-size: {FONT_SIZE_MD}pt; color: {p['CLR_TEXT_MUTED']}; border-radius: 4px; min-width: 100px; text-align: left; }}"
            f"QTabBar::tab:selected {{ color: {p['CLR_TEXT']}; background: {p['CLR_BG_ELEVATED']}; border-left: 3px solid {p['CLR_YELLOW']}; }}"
            f"QTabBar::tab:hover {{ background: {p['CLR_BG_ELEVATED']}; }}"
        )
        outer.addWidget(self.tabs)

        self._build_dashboard_tab()

        tab_general = QWidget()
        left = QFormLayout(tab_general)
        left.setVerticalSpacing(G_2)
        left.setHorizontalSpacing(G_4)
        left.setContentsMargins(G_4, G_4, G_4, G_4)
        self.tabs.addTab(tab_general, "Genel")

        left.addRow(self._section_title("settings.group_general"))

        self.btn_hotkey = QPushButton()
        self.btn_hotkey.setProperty("isIconBtn", True)
        self.btn_hotkey.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hotkey.clicked.connect(self._start_hotkey_capture)
        self.btn_hotkey.setFixedHeight(G_4)
        self.btn_hotkey.setMinimumWidth(G_4)
        self.btn_hotkey.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        left.addRow(t("settings.hotkey_label"), self.btn_hotkey)
        
        self.mic_combo = NoScrollComboBox()
        self.mic_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.mic_combo.currentIndexChanged.connect(self._on_device_changed)
        left.addRow("Microphone", self.mic_combo)

        self._lang_combo = NoScrollComboBox()
        self._lang_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for name, code in available_languages():
            self._lang_combo.addItem(name, userData=code)
        self._lang_combo.currentIndexChanged.connect(self._on_app_language_changed)
        left.addRow(t("settings.app_language_label"), self._lang_combo)

        self._theme_combo = NoScrollComboBox()
        self._theme_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for label, value in [
            (t("settings.theme_system"), "system"),
            (t("settings.theme_dark"),   "dark"),
            (t("settings.theme_light"),  "light"),
        ]:
            self._theme_combo.addItem(label, userData=value)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        left.addRow(t("settings.theme_label"), self._theme_combo)

        self._injection_combo = NoScrollComboBox()
        self._injection_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for label, value in [
            ("Clipboard (Fast)", "clipboard"),
            ("Keystroke (Safe)", "keystroke"),
        ]:
            self._injection_combo.addItem(label, userData=value)
        self._injection_combo.currentIndexChanged.connect(
            lambda _idx: self._on_dynamic_changed("injection_method", self._injection_combo.currentData())
        )
        left.addRow(t("settings.injection_method_label"), self._injection_combo)

        left.addRow(QLabel(""))

        left.addRow(self._section_title("settings.group_system"))

        btn_help = QPushButton(t("settings.user_guide"))
        btn_help.clicked.connect(self._open_help)
        left.addRow(btn_help)
        
        btn_copy = QPushButton("Copy Last Transcript")
        btn_copy.clicked.connect(self._copy_last_transcript)
        left.addRow(btn_copy)

        btn_logs = QPushButton(t("settings.open_log_folder"))
        btn_logs.clicked.connect(self._open_log_folder)
        left.addRow(btn_logs)

        
        btn_reset = QPushButton(t("settings.reset_settings"))
        btn_reset.clicked.connect(self._reset_advanced)
        left.addRow(btn_reset)

        self._build_model_tab()

        # Status Bar
        status_bar = QWidget()
        status_lay = QHBoxLayout(status_bar)
        status_lay.setContentsMargins(G_2, G_1, G_2, G_1)
        status_lay.setSpacing(G_1)
        self.led_indicator = QLabel("●")
        self.led_indicator.setStyleSheet(f"color: {p['CLR_IDLE']}; font-size: 12pt;")
        self.lbl_status = QLabel(t('status.idle'))
        self.lbl_status.setStyleSheet(f"color: {p.get('CLR_TEXT_MUTED', '#928374')}; font-size: {FONT_SIZE_SM}pt;")
        status_lay.addWidget(self.led_indicator)
        status_lay.addWidget(self.lbl_status)
        status_lay.addStretch(1)
        
        outer.addWidget(status_bar)

        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._on_tab_changed(0)



    def _build_model_tab(self):
        p = theme_manager.palette
        tab_model = QWidget()
        right = QVBoxLayout(tab_model)
        right.setSpacing(G_2)
        right.setContentsMargins(G_4, G_4, G_4, G_4)
        self.tabs.addTab(tab_model, "Modeller")
        
        right.addWidget(self._section_title("settings.group_model"))
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background: transparent; }}")
        
        self.model_list_widget = QWidget()
        self.model_list_layout = QVBoxLayout(self.model_list_widget)
        self.model_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.model_list_widget)
        right.addWidget(scroll)
        
        self._model_widgets = {}
        self._populate_model_list()
        
        right.addSpacing(G_4)
        right.addWidget(self._section_title("settings.group_processing"))
        
        proc_form = QFormLayout()
        right.addLayout(proc_form)
        

        for sdef in SETTINGS_SCHEMA:
            if sdef.ui_group != "Processing":
                continue

            widget = None
            real_input_widget = None
            full_width = sdef.ui_kwargs.get("full_width", False)

            if sdef.ui_widget == "combobox":
                widget = NoScrollComboBox()
                widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                for lbl, val in sdef.ui_kwargs.get("options", []):
                    widget.addItem(lbl, userData=val)
                widget.currentIndexChanged.connect(
                    lambda _idx, key=sdef.key, w=widget: self._on_dynamic_changed(key, w.currentData())
                )

            elif sdef.ui_widget == "spinbox":
                widget = QSpinBox()
                widget.setRange(sdef.ui_kwargs.get("min", 0), sdef.ui_kwargs.get("max", 100))
                widget.valueChanged.connect(lambda v, key=sdef.key: self._on_dynamic_changed(key, v))

            elif sdef.ui_widget == "doublespinbox":
                widget = QDoubleSpinBox()
                widget.setRange(sdef.ui_kwargs.get("min", 0.0), sdef.ui_kwargs.get("max", 1.0))
                widget.setSingleStep(sdef.ui_kwargs.get("step", 0.1))
                widget.setDecimals(sdef.ui_kwargs.get("decimals", 2))
                widget.valueChanged.connect(lambda v, key=sdef.key: self._on_dynamic_changed(key, v))

            elif sdef.ui_widget == "lineedit":
                container = QWidget()
                hlay = QHBoxLayout(container)
                hlay.setContentsMargins(0, 0, 0, 0)
                hlay.setSpacing(G_1)
                if sdef.key == "initial_prompt":
                    le = QTextEdit()
                    le.setFixedHeight(G_6)
                    le.setAcceptRichText(False)
                else:
                    le = QLineEdit()
                    le.setMinimumWidth(50)
                    le.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                btn_save = DynamicIconButton(ICN_TICK, p["CLR_YELLOW"])
                btn_save.setEnabled(False)

                def _make_save_handler(k, input_w, btn):
                    def _get_text():
                        return input_w.toPlainText() if isinstance(input_w, QTextEdit) else input_w.text()
                    def on_text_changed():
                        is_changed = _get_text() != self.settings.get(k, "")
                        btn.setEnabled(is_changed)
                        btn.set_active(is_changed)
                    def on_save():
                        if not btn.isEnabled(): return
                        val = _get_text()
                        self._on_dynamic_changed(k, val)
                        if k == "initial_prompt":
                            lang = self.settings.get("language", "auto")
                            if lang != "auto":
                                prompts = self.settings.get("initial_prompts") or {}
                                prompts[lang] = val
                                self.settings.set("initial_prompts", prompts)
                        btn.setEnabled(False)
                        btn.set_active(False)
                    return on_text_changed, on_save

                text_handler, save_handler = _make_save_handler(sdef.key, le, btn_save)
                if isinstance(le, QTextEdit):
                    le.textChanged.connect(text_handler)
                else:
                    le.textChanged.connect(lambda _text, h=text_handler: h())
                    le.returnPressed.connect(save_handler)
                btn_save.clicked.connect(save_handler)
                hlay.addWidget(le)
                hlay.addWidget(btn_save)
                widget = container
                real_input_widget = le

            elif sdef.ui_widget == "custom":
                if sdef.key == "compute_type":
                    self.compute_combo = NoScrollComboBox()
                    self.compute_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                    self.compute_combo.currentIndexChanged.connect(self._on_compute_type_changed)
                    widget = self.compute_combo

            if widget:
                real_widget = real_input_widget if real_input_widget is not None else widget
                if sdef.tooltip:
                    real_widget.setToolTip(t(sdef.tooltip))
                self._dynamic_widgets[sdef.key] = real_widget
                if full_width and sdef.key == "initial_prompt":
                    lbl_tmp = QLabel(t(sdef.ui_label))
                    proc_form.addRow(lbl_tmp, real_widget)
                else:
                    proc_form.addRow(t(sdef.ui_label), real_widget)

        

        # Tab 3: Logs
        tab_logs = QWidget()
        logs_layout = QVBoxLayout(tab_logs)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs.addTab(tab_logs, "Kayıtlar (Logs)")
        
        self.log_display = QTextBrowser()
        self.log_display.setOpenExternalLinks(False)
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("background-color: #0d0d0d; color: #d0d0d0; font-family: Consolas, monospace; font-size: 10pt; border: none; padding: 4px;")
        logs_layout.addWidget(self.log_display)


    def _on_tab_changed(self, index: int) -> None:
        for i in range(self.tabs.count()):
            policy = QSizePolicy.Policy.Ignored if i != index else QSizePolicy.Policy.Preferred
            self.tabs.widget(i).setSizePolicy(QSizePolicy.Policy.Preferred, policy)
        self.adjustSize()

    def focus_model(self) -> None:
        pass

    def _on_dynamic_changed(self, key: str, value):
        self.settings.set(key, value)
        if key == "language":
            self._load_prompt_for_language(value)

    def _load_prompt_for_language(self, lang: str) -> None:
        le = self._dynamic_widgets.get("initial_prompt")
        if not isinstance(le, (QLineEdit, QTextEdit)):
            return
        if lang == "auto":
            prompt = ""
        else:
            saved = (self.settings.get("initial_prompts") or {}).get(lang)
            prompt = saved if saved is not None else self._DEFAULT_PROMPTS.get(lang, "")
        le.blockSignals(True)
        if isinstance(le, QTextEdit):
            le.setPlainText(prompt)
        else:
            le.setText(prompt)
        le.blockSignals(False)
        self.settings.set("initial_prompt", prompt)
        parent_w = le.parentWidget()
        if parent_w:
            btn = parent_w.findChild(DynamicIconButton)
            if btn:
                btn.setEnabled(False)
                btn.set_active(False)

    def _on_app_language_changed(self, _idx: int) -> None:
        code = self._lang_combo.currentData()
        if code:
            self.settings.set("app_language", code)
            self.language_change_requested.emit(code)

    def _on_theme_changed(self, _idx: int) -> None:
        value = self._theme_combo.currentData()
        if value:
            self.settings.set("theme", value)
            self.theme_changed.emit(value)

    def _center_on_screen(self):
        screen_geo = QApplication.primaryScreen().availableGeometry()
        center_pt = screen_geo.center()
        x_pos = center_pt.x() - int(self.width() / 2)
        y_pos = center_pt.y() - int(self.height() / 2)
        self.setGeometry(x_pos, y_pos, self.width(), self.height())

    def _open_help(self) -> None:
        from ui.help_window import HelpWindow
        if not hasattr(self, "_help_window"):
            self._help_window = HelpWindow(settings=self.settings, parent=self)
        self._help_window.show()

    def _open_log_folder(self) -> None:
        import os
        import sys
        log_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), APP_NAME, "Logs")
        if os.path.exists(log_dir):
            if sys.platform == "win32":
                os.startfile(log_dir)
            else:
                import subprocess
                subprocess.Popen(["xdg-open", log_dir])
        else:
            self.log_entry.emit("WRN", "APP", t("settings.log_folder_missing"))

    def _start_hotkey_capture(self) -> None:
        self._capturing_hotkey = True
        self.btn_hotkey.setText(t("settings.hotkey_capture"))
        from ui.theme import theme_manager
        clr = theme_manager.palette["CLR_INFO"]
        self.btn_hotkey.setStyleSheet(f"border-color: {clr}; color: {clr}; font-weight: bold;")
        self.btn_hotkey.setFocus()
        self.capture_mode_changed.emit(True)

    def _sync_list_with_current_dir(self, current_dir: str):
        self._refresh_model_list_badges()

        if hasattr(self, "dashboard_model") and current_dir:
            import os
            self.dashboard_model.setText(f"Aktif Model: {os.path.basename(current_dir)}")

    def _get_selected_model_path(self, repo):
        from pathlib import Path
        if not repo or repo == "browse_custom": return None
        if str(repo).startswith("custom:"):
            return Path(repo.split(":", 1)[1])
        from core.settings import WHISPER_MODELS, DEFAULT_DOWNLOAD_PARENT
        model_info = WHISPER_MODELS.get(repo)
        if not model_info: return None
        return DEFAULT_DOWNLOAD_PARENT / model_info["filename"]

    def _populate_model_list(self):
        from pathlib import Path
        from core.settings import WHISPER_MODELS, DEFAULT_DOWNLOAD_PARENT
        
        # Clear existing widgets
        for i in reversed(range(self.model_list_layout.count())):
            widget = self.model_list_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        self._model_widgets.clear()
        
        active_dir = self.settings.get("model_dir")
        
        # 1. Standard Models
        for key, info in WHISPER_MODELS.items():
            expected = DEFAULT_DOWNLOAD_PARENT / info["filename"]
            is_installed = expected.exists()
            is_active = (active_dir is not None and Path(active_dir) == expected)
            
            widget = ModelItemWidget(key, info, is_installed, is_active)
            widget.download_requested.connect(self._on_model_download)
            widget.select_requested.connect(self._on_model_select)
            
            self.model_list_layout.addWidget(widget)
            self._model_widgets[key] = widget
            
        # 2. Dynamic Models
        if DEFAULT_DOWNLOAD_PARENT.exists():
            known_filenames = {info["filename"] for info in WHISPER_MODELS.values()}
            for child in DEFAULT_DOWNLOAD_PARENT.iterdir():
                if child.is_file() and child.suffix in ('.bin', '.gguf'):
                    if child.name not in known_filenames:
                        custom_id = f"custom:{child}"
                        is_installed = True
                        is_active = (active_dir is not None and Path(active_dir) == child)
                        info = {"size": "Local File", "desc": "Custom imported model"}
                        
                        widget = ModelItemWidget(custom_id, info, is_installed, is_active)
                        widget.download_requested.connect(self._on_model_download)
                        widget.select_requested.connect(self._on_model_select)
                        
                        self.model_list_layout.addWidget(widget)
                        self._model_widgets[custom_id] = widget

    def _refresh_model_list_badges(self) -> None:
        from pathlib import Path
        from core.settings import WHISPER_MODELS, DEFAULT_DOWNLOAD_PARENT
        active_dir = self.settings.get("model_dir")
        
        for key, widget in self._model_widgets.items():
            if key.startswith("custom:"):
                file_path = Path(key.split(":", 1)[1])
                is_active = (active_dir is not None and Path(active_dir) == file_path)
                is_installed = file_path.exists()
            else:
                info = WHISPER_MODELS.get(key)
                if not info: continue
                expected = DEFAULT_DOWNLOAD_PARENT / info["filename"]
                is_active = (active_dir is not None and Path(active_dir) == expected)
                is_installed = expected.exists()
            
            widget.update_state(is_installed, is_active)

    def _on_model_select(self, model_id: str):
        target_path = self._get_selected_model_path(model_id)
        if target_path and target_path.exists():
            self.settings.set("model_dir", str(target_path))
            self.model_dir_changed.emit(str(target_path))
            self.log_entry.emit("OK", "APP", f"Switched to model: {target_path.name}")
            self._refresh_model_list_badges()
            if hasattr(self, "dashboard_model"):
                self.dashboard_model.setText(f"Aktif Model: {model_id.upper()} ({target_path.name})")

    def _on_model_download(self, model_id: str):
        from core.settings import DEFAULT_DOWNLOAD_PARENT
        target_path = self._get_selected_model_path(model_id)
        if not target_path: return
        is_installed = target_path.exists()
        if not is_installed:
            from core.i18n import t
            msg = t("settings.download_confirm_msg").format(model=model_id)
            reply = QMessageBox(self)
            reply.setWindowTitle(t("settings.download_confirm_title"))
            reply.setText(msg)
            reply.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            reply.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            if reply.exec() == QMessageBox.StandardButton.Yes:
                widget = self._model_widgets.get(model_id)
                if widget:
                    widget.set_downloading(True)
                self.download_model_requested.emit(str(DEFAULT_DOWNLOAD_PARENT), model_id)

    def _refresh_values(self, hard: bool = False) -> None:
        current_dir = self.settings.get("model_dir")
        fallback = self.model_provider.get_active_model_path()
        if not current_dir and fallback:
            if self.model_provider.resolve_model_dir(fallback):
                current_dir = fallback
                self.settings.set("model_dir", current_dir)
                self.model_dir_changed.emit(current_dir)

        self._sync_list_with_current_dir(current_dir)
        self._populate_compute_type_options()
        
        for key, widget in self._dynamic_widgets.items():
            val = self.settings.get(key)
            if val is None:
                continue
            widget.blockSignals(True)
            if isinstance(widget, QComboBox):
                idx = widget.findData(val)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setValue(val)
            elif isinstance(widget, QTextEdit):
                if key == "initial_prompt":
                    lang = self.settings.get("language", "auto")
                    saved_prompts = self.settings.get("initial_prompts") or {}
                    prompt_val = saved_prompts.get(lang) if lang != "auto" else ""
                    if prompt_val is None:
                        prompt_val = self._DEFAULT_PROMPTS.get(lang, "")
                    widget.setPlainText(prompt_val)
                else:
                    widget.setPlainText(str(val))
            elif isinstance(widget, QLineEdit):
                widget.setText(str(val))
            widget.blockSignals(False)
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._capturing_hotkey:
            modifiers = event.modifiers()
            parts = []
            if modifiers & Qt.KeyboardModifier.ControlModifier: parts.append("ctrl")
            if modifiers & Qt.KeyboardModifier.ShiftModifier: parts.append("shift")
            if modifiers & Qt.KeyboardModifier.AltModifier: parts.append("alt")
            if event.key() == Qt.Key.Key_Escape:
                self._end_hotkey_capture(self.settings.get("hotkey", "F9"))
                return
            key_name = qt_key_to_keyboard(event.key())
            if not key_name: return
            parts.append(key_name)
            new_key = "+".join(parts)
            self.settings.set("hotkey", new_key)
            self.hotkey_changed.emit(new_key)
            self._end_hotkey_capture(new_key)
            return
        if event.key() == Qt.Key.Key_Escape: self.hide()
        else: super().keyPressEvent(event)

    def _end_hotkey_capture(self, key: str) -> None:
        self._capturing_hotkey = False
        self.btn_hotkey.setText(key.upper())
        self.btn_hotkey.setStyleSheet("")
        self.capture_mode_changed.emit(False)

    def set_download_state(self, active: bool) -> None:
        self.btn_download.setEnabled(not active)

    def on_download_complete(self, model_dir: str) -> None:
        self._update_model_path_label(model_dir)
        self._sync_combo_with_current_dir(model_dir)
        self._check_selected_model_status()

    # --- Microphone Selection Methods ---
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._capturing_hotkey:
            modifiers = event.modifiers()
            parts = []
            if modifiers & Qt.KeyboardModifier.ControlModifier: parts.append("ctrl")
            if modifiers & Qt.KeyboardModifier.ShiftModifier: parts.append("shift")
            if modifiers & Qt.KeyboardModifier.AltModifier: parts.append("alt")
            if event.key() == Qt.Key.Key_Escape:
                self._end_hotkey_capture(self.settings.get("hotkey", "F9"))
                return
            key_name = qt_key_to_keyboard(event.key())
            if not key_name: return
            parts.append(key_name)
            new_key = "+".join(parts)
            self.settings.set("hotkey", new_key)
            self.hotkey_changed.emit(new_key)
            self._end_hotkey_capture(new_key)
            return
        if event.key() == Qt.Key.Key_Escape: self.hide()
        else: super().keyPressEvent(event)

    def _end_hotkey_capture(self, key: str) -> None:
        self._capturing_hotkey = False
        self.btn_hotkey.setText(key.upper())
        self.btn_hotkey.setStyleSheet("")
        self.capture_mode_changed.emit(False)

    def set_download_state(self, active: bool) -> None:
        self.btn_download.setEnabled(not active)

    def on_download_complete(self, model_dir: str) -> None:
        self._update_model_path_label(model_dir)
        self._sync_combo_with_current_dir(model_dir)
        self._check_selected_model_status()

    # --- Microphone Selection Methods ---
    def populate_devices(self, items: list[tuple[str, int, bool]]) -> None:
        if getattr(self, "_last_devices", None) == items:
            return
        self._last_devices = items
        self.mic_combo.blockSignals(True)
        self.mic_combo.clear()
        saved_device  = self.settings.get("device_index")
        saved_device_name = self.settings.get("device_name")
        preferred_idx = -1
        default_idx   = -1
        for i, (label, index, is_default) in enumerate(items):
            label = label.replace("\r", "").replace("\n", " ").strip()
            self.mic_combo.addItem(label, userData=index)
            clean_label = label.replace(" (Default)", "")
            if saved_device_name:
                if clean_label == saved_device_name:
                    preferred_idx = i
            elif index == saved_device:
                preferred_idx = i
            if is_default:
                default_idx = i
        select_idx = preferred_idx if preferred_idx != -1 else default_idx
        if select_idx == -1 and items:
            select_idx = 0
        if select_idx != -1:
            self.mic_combo.setCurrentIndex(select_idx)
            
        if not items:
            self.mic_combo.setPlaceholderText(t("dashboard.no_mic_found"))
            self.mic_combo.setCurrentIndex(-1)
            self.mic_combo.setEnabled(False)
        else:
            self.mic_combo.setPlaceholderText("")
            self.mic_combo.setEnabled(True)
        self.mic_combo.blockSignals(False)

    def _on_device_changed(self, combo_idx: int):
        device_idx = self.mic_combo.itemData(combo_idx)
        if device_idx is not None:
            raw_text = self.mic_combo.itemText(combo_idx)
            clean_name = raw_text.replace(" (Default)", "")
            if " (Default)" in raw_text:
                self.settings.set("device_index", -1)
                self.settings.set("device_name", "")
            else:
                self.settings.set("device_index", device_idx)
                self.settings.set("device_name", clean_name)
            self.device_changed.emit(device_idx)

    def selected_device_index(self) -> int | None:
        return self.mic_combo.currentData()
        
    _COMPUTE_LABELS = {"int8": "Fast", "int8_float32": "Balanced", "int8_float16": "Balanced", "float16": "Fast", "float32": "Precise"}

    def _on_compute_type_changed(self, _idx: int) -> None:
        val = self.compute_combo.currentData()
        if val is None: return
        self.settings.set("compute_type", val)
        self.log_entry.emit("...", "APP", f"Precision → {val}")
        self.model_reload_requested.emit()

    def _populate_compute_type_options(self) -> None:
        options = COMPUTE_TYPE_OPTIONS_CPU
        current = self.settings.get("compute_type")
        self.compute_combo.blockSignals(True)
        self.compute_combo.clear()
        for val in options:
            label = f"{self._COMPUTE_LABELS.get(val, val)} ({val})"
            self.compute_combo.addItem(label, userData=val)
            if val == current: self.compute_combo.setCurrentIndex(self.compute_combo.count() - 1)
        self.compute_combo.blockSignals(False)

    def _reset_advanced(self) -> None:
        self.settings.reset_processing_settings()
        self._refresh_values()
        self.log_entry.emit("OK", "APP", "Settings reset.")

    def refresh_theme(self) -> None:
        from ui.theme import theme_manager
        p = theme_manager.palette
        self.btn_download.recolor(p["CLR_YELLOW"], idle_color=p["CLR_YELLOW"], hover_color=p["CLR_YELLOW"])
        for btn in self.findChildren(DynamicIconButton):
            if btn is not self.btn_download:
                btn.recolor(p["CLR_YELLOW"])


    def populate_devices(self, items: list[tuple[str, int, bool]]) -> None:
        if getattr(self, "_last_devices", None) == items:
            return
        self._last_devices = items
        self.mic_combo.blockSignals(True)
        self.mic_combo.clear()
        saved_device  = self.settings.get("device_index")
        saved_device_name = self.settings.get("device_name")
        preferred_idx = -1
        default_idx   = -1
        for i, (label, index, is_default) in enumerate(items):
            label = label.replace("\r", "").replace("\n", " ").strip()
            self.mic_combo.addItem(label, userData=index)
            clean_label = label.replace(" (Default)", "")
            if saved_device_name:
                if clean_label == saved_device_name:
                    preferred_idx = i
            elif index == saved_device:
                preferred_idx = i
            if is_default:
                default_idx = i
        select_idx = preferred_idx if preferred_idx != -1 else default_idx
        if select_idx == -1 and items:
            select_idx = 0
        if select_idx != -1:
            self.mic_combo.setCurrentIndex(select_idx)
            
        if not items:
            self.mic_combo.setPlaceholderText(t("dashboard.no_mic_found"))
            self.mic_combo.setCurrentIndex(-1)
            self.mic_combo.setEnabled(False)
        else:
            self.mic_combo.setPlaceholderText("")
            self.mic_combo.setEnabled(True)
        self.mic_combo.blockSignals(False)

    def _on_device_changed(self, combo_idx: int):
        device_idx = self.mic_combo.itemData(combo_idx)
        if device_idx is not None:
            raw_text = self.mic_combo.itemText(combo_idx)
            clean_name = raw_text.replace(" (Default)", "")
            if " (Default)" in raw_text:
                self.settings.set("device_index", -1)
                self.settings.set("device_name", "")
            else:
                self.settings.set("device_index", device_idx)
                self.settings.set("device_name", clean_name)
            self.device_changed.emit(device_idx)

    def selected_device_index(self) -> int | None:
        return self.mic_combo.currentData()
        

    def _copy_last_transcript(self) -> None:
        # SettingsDialog does not store the transcript natively, we can just proxy it via dashboard
        p = self.parentWidget()
        if p and hasattr(p, "_copy_last_transcript"):
            # Call dashboard's method but update tooltip on Settings button
            if p._last_transcript:
                QApplication.clipboard().setText(p._last_transcript)
                self.log_entry.emit("...", "APP", "Transcript copied to clipboard.")

    def set_status(self, a, b=None): pass
    def update_level(self, a): pass
    def set_loading_indicator(self, a): pass
    def on_download_complete(self, a): self._sync_combo_with_current_dir(a)
    def refresh_theme(self): self.update()

    @Slot(str, str)
    def set_system_status(self, text: str, level: str = "IDLE") -> None:
        if not hasattr(self, "lbl_status") or not hasattr(self, "led_indicator"): return
        
        p = theme_manager.palette
        colors = {
            "ERR": p.get("CLR_ERR", "red"),
            "WRN": p.get("CLR_WARN", "orange"),
            "OK":  p.get("CLR_OK", "green"),
            "INFO": p.get("CLR_INFO", "cyan"),
            "IDLE": p.get("CLR_IDLE", "gray")
        }
        color = colors.get(level, colors["IDLE"])
        
        self.lbl_status.setText(t(text))
        self.led_indicator.setStyleSheet(f"color: {color}; font-size: 12pt;")

        if hasattr(self, "_update_dashboard_status"):
            self._update_dashboard_status(text, level)

    @Slot(list)
    def populate_devices(self, devices: list) -> None:
        if not hasattr(self, "mic_combo"): return
        self.mic_combo.blockSignals(True)
        self.mic_combo.clear()
        for dev in devices:
            self.mic_combo.addItem(dev[0], userData=dev[1])
            if dev[2]:
                self.mic_combo.setCurrentIndex(self.mic_combo.count() - 1)
        self.mic_combo.blockSignals(False)
