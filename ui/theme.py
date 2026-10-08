from pathlib import Path
import tempfile
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication

# 8-pt Grid System
G_1, G_2, G_3, G_4, G_5, G_6 = 8, 16, 24, 32, 40, 48

# Typography Scale
FONT_SIZE_SM = 8   # pt — log box, helper labels
FONT_SIZE_MD = 9   # pt — general UI default
FONT_SIZE_LG = 10  # pt — toolbar icons
FONT_SIZE_OSD = 12 # px — OSD overlay

# Panel Dimensions
DIALOG_WIDTH = 384     # px — HelpWindow
SETTINGS_WIDTH  = 600  # px — SettingsWindow fixed width
SETTINGS_HEIGHT = 340  # px — SettingsWindow fixed height
OSD_TOP_MARGIN = 12 # px — OSD offset from the top of the screen

# The one colour scheme (ADR-0013): dark blue-grey. There is no light theme.
PALETTE = {
    # Functional states
    "CLR_OK":     "#3ecf8e",  # green — done, written
    "CLR_ERR":    "#f26d78",  # red — errors, recording
    "CLR_WARN":   "#f0a45b",  # orange — warnings, messages
    "CLR_INFO":   "#5cb8e6",  # cyan — in progress
    "CLR_ACCENT": "#6aa9ff",  # blue — the thing to look at or click
    # Backgrounds, darkest to lightest
    "CLR_PRESSED_BG":  "#0e1116",  # pressed controls
    "CLR_BG_DEEP":     "#12151b",  # window ground, text fields, log
    "CLR_BG":          "#1a1e26",  # panels, tab pages
    "CLR_BG_ELEVATED": "#262c38",  # buttons, popups
    "CLR_BG_HOVER":    "#313a49",  # hover
    "CLR_BG_ACTIVE":   "#3d485b",  # selected, active
    # Text, brightest to faintest
    "CLR_TEXT":        "#e4e8ef",  # primary text and content
    "CLR_FG2":         "#c9d0dc",  # control text on hover
    "CLR_FG3":         "#aab3c2",  # control text at rest
    "CLR_TEXT_STATUS": "#97a1b3",  # pill and status text
    "CLR_TEXT_MUTED":  "#8490a3",  # secondary text, idle icons
    "CLR_TEXT_FAINT":  "#586273",  # timestamps, disabled icons
    # Borders
    "CLR_BORDER":       "#232934",  # barely visible frame
    "CLR_BORDER_LIGHT": "#2d3542",  # visible frame
    "CLR_HOVER_BORDER": "#4f7fc0",  # field under the mouse
    "CLR_FOCUS_BORDER": "#6aa9ff",  # field with focus
}


class ThemeManager:
    """Holds the palette and installs it on the application. Widgets read `palette`."""

    def __init__(self):
        self.palette = PALETTE

    def apply_theme(self, app: QApplication):
        pal = app.palette()
        pal.setColor(QPalette.ColorRole.Window,     QColor(self.palette["CLR_BG"]))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(self.palette["CLR_TEXT"]))
        pal.setColor(QPalette.ColorRole.Base,       QColor(self.palette["CLR_BG_DEEP"]))
        pal.setColor(QPalette.ColorRole.Text,       QColor(self.palette["CLR_TEXT"]))
        app.setPalette(pal)
        app.setStyleSheet(self._generate_stylesheet())

    def _generate_stylesheet(self) -> str:
        p = self.palette

        def _get_cached_svg(name: str, svg_str: str) -> str:
            # QSS takes images by URL only, so the coloured arrow icons live in a temp folder.
            cache_dir = Path(tempfile.gettempdir()) / "katib_theme_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            file_path = cache_dir / f"{name}.svg"
            if not file_path.exists() or file_path.read_text(encoding="utf-8") != svg_str:
                file_path.write_text(svg_str, encoding="utf-8")
            return f"url('{file_path.as_posix()}')"

        from ui.icons import ICN_DOWN

        url_down = _get_cached_svg("down", ICN_DOWN.replace("{color}", p['CLR_FG3']))
        url_down_disabled = _get_cached_svg("down_disabled", ICN_DOWN.replace("{color}", p['CLR_TEXT_MUTED']))
        url_down_hover = _get_cached_svg("down_hover", ICN_DOWN.replace("{color}", p['CLR_FG2']))

        return f"""
        * {{ font-family: 'Segoe UI', system-ui, sans-serif; font-size: {FONT_SIZE_MD}pt; outline: none; }}
        QWidget {{ color: {p['CLR_TEXT']}; }}
        QLabel {{ background: transparent; }}
        QFrame {{ border: none; }}

        QPushButton {{ background-color: {p['CLR_BG_ELEVATED']}; border: none; border-radius: 4px; padding: 4px 12px; color: {p['CLR_TEXT']}; min-height: 20px; }}
        QPushButton:hover {{ background-color: {p['CLR_BG_HOVER']}; }}
        QPushButton:pressed {{ background-color: {p['CLR_PRESSED_BG']}; }}
        QPushButton:disabled {{ color: {p['CLR_TEXT_MUTED']}; background-color: {p['CLR_BG_DEEP']}; }}
        QPushButton[isIconBtn="true"] {{ padding: 5px; }}

        QToolTip {{
            background-color: {p['CLR_BG_ELEVATED']};
            color: {p['CLR_TEXT']};
            border: 1px solid {p['CLR_BORDER_LIGHT']};
            border-radius: 4px;
            padding: 4px;
        }}

        QComboBox {{ background-color: {p['CLR_BG_DEEP']}; border: 1px solid {p['CLR_BORDER_LIGHT']}; border-radius: 4px; padding: 2px 24px 2px 8px; color: {p['CLR_FG3']}; min-height: 20px; combobox-popup: 0; }}
        QComboBox:hover {{ border-color: {p['CLR_HOVER_BORDER']}; color: {p['CLR_FG2']}; }}
        QComboBox:focus {{ border-color: {p['CLR_FOCUS_BORDER']}; color: {p['CLR_TEXT']}; }}
        QComboBox:disabled {{ color: {p['CLR_TEXT_MUTED']}; border-color: {p['CLR_BORDER']}; }}
        QComboBox:pressed {{ background-color: {p['CLR_PRESSED_BG']}; border-color: {p['CLR_TEXT_MUTED']}; color: {p['CLR_TEXT']}; }}
        QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 24px; border: none; }}
        QComboBox::down-arrow {{ image: {url_down}; width: 14px; height: 14px; }}
        QComboBox::down-arrow:hover, QComboBox::down-arrow:on, QComboBox::down-arrow:focus {{ image: {url_down_hover}; width: 14px; height: 14px; }}
        QComboBox::down-arrow:disabled {{ image: {url_down_disabled}; width: 14px; height: 14px; }}

        /* --- DROPDOWN MENU --- */
        QComboBox QAbstractItemView {{ background-color: {p['CLR_BG_ELEVATED']}; border: 1px solid {p['CLR_BG_ACTIVE']}; border-radius: 4px; outline: none; padding: 0px; show-decoration-selected: 1; }}
        QComboBox QAbstractItemView::item {{ min-height: {G_3}px; max-height: {G_3}px; padding-left: {G_1}px; color: {p['CLR_TEXT']}; border-radius: 0px; margin: 0px; }}
        QComboBox QAbstractItemView::item:hover {{ background-color: {p['CLR_BG_HOVER']}; }}
        QComboBox QAbstractItemView::item:selected {{ background-color: {p['CLR_BG_ACTIVE']}; color: {p['CLR_TEXT']}; font-weight: bold; border-left: 2px solid {p['CLR_ACCENT']}; }}
        QComboBox QAbstractItemView::item:pressed {{ background-color: {p['CLR_PRESSED_BG']}; color: {p['CLR_TEXT']}; }}
        QComboBox QAbstractItemView QScrollBar:vertical {{ background-color: {p['CLR_BG_DEEP']}; }}

        #log_box {{
            background-color: {p['CLR_BG_DEEP']};
            color: {p['CLR_TEXT']};
            border: 1px solid {p['CLR_BORDER_LIGHT']};
            border-radius: 4px;
        }}

        QLineEdit, QTextEdit {{
            font-family: Consolas, 'Courier New', monospace;
            font-size: {FONT_SIZE_SM}pt;
            background-color: {p['CLR_BG_DEEP']};
            color: {p['CLR_TEXT']};
            border: 1px solid {p['CLR_BORDER_LIGHT']};
            border-radius: 4px;
            padding: 4px 6px;
            selection-background-color: {p['CLR_ACCENT']};
            selection-color: {p['CLR_PRESSED_BG']};
        }}
        QLineEdit:hover, QTextEdit:hover {{ border-color: {p['CLR_HOVER_BORDER']}; }}
        QLineEdit:focus, QTextEdit:focus {{ border-color: {p['CLR_FOCUS_BORDER']}; }}

        QProgressBar {{ border: none; border-radius: 4px; background: {p['CLR_BG_DEEP']}; text-align: center; }}
        QProgressBar::chunk {{ background-color: {p['CLR_ACCENT']}; border-radius: 4px; }}

        QScrollBar:vertical {{
            border: none;
            background-color: {p['CLR_BG_DEEP']};
            width: 8px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background-color: {p['CLR_BG_ELEVATED']};
            min-height: 24px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{ background-color: {p['CLR_BG_HOVER']}; }}
        QScrollBar::handle:vertical:pressed {{ background-color: {p['CLR_BG_ACTIVE']}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: none; background: none; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

        /* --- TABS: flat, the open one underlined in the accent colour --- */
        QTabWidget::pane {{ border: 1px solid {p['CLR_BORDER_LIGHT']}; border-radius: 4px; background-color: {p['CLR_BG']}; }}
        QTabBar::tab {{ background: transparent; color: {p['CLR_TEXT_MUTED']}; border: none; border-bottom: 2px solid transparent; padding: 6px 14px; margin-right: 2px; }}
        QTabBar::tab:selected {{ color: {p['CLR_TEXT']}; border-bottom: 2px solid {p['CLR_ACCENT']}; font-weight: bold; }}
        QTabBar::tab:hover:!selected {{ color: {p['CLR_FG2']}; }}

        /* --- COMPONENTS (Settings Card, used by the help window) --- */
        QLabel#settingCardTitle {{ color: {p['CLR_ACCENT']}; font-weight: bold; font-size: {FONT_SIZE_SM}pt; letter-spacing: 1px; }}
        QFrame#settingCard {{ background-color: {p['CLR_BG']}; border-radius: 4px; border: 1px solid {p['CLR_BORDER_LIGHT']}; }}

        /* --- TRAY / CONTEXT MENU --- */
        QMenu {{
            background-color: {p['CLR_BG_ELEVATED']};
            color: {p['CLR_TEXT']};
            border: 1px solid {p['CLR_BORDER_LIGHT']};
            border-radius: 4px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 24px 6px 12px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background-color: {p['CLR_BG_HOVER']};
            color: {p['CLR_TEXT']};
        }}
        QMenu::item:pressed {{
            background-color: {p['CLR_PRESSED_BG']};
        }}
        QMenu::item:disabled {{
            color: {p['CLR_TEXT_MUTED']};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {p['CLR_BORDER_LIGHT']};
            margin: 4px 8px;
        }}
        """

theme_manager = ThemeManager()
