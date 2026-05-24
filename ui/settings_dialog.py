from PySide6.QtWidgets import (
    QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QFrame, QFileDialog, QMessageBox, QLineEdit, QTextEdit,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QKeyEvent, QFont

from ui.utils_win import apply_dark_mode_to_window
from ui.utils import qt_key_to_keyboard
from core.settings import (
    APP_NAME, WHISPER_MODELS,
    validate_model_dir,
    DEFAULT_DOWNLOAD_PARENT, COMPUTE_TYPE_OPTIONS_CPU,
    SETTINGS_SCHEMA
)
from ui.theme import G_1, G_2, G_4, G_6, FONT_SIZE_SM, SETTINGS_WIDTH, SETTINGS_HEIGHT, theme_manager
from ui.components import NoScrollComboBox, DynamicIconButton
from ui.icons import ICN_DOWNLOAD, ICN_TICK
from core.i18n import t, available_languages

class SettingsDialog(QDialog):
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
    model_dir_changed        = Signal(str)
    model_reload_requested   = Signal()
    download_model_requested = Signal(str, str)
    log_entry                = Signal(str, str, str)
    capture_mode_changed     = Signal(bool)  # True=capture started, False=finished
    language_change_requested = Signal(str)
    theme_changed             = Signal(str)

    def __init__(self, settings, parent: QWidget | None = None):
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
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowTitle(f"{APP_NAME} - {t('settings.title')}")
        self.setFixedSize(SETTINGS_WIDTH, SETTINGS_HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._capturing_hotkey = False
        self._dynamic_widgets = {}
        self._build_ui()

    def paintEvent(self, event: QPaintEvent) -> None:
        from ui.theme import theme_manager
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(theme_manager.palette["CLR_BG_DEEP"]))
        painter.end()
        super().paintEvent(event)

    def show(self):
        self._refresh_values()
        try:
            apply_dark_mode_to_window(int(self.winId()))
        except Exception:
            pass
        super().show()
        self.raise_()
        self.activateWindow()
        # On a top-level QDialog, setFocus() is equivalent to activateWindow() — the OS
        # would hand focus to the first ComboBox. Because btn_hotkey is a real child widget,
        # setFocus() override works; there is no :focus style, so the user sees no highlight,
        # but Tab navigation starts from btn_hotkey.
        QTimer.singleShot(0, self.btn_hotkey.setFocus)

    def _section_title(self, key: str) -> QLabel:
        p = theme_manager.palette
        lbl = QLabel(t(key).upper())
        lbl.setStyleSheet(
            f"color: {p['CLR_YELLOW']}; font-weight: bold; "
            f"font-size: {FONT_SIZE_SM}pt; letter-spacing: 1px;"
        )
        return lbl

    def _make_row(self, label_text: str, widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
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
        outer.setSpacing(0)

        cols = QHBoxLayout()
        cols.setSpacing(0)
        outer.addLayout(cols)

        # ── Left column: General + System ────────────────────────
        left = QVBoxLayout()
        left.setSpacing(G_1)
        left.setContentsMargins(0, 0, G_2, 0)
        cols.addLayout(left, 1)

        left.addWidget(self._section_title("settings.group_general"))

        self.btn_hotkey = QPushButton()
        self.btn_hotkey.setProperty("isIconBtn", True)
        self.btn_hotkey.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hotkey.clicked.connect(self._start_hotkey_capture)
        self.btn_hotkey.setFixedHeight(G_4)
        self.btn_hotkey.setMinimumWidth(G_4)
        self.btn_hotkey.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        left.addLayout(self._make_row(t("settings.hotkey_label"), self.btn_hotkey))

        self._lang_combo = NoScrollComboBox()
        self._lang_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for name, code in available_languages():
            self._lang_combo.addItem(name, userData=code)
        self._lang_combo.currentIndexChanged.connect(self._on_app_language_changed)
        left.addWidget(QLabel(t("settings.app_language_label")))
        left.addWidget(self._lang_combo)

        self._theme_combo = NoScrollComboBox()
        self._theme_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for label, value in [
            (t("settings.theme_system"), "system"),
            (t("settings.theme_dark"),   "dark"),
            (t("settings.theme_light"),  "light"),
        ]:
            self._theme_combo.addItem(label, userData=value)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        left.addWidget(QLabel(t("settings.theme_label")))
        left.addWidget(self._theme_combo)

        left.addSpacing(G_4)

        left.addWidget(self._section_title("settings.group_system"))

        btn_help = QPushButton(t("settings.user_guide"))
        btn_help.clicked.connect(self._open_help)
        left.addWidget(btn_help)

        btn_logs = QPushButton(t("settings.open_log_folder"))
        btn_logs.clicked.connect(self._open_log_folder)
        left.addWidget(btn_logs)

        left.addSpacing(G_2)
        btn_reset = QPushButton(t("settings.reset_settings"))
        btn_reset.clicked.connect(self._reset_advanced)
        left.addWidget(btn_reset)

        # ── Divider ───────────────────────────────────────────────
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet(
            f"background-color: {p['CLR_BORDER_LIGHT']}; border: none;"
        )
        cols.addWidget(divider)

        # ── Right column: Model + Processing ─────────────────────
        right = QVBoxLayout()
        right.setSpacing(G_1)
        right.setContentsMargins(G_2, 0, 0, 0)
        cols.addLayout(right, 1)

        right.addWidget(self._section_title("settings.group_model"))

        self.model_select_combo = NoScrollComboBox()
        self.model_select_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._model_combo_base_labels: dict[str, str] = {}
        for key, info in WHISPER_MODELS.items():
            label = f"{key.capitalize()} ({info['size']}) — {info['desc']}"
            self._model_combo_base_labels[info['repo_id']] = label
            self.model_select_combo.addItem(label, userData=info['repo_id'])
        browse_idx = self.model_select_combo.count()
        self.model_select_combo.addItem(t("settings.browse"), userData="browse_custom")
        action_font = QFont()
        action_font.setItalic(True)
        self.model_select_combo.setItemData(browse_idx, action_font, Qt.ItemDataRole.FontRole)
        self.model_select_combo.currentIndexChanged.connect(self._on_combo_index_changed)

        self.btn_download = DynamicIconButton(
            ICN_DOWNLOAD, p["CLR_YELLOW"],
            idle_color=p["CLR_YELLOW"], hover_color=p["CLR_YELLOW"]
        )
        self.btn_download.setToolTip(t("settings.download"))
        self.btn_download.clicked.connect(self._on_download_clicked)

        right.addWidget(QLabel(t("settings.ai_model_label")))
        model_row = QHBoxLayout()
        model_row.setSpacing(G_1)
        model_row.addWidget(self.model_select_combo, 1)
        model_row.addWidget(self.btn_download)
        right.addLayout(model_row)

        self.lbl_model_path = QLabel(t("settings.path_not_selected"))
        self.lbl_model_path.setStyleSheet(
            f"color: {p['CLR_TEXT_MUTED']}; font-size: {FONT_SIZE_SM}pt; padding-left: 4px;"
        )
        self.lbl_model_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_model_path.setMinimumWidth(10)
        right.addWidget(self.lbl_model_path)

        right.addSpacing(G_2)
        right.addWidget(self._section_title("settings.group_processing"))

        _first_processing = True
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
                if full_width:
                    if not _first_processing:
                        right.addSpacing(G_1)
                    _first_processing = False
                    right.addWidget(QLabel(t(sdef.ui_label)))
                    right.addWidget(widget)
                else:
                    right.addLayout(self._make_row(t(sdef.ui_label), widget))

    def focus_model(self) -> None:
        QTimer.singleShot(50, self.model_select_combo.setFocus)

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
        log_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), APP_NAME, "Logs")
        if os.path.exists(log_dir):
            os.startfile(log_dir)
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

    def _on_combo_index_changed(self, idx: int) -> None:
        data = self.model_select_combo.currentData()
        if data == "browse_custom":
            self._browse_model_dir()
        else:
            self._last_combo_idx = idx
            if data and not str(data).startswith("custom:"):
                self.settings.set("selected_model_repo", data)

            # Auto-apply: switch immediately if the selected model is already installed.
            target_path = self._get_selected_model_path()
            if target_path and validate_model_dir(str(target_path)) is not None:
                current_dir = self.settings.get("model_dir")
                if current_dir != str(target_path):
                    self.settings.set("model_dir", str(target_path))
                    self._update_model_path_label(str(target_path))
                    self.model_dir_changed.emit(str(target_path))
                    name = target_path.name if not str(data).startswith("custom:") else "Custom Folder"
                    self.log_entry.emit("OK", "APP", f"Switched to model: {name}")
            
            self._check_selected_model_status()

    def _revert_combo(self):
        self.model_select_combo.blockSignals(True)
        self.model_select_combo.setCurrentIndex(getattr(self, '_last_combo_idx', 2))
        self.model_select_combo.blockSignals(False)

    def _browse_model_dir(self) -> None:
        from pathlib import Path
        start_dir = self.settings.get("model_dir") or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, t("settings.select_folder_dialog"), start_dir)
        if not folder:
            self._revert_combo()
            return
        resolved = validate_model_dir(folder)
        if resolved:
            self.settings.set("model_dir", resolved)
            self._update_model_path_label(resolved)
            self.log_entry.emit("...", "APP", f"Model folder → {resolved}")
            self.model_dir_changed.emit(resolved)
            self._sync_combo_with_current_dir(resolved)
        else:
            QMessageBox.warning(self, t("settings.invalid_folder_title"), t("settings.invalid_folder_msg"))
            self._revert_combo()

    def _update_model_path_label(self, path: str) -> None:
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(self.lbl_model_path.font())
        elided = fm.elidedText(path, Qt.TextElideMode.ElideMiddle, SETTINGS_WIDTH // 2 - G_2 * 3)
        self.lbl_model_path.setText(f"Path: {elided}")
        self.lbl_model_path.setToolTip(path)

    def _sync_combo_with_current_dir(self, current_dir: str):
        from pathlib import Path
        if not current_dir:
            # No model_dir — set the combo based on selected_model_repo instead.
            saved_repo = self.settings.get("selected_model_repo", "")
            if saved_repo:
                idx = self.model_select_combo.findData(saved_repo)
                if idx >= 0:
                    self.model_select_combo.blockSignals(True)
                    self.model_select_combo.setCurrentIndex(idx)
                    self._last_combo_idx = idx
                    self.model_select_combo.blockSignals(False)
                    return
            self.model_select_combo.setCurrentIndex(2)
            return
        folder_name = Path(current_dir).name
        matched_idx = -1
        for i in range(self.model_select_combo.count()):
            repo = self.model_select_combo.itemData(i)
            if repo and repo != "browse_custom" and not str(repo).startswith("custom:"):
                if repo.split('/')[-1] == folder_name:
                    matched_idx = i
                    break
        self.model_select_combo.blockSignals(True)
        if matched_idx >= 0:
            self.model_select_combo.setCurrentIndex(matched_idx)
            self._last_combo_idx = matched_idx
        else:
            custom_id = f"custom:{current_dir}"
            idx = self.model_select_combo.findData(custom_id)
            if idx == -1:
                idx = self.model_select_combo.count() - 2
                self.model_select_combo.insertItem(idx, t("settings.custom_folder").format(name=folder_name), userData=custom_id)
            self.model_select_combo.setCurrentIndex(idx)
            self._last_combo_idx = idx
        self.model_select_combo.blockSignals(False)
        self._check_selected_model_status()

    def _get_selected_model_path(self):
        from pathlib import Path
        repo = self.model_select_combo.currentData()
        if not repo or repo == "browse_custom": return None
        if str(repo).startswith("custom:"):
            return Path(repo.split(":", 1)[1])
        return DEFAULT_DOWNLOAD_PARENT / repo.split('/')[-1]

    def _refresh_model_combo_badges(self) -> None:
        from pathlib import Path
        current_dir = self.settings.get("model_dir")
        active_path = Path(current_dir).resolve() if current_dir else None
        self.model_select_combo.blockSignals(True)
        
        bold_font = QFont()
        bold_font.setBold(True)
        normal_font = QFont()
        normal_font.setBold(False)
        
        for i in range(self.model_select_combo.count()):
            repo = self.model_select_combo.itemData(i)
            if not repo or repo == "browse_custom" or str(repo).startswith("custom:"):
                continue
            base = self._model_combo_base_labels.get(repo) or repo.split('/')[-1]
            folder_name = repo.split('/')[-1]
            expected = DEFAULT_DOWNLOAD_PARENT / folder_name
            is_active = active_path is not None and active_path.name == folder_name
            is_installed = is_active or validate_model_dir(str(expected)) is not None
            if is_active:
                prefix = "▶ "
                self.model_select_combo.setItemData(i, bold_font, Qt.ItemDataRole.FontRole)
            elif is_installed:
                prefix = "● "
                self.model_select_combo.setItemData(i, normal_font, Qt.ItemDataRole.FontRole)
            else:
                prefix = "  "
                self.model_select_combo.setItemData(i, normal_font, Qt.ItemDataRole.FontRole)
            self.model_select_combo.setItemText(i, prefix + base)
        self.model_select_combo.blockSignals(False)

    def _check_selected_model_status(self, _idx: int = 0) -> None:
        target_path = self._get_selected_model_path()
        if not target_path: return
        is_installed = validate_model_dir(str(target_path)) is not None
        
        repo = self.model_select_combo.currentData()
        can_download = not is_installed and not (repo and str(repo).startswith("custom:"))
        self.btn_download.setEnabled(can_download)
            
        self._refresh_model_combo_badges()

    def _on_download_clicked(self) -> None:
        selected_repo = self.model_select_combo.currentData()
        if not selected_repo or selected_repo == "browse_custom" or str(selected_repo).startswith("custom:"): return
        target_path = self._get_selected_model_path()
        if not target_path: return
        is_installed = validate_model_dir(str(target_path)) is not None
        if not is_installed:
            model_name = self.model_select_combo.currentText().split(" (")[0]
            msg = t("settings.download_confirm_msg").format(model=model_name)
            reply = QMessageBox.question(self, t("settings.download_confirm_title"), msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            self.model_select_combo.setFocus()
            if reply == QMessageBox.StandardButton.Yes:
                self.download_model_requested.emit(str(DEFAULT_DOWNLOAD_PARENT), selected_repo)

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

    def _refresh_values(self):
        self.btn_hotkey.setText(self.settings.get("hotkey", "F9").upper())
        lang = self.settings.get("app_language", "en") or "en"
        lang_idx = self._lang_combo.findData(lang)
        if lang_idx >= 0:
            self._lang_combo.blockSignals(True)
            self._lang_combo.setCurrentIndex(lang_idx)
            self._lang_combo.blockSignals(False)
        current_dir = self.settings.get("model_dir")
        if current_dir:
            self._update_model_path_label(current_dir)
        else:
            self.lbl_model_path.setText(t("settings.path_not_selected"))
            self.lbl_model_path.setToolTip("")
        self._sync_combo_with_current_dir(current_dir)
        self._refresh_model_combo_badges()
        self._populate_compute_type_options()
        
        # Reflect schema/saved values back into dynamically-generated widgets.
        for key, widget in self._dynamic_widgets.items():
            val = self.settings.get(key)
            widget.blockSignals(True)
            if isinstance(widget, QComboBox):
                idx = widget.findData(val)
                if idx >= 0: widget.setCurrentIndex(idx)
            elif isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
                if val is not None: widget.setValue(val)
            elif isinstance(widget, QTextEdit):
                if val is not None: widget.setPlainText(str(val))
                parent_w = widget.parentWidget()
                if parent_w is not None:
                    btn = parent_w.findChild(QPushButton)
                    if btn:
                        btn.setEnabled(False)
            elif isinstance(widget, QLineEdit):
                if val is not None: widget.setText(str(val))
                parent_w = widget.parentWidget()
                if parent_w is not None:
                    btn = parent_w.findChild(QPushButton)
                    if btn:
                        btn.setEnabled(False)
            widget.blockSignals(False)
            
        self._load_prompt_for_language(self.settings.get("language", "auto"))

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
