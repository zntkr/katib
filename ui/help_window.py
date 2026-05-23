from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QKeyEvent, QFont

from core.settings import APP_NAME
from core.i18n import t
from ui.theme import G_1, G_2, PANEL_WIDTH, FONT_SIZE_SM, theme_manager
from ui.components import SettingGroup
from ui.utils_win import apply_dark_mode_to_window


def _lbl(text: str, muted: bool = False, bold: bool = False, wrap: bool = True) -> QLabel:
    p = theme_manager.palette
    l = QLabel(text)
    l.setWordWrap(wrap)
    l.setMinimumWidth(10)
    color = p["CLR_TEXT_MUTED"] if muted else p["CLR_TEXT_CONTENT"]
    weight = "bold" if bold else "normal"
    l.setStyleSheet(f"color: {color}; font-weight: {weight};")
    return l


def _accent_block(lines: list[str]) -> QFrame:
    """Monospace block with a CLR_INFO accent bar on the left edge."""
    p = theme_manager.palette
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background-color: {p['CLR_BG_DEEP']};
            border: 1px solid {p['CLR_BORDER']};
            border-left: 3px solid {p['CLR_INFO']};
            border-radius: 2px;
        }}
        QLabel {{ background: transparent; border: none; }}
    """)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(G_2, G_1, G_2, G_1)
    lay.setSpacing(4)
    font = QFont("Consolas", FONT_SIZE_SM)
    for line in lines:
        lbl = QLabel(line)
        lbl.setFont(font)
        lbl.setStyleSheet(f"color: {p['CLR_TEXT_CONTENT']};")
        lay.addWidget(lbl)
    return frame


def _table(headers: list[str], rows: list[list[str]]) -> QFrame:
    """Simple QLabel grid table."""
    p = theme_manager.palette
    frame = QFrame()
    frame.setStyleSheet(f"background: transparent; border: none;")
    grid = QVBoxLayout(frame)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setSpacing(0)

    def _row(cells: list[str], is_header: bool = False) -> QWidget:
        w = QWidget()
        w.setStyleSheet(
            f"background-color: {p['CLR_BG_DEEP']}; border-bottom: 1px solid {p['CLR_BORDER']};"
            if is_header else
            f"background: transparent; border-bottom: 1px solid {p['CLR_BORDER_LIGHT']};"
        )
        h = QHBoxLayout(w)
        h.setContentsMargins(G_1, 4, G_1, 4)
        h.setSpacing(0)
        for i, cell in enumerate(cells):
            lbl = QLabel(cell)
            lbl.setWordWrap(False)
            lbl.setStyleSheet(
                f"color: {p['CLR_TEXT_MUTED']}; font-size: {FONT_SIZE_SM}pt; font-weight: bold; background: transparent; border: none;"
                if is_header else
                f"color: {p['CLR_TEXT_CONTENT']}; font-size: {FONT_SIZE_SM}pt; background: transparent; border: none;"
            )
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            h.addWidget(lbl)
        return w

    grid.addWidget(_row(headers, is_header=True))
    for i, row in enumerate(rows):
        r = _row(row)
        if i == len(rows) - 1:
            r.setStyleSheet("background: transparent; border: none;")
        grid.addWidget(r)

    outer = QFrame()
    outer.setStyleSheet(f"""
        QFrame {{
            border: 1px solid {p['CLR_BORDER']};
            border-radius: 2px;
            background: transparent;
        }}
    """)
    ol = QVBoxLayout(outer)
    ol.setContentsMargins(0, 0, 0, 0)
    ol.setSpacing(0)
    ol.addWidget(frame)
    return outer


class HelpWindow(QWidget):
    def __init__(self, settings=None, parent: QWidget | None = None):
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
        self.setWindowTitle(f"{APP_NAME} — {t('help.title')}")
        self.setFixedWidth(PANEL_WIDTH)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui()
        self.setMaximumHeight(640)
        self.adjustSize()

    def _hotkey(self) -> str:
        if self.settings is not None:
            return str(self.settings.get("hotkey") or "F9")
        return "F9"

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme_manager.palette["CLR_BG_DEEP"]))
        painter.end()
        super().paintEvent(event)

    def _build_ui(self):
        hk = self._hotkey()

        main = QVBoxLayout(self)
        main.setContentsMargins(G_1, G_1, 0, G_1)
        main.setSpacing(G_1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setObjectName("helpScrollArea")
        scroll.setStyleSheet("QScrollArea#helpScrollArea { background-color: transparent; }")

        container = QWidget()
        container.setObjectName("helpContainer")
        container.setStyleSheet("QWidget#helpContainer { background-color: transparent; }")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, G_1, G_2)
        layout.setSpacing(G_2)

        # ── How to Use ────────────────────────────────────────────────────
        grp_temel = SettingGroup(t("help.how_to_use"))
        steps = [
            t("help.step1"),
            t("help.step2").format(hotkey=hk),
            t("help.step3"),
        ]
        for s in steps:
            grp_temel.group_layout.addWidget(_lbl(s, muted=True))
        grp_temel.group_layout.addSpacing(G_1)
        grp_temel.group_layout.addWidget(_accent_block([
            t("help.status_rec"),
            t("help.status_writing"),
            t("help.status_warning"),
        ]))
        layout.addWidget(grp_temel)

        # ── Settings ──────────────────────────────────────────────────────
        grp_ayar = SettingGroup(t("help.settings_section"))

        grp_ayar.group_layout.addWidget(_lbl(t("help.hotkey_title"), bold=True))
        grp_ayar.group_layout.addWidget(_lbl(t("help.hotkey_desc"), muted=True))
        grp_ayar.group_layout.addSpacing(G_1)

        grp_ayar.group_layout.addWidget(_lbl(t("help.model_title"), bold=True))
        grp_ayar.group_layout.addWidget(_lbl(t("help.model_desc"), muted=True))
        grp_ayar.group_layout.addSpacing(G_1)
        grp_ayar.group_layout.addWidget(_table(
            [t("help.model.col_model"), t("help.model.col_size"), t("help.model.col_speed"), t("help.model.col_accuracy")],
            [
                ["tiny",     "~150 MB", t("help.model.speed_vfast"), t("help.model.acc_low")],
                ["base",     "~300 MB", t("help.model.speed_fast"),  t("help.model.acc_fair")],
                ["small ✓",  "~500 MB", t("help.model.speed_balanced"), t("help.model.acc_good")],
                ["medium",   "~1.5 GB", t("help.model.speed_slow"),  t("help.model.acc_high")],
                ["large-v3", "~3 GB",   t("help.model.speed_vslow"), t("help.model.acc_max")],
            ]
        ))
        grp_ayar.group_layout.addSpacing(G_1)

        grp_ayar.group_layout.addWidget(_lbl(t("help.ai_prompt_title"), bold=True))
        grp_ayar.group_layout.addWidget(_lbl(t("help.ai_prompt_desc"), muted=True))
        grp_ayar.group_layout.addWidget(_accent_block([
            t("help.ai_prompt_ex1"),
            t("help.ai_prompt_ex2"),
        ]))
        layout.addWidget(grp_ayar)

        # ── Troubleshooting ───────────────────────────────────────────────
        grp_sorun = SettingGroup(t("help.troubleshooting"))
        sorunlar = [
            (t("help.trouble_title1"), t("help.trouble_desc1")),
            (t("help.trouble_title2"), t("help.trouble_desc2")),
            (t("help.trouble_title3"), t("help.trouble_desc3")),
            (t("help.trouble_title4"), t("help.trouble_desc4").format(app=APP_NAME)),
            (t("help.trouble_title5"), t("help.trouble_desc5")),
        ]
        for title, desc in sorunlar:
            grp_sorun.group_layout.addWidget(_lbl(f"· {title}", bold=True))
            grp_sorun.group_layout.addWidget(_lbl(f"  {desc}", muted=True))
            grp_sorun.group_layout.addSpacing(G_1 // 2)
        layout.addWidget(grp_sorun)

        layout.addStretch()
        scroll.setWidget(container)
        main.addWidget(scroll)

    def show(self):
        try:
            apply_dark_mode_to_window(int(self.winId()))
        except Exception:
            pass
        super().show()
        self.raise_()
        self.activateWindow()

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.ActivationChange and not self.isActiveWindow():
            self.close()
        super().changeEvent(event)

    def closeEvent(self, event) -> None:
        """Stops active QTimers on teardown to prevent memory leaks."""
        for timer in self.findChildren(QTimer):
            if timer.isActive():
                timer.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
