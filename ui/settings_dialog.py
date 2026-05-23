from PySide6.QtWidgets import (
    QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QFrame, QFileDialog, QMessageBox, QLineEdit, QScrollArea,
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
from ui.theme import G_1, G_2, G_4, PANEL_WIDTH, FONT_SIZE_SM, WIDGET_WIDTH_SM, theme_manager
from ui.components import SettingGroup, NoScrollComboBox
from core.i18n import t, available_languages

class SettingsDialog(QDialog):
    hotkey_changed           = Signal(str)
    model_dir_changed        = Signal(str)
    model_reload_requested   = Signal()
    download_model_requested = Signal(str, str)
    log_entry                = Signal(str, str, str)
    capture_mode_changed     = Signal(bool)  # True=capture started, False=finished

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
        # The dialog container itself must be focusable: no child widget
        # highlights on open, but Tab navigation still works correctly.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowTitle(f"{APP_NAME} — {t('settings.title')}")
        self.setFixedWidth(PANEL_WIDTH)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._capturing_hotkey = False
        
        # Holds references to dynamically-generated UI widgets keyed by setting name.
        self._dynamic_widgets = {}

        self._build_ui()
        self.setMaximumHeight(704)
        self.adjustSize()

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

    def _build_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(G_1, G_1, 0, G_1)
        self.main_layout.setSpacing(G_1)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.scroll_area.setObjectName("settingsScrollArea")
        self.scroll_area.setStyleSheet("QScrollArea#settingsScrollArea { background-color: transparent; }")

        self.container = QWidget()
        self.container.setObjectName("settingsContainer")
        self.container.setStyleSheet("QWidget#settingsContainer { background-color: transparent; }")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, G_1, G_2)
        self.container_layout.setSpacing(G_2)

        # --- GROUP: GENERAL ---
        genel_grp = SettingGroup(t("settings.group_general"))
        self.btn_hotkey = QPushButton()
        self.btn_hotkey.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hotkey.clicked.connect(self._start_hotkey_capture)
        genel_grp.add_widget_row(t("settings.hotkey_label"), self.btn_hotkey, widget_width=80)

        self._chk_startup = QCheckBox()
        self._chk_startup.setCursor(Qt.CursorShape.PointingHandCursor)
        self._chk_startup.toggled.connect(self._on_startup_toggled)

        chk_lay = QHBoxLayout()
        chk_lay.setContentsMargins(0, 0, 0, 0)
        chk_lay.setSpacing(G_1)
        chk_lbl = QLabel(t("settings.startup_label"))
        chk_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        chk_lbl.mousePressEvent = lambda e: self._chk_startup.toggle()
        chk_lbl.setWordWrap(True)
        chk_lbl.setMinimumWidth(10)
        chk_lbl.setStyleSheet(f"color: {theme_manager.palette['CLR_TEXT_MUTED']};")
        chk_lay.addWidget(chk_lbl, stretch=1)
        chk_lay.addStretch()
        chk_lay.addWidget(self._chk_startup)
        genel_grp.group_layout.addLayout(chk_lay)

        self._lang_combo = NoScrollComboBox()
        for name, code in available_languages():
            self._lang_combo.addItem(name, userData=code)
        self._lang_combo.currentIndexChanged.connect(self._on_app_language_changed)
        self._btn_restart = QPushButton(t("settings.restart_now"))
        self._btn_restart.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_restart.setEnabled(False)
        self._btn_restart.clicked.connect(self._restart_app)
        lang_widget = QWidget()
        lang_lay = QHBoxLayout(lang_widget)
        lang_lay.setContentsMargins(0, 0, 0, 0)
        lang_lay.setSpacing(G_1)
        lang_lay.addWidget(self._lang_combo, 1)
        lang_lay.addWidget(self._btn_restart)
        genel_grp.add_widget_row(t("settings.app_language_label"), lang_widget, full_width=True)
        self.container_layout.addWidget(genel_grp)

        # --- GROUP: MODEL ---
        model_grp = SettingGroup(t("settings.group_model"))
        self.model_select_combo = NoScrollComboBox()
        self._model_combo_base_labels: dict[str, str] = {}
        for key, info in WHISPER_MODELS.items():
            label = f"{key.capitalize()} ({info['size']}) — {info['desc']}"
            self._model_combo_base_labels[info['repo_id']] = label
            self.model_select_combo.addItem(label, userData=info['repo_id'])
        
        # Action item — italic font only, no decoration or indent.
        self.model_select_combo.addItem(t("settings.browse"), userData="browse_custom")
        browse_idx = self.model_select_combo.count() - 1
        action_font = QFont()
        action_font.setItalic(True)
        self.model_select_combo.setItemData(browse_idx, action_font, Qt.ItemDataRole.FontRole)
        
        self.model_select_combo.currentIndexChanged.connect(self._on_combo_index_changed)
        
        self.btn_download = QPushButton(t("settings.download"))
        self.btn_download.setFixedWidth(WIDGET_WIDTH_SM)
        self.btn_download.clicked.connect(self._on_download_clicked)
        dl_widget = QWidget()
        dl_lay = QHBoxLayout(dl_widget)
        dl_lay.setContentsMargins(0,0,0,0)
        dl_lay.setSpacing(G_1)
        dl_lay.addWidget(self.model_select_combo, 1)
        dl_lay.addWidget(self.btn_download)
        model_grp.add_widget_row(t("settings.ai_model_label"), dl_widget, full_width=True)
        
        self.lbl_model_path = QLabel(t("settings.path_not_selected"))
        self.lbl_model_path.setStyleSheet(f"color: {theme_manager.palette['CLR_TEXT_MUTED']}; font-size: {FONT_SIZE_SM}pt; padding-left: 4px;")
        self.lbl_model_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_model_path.setMinimumWidth(10)
        model_grp.group_layout.addWidget(self.lbl_model_path)
        self.container_layout.addWidget(model_grp)

        # --- GROUP: PROCESSING ---

        adv_grp = SettingGroup(t("settings.group_processing"))

        # Data-driven UI: widgets are generated automatically from the settings schema.
        for sdef in SETTINGS_SCHEMA:
            if sdef.ui_group != "Processing":
                continue
                
            widget = None
            real_input_widget = None
            full_width = sdef.ui_kwargs.get("full_width", False)
            
            if sdef.ui_widget == "combobox":
                widget = NoScrollComboBox()
                for label, val in sdef.ui_kwargs.get("options", []):
                    widget.addItem(label, userData=val)
                widget.currentIndexChanged.connect(lambda idx, key=sdef.key, w=widget: self._on_dynamic_changed(key, w.currentData()))
                
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
                
                le = QLineEdit()
                le.setMinimumWidth(50)
                le.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                
                btn_save = QPushButton(t("settings.save"))
                btn_save.setFixedWidth(72)
                btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_save.setEnabled(False)  # disabled initially
                
                def _make_save_handler(k, input_w, btn):
                    def on_text_changed(text):
                        is_changed = text != self.settings.get(k, "")
                        btn.setEnabled(is_changed)
                        if is_changed and btn.text() == "✓":
                            btn.setText(t("settings.save"))
                            
                    def on_save():
                        if not btn.isEnabled(): return
                        self._on_dynamic_changed(k, input_w.text())
                        btn.setText("✓")
                        btn.setEnabled(False)
                        QTimer.singleShot(1500, lambda: btn.setText(t("settings.save")) if not btn.isEnabled() else None)
                    return on_text_changed, on_save
                    
                text_handler, save_handler = _make_save_handler(sdef.key, le, btn_save)
                le.textChanged.connect(text_handler)
                btn_save.clicked.connect(save_handler)
                le.returnPressed.connect(save_handler)  # pressing Enter also saves
                
                hlay.addWidget(le)
                hlay.addWidget(btn_save)
                
                widget = container
                real_input_widget = le
                
            elif sdef.ui_widget == "custom":
                # Widgets with custom business logic are still defined manually.
                if sdef.key == "compute_type":
                    self.compute_combo = NoScrollComboBox()
                    self.compute_combo.currentIndexChanged.connect(self._on_compute_type_changed)
                    widget = self.compute_combo
            
            if widget:
                real_widget = real_input_widget if real_input_widget is not None else widget
                if sdef.tooltip:
                    real_widget.setToolTip(t(sdef.tooltip))
                w = 80 if not full_width else 136
                adv_grp.add_widget_row(t(sdef.ui_label), widget, full_width=full_width, widget_width=w)
                self._dynamic_widgets[sdef.key] = real_widget

        self.container_layout.addWidget(adv_grp)

        # --- GROUP: SYSTEM ---
        system_grp = SettingGroup(t("settings.group_system"))
        btn_help = QPushButton(t("settings.user_guide"))
        btn_help.clicked.connect(self._open_help)
        system_grp.group_layout.addWidget(btn_help)

        btn_logs = QPushButton(t("settings.open_log_folder"))
        btn_logs.clicked.connect(self._open_log_folder)
        system_grp.group_layout.addWidget(btn_logs)

        btn_reset = QPushButton(t("settings.reset_settings"))
        btn_reset.clicked.connect(self._reset_advanced)
        system_grp.group_layout.addWidget(btn_reset)
        self.container_layout.addWidget(system_grp)

        self.container_layout.addStretch()  # push all items to the top
        self.scroll_area.setWidget(self.container)
        self.main_layout.addWidget(self.scroll_area)


        # Re-apply after the expanding policy overrides the 80 px fixed width on btn_hotkey.
        # language and compute_combo are now full_width=True, so the 80 px override is removed.
        self.btn_hotkey.setFixedWidth(WIDGET_WIDTH_SM)

    def _on_dynamic_changed(self, key: str, value):
        self.settings.set(key, value)

    def _on_app_language_changed(self, _idx: int) -> None:
        code = self._lang_combo.currentData()
        if code:
            self.settings.set("app_language", code)
            self._btn_restart.setEnabled(True)
            self.log_entry.emit("...", "APP", t("settings.restart_for_language"))

    def _restart_app(self) -> None:
        import sys
        import subprocess
        subprocess.Popen([sys.executable] + sys.argv)
        app = QApplication.instance()
        if app:
            app.quit()

    def _on_startup_toggled(self, checked: bool) -> None:
        try:
            from core.startup import set_startup_enabled
            set_startup_enabled(checked)
            status = t("settings.startup_enabled") if checked else t("settings.startup_disabled")
            self.log_entry.emit("...", "APP", f"Launch on startup: {status}")
        except Exception as e:
            self.log_entry.emit("ERR", "APP", f"Startup setting could not be changed: {e}")

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
        elided = fm.elidedText(path, Qt.TextElideMode.ElideMiddle, 260)
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
        
        self.btn_download.setText(t("settings.download"))
        repo = self.model_select_combo.currentData()
        if repo and str(repo).startswith("custom:"):
            self.btn_download.setEnabled(False)
        else:
            self.btn_download.setEnabled(not is_installed)
            
        self._refresh_model_combo_badges()

    def _on_download_clicked(self) -> None:
        selected_repo = self.model_select_combo.currentData()
        if not selected_repo or selected_repo == "browse_custom" or str(selected_repo).startswith("custom:"): return
        target_path = self._get_selected_model_path()
        if not target_path: return
        is_installed = validate_model_dir(str(target_path)) is not None
        if not is_installed:
            reply = QMessageBox.question(self, t("settings.download_confirm_title"), t("settings.download_confirm_msg"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
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
            elif isinstance(widget, QLineEdit):
                if val is not None: widget.setText(str(val))
                # Reset the Save button to its initial (disabled) state.
                parent_w = widget.parentWidget()
                if parent_w is not None:
                    btn = parent_w.findChild(QPushButton)
                    if btn:
                        btn.setEnabled(False)
                        btn.setText(t("settings.save"))
            widget.blockSignals(False)
            
        try:
            from core.startup import get_startup_enabled
            self._chk_startup.blockSignals(True)
            self._chk_startup.setChecked(get_startup_enabled())
            self._chk_startup.blockSignals(False)
        except Exception:
            pass

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
        if active: self.btn_download.setText(t("settings.downloading"))

    def on_download_complete(self, model_dir: str) -> None:
        self._update_model_path_label(model_dir)
        self._sync_combo_with_current_dir(model_dir)
        self._check_selected_model_status()
