import re

with open('c:/Projeler/katib/ui/control_center.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Rename class
text = text.replace('class SettingsDialog(QDialog):', 'class ControlCenterWindow(QDialog):')
text = text.replace('APP_NAME + \" - \" + t(\"settings.title\")', 'APP_NAME + \" - Control Center\"')

# 2. Add imports
text = text.replace('QTextEdit,', 'QTextEdit, QTabWidget, QProgressBar, QTextBrowser,')

# 3. Modify _build_ui
old_build_ui = '''        outer = QVBoxLayout(self)
        outer.setContentsMargins(G_4, G_4, G_4, G_4)
        outer.setSpacing(0)

        cols = QHBoxLayout()
        cols.setSpacing(0)
        outer.addLayout(cols)

        # Left column: General + System
        left = QVBoxLayout()
        left.setSpacing(G_1)
        left.setContentsMargins(0, 0, G_2, 0)
        cols.addLayout(left, 1)'''

new_build_ui = '''        outer = QVBoxLayout(self)
        outer.setContentsMargins(G_2, G_2, G_2, G_2)
        outer.setSpacing(G_2)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)

        tab_general = QWidget()
        left = QVBoxLayout(tab_general)
        left.setSpacing(G_1)
        left.setContentsMargins(G_2, G_2, G_2, G_2)
        self.tabs.addTab(tab_general, "Genel")'''
text = text.replace(old_build_ui, new_build_ui)

old_divider = '''        # Divider
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet(
            f"background-color: {p['CLR_BORDER_LIGHT']}; border: none;"
        )
        cols.addWidget(divider)

        # Right column: Model + Processing
        right = QVBoxLayout()
        right.setSpacing(G_1)
        right.setContentsMargins(G_2, 0, 0, 0)
        cols.addLayout(right, 1)'''

new_divider = '''        left.addStretch(1)

        tab_model = QWidget()
        right = QVBoxLayout(tab_model)
        right.setSpacing(G_1)
        right.setContentsMargins(G_2, G_2, G_2, G_2)
        self.tabs.addTab(tab_model, "Model & Donaným")'''
text = text.replace(old_divider, new_divider)

# 4. Add progress bar for downloads
old_model_row = '''        model_row = QHBoxLayout()
        model_row.setSpacing(G_1)
        model_row.addWidget(self.model_select_combo, 1)
        model_row.addWidget(self.btn_download)
        right.addLayout(model_row)

        self.lbl_model_path = QLabel(t("settings.path_not_selected"))'''

new_model_row = '''        model_row = QHBoxLayout()
        model_row.setSpacing(G_1)
        model_row.addWidget(self.model_select_combo, 1)
        model_row.addWidget(self.btn_download)
        right.addLayout(model_row)
        
        self.dl_progress = QProgressBar()
        self.dl_progress.setTextVisible(True)
        self.dl_progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dl_progress.setFixedHeight(20)
        self.dl_progress.hide()
        right.addWidget(self.dl_progress)

        self.lbl_model_path = QLabel(t("settings.path_not_selected"))'''
text = text.replace(old_model_row, new_model_row)

# 5. Add Logs tab at the end of _build_ui
old_build_ui_end = '''            if sdef.ui_widget == "combobox":
                right.addLayout(self._make_row(t(sdef.label_key), widget))
            else:
                right.addWidget(QLabel(t(sdef.label_key)))
                right.addWidget(real_input_widget)
                if not full_width:
                    right.addSpacing(G_2)'''

new_build_ui_end = '''            if sdef.ui_widget == "combobox":
                right.addLayout(self._make_row(t(sdef.label_key), widget))
            else:
                right.addWidget(QLabel(t(sdef.label_key)))
                right.addWidget(real_input_widget)
                if not full_width:
                    right.addSpacing(G_2)
        
        right.addStretch(1)
        
        # Tab 3: Logs
        tab_logs = QWidget()
        logs_layout = QVBoxLayout(tab_logs)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs.addTab(tab_logs, "Kayýtlar (Logs)")
        
        self.log_display = QTextBrowser()
        self.log_display.setOpenExternalLinks(False)
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("background-color: #0d0d0d; color: #d0d0d0; font-family: Consolas, monospace; font-size: 10pt; border: none; padding: 4px;")
        logs_layout.addWidget(self.log_display)'''
text = text.replace(old_build_ui_end, new_build_ui_end)

with open('c:/Projeler/katib/ui/control_center.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Patching complete.")
