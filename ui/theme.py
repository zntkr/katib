from pathlib import Path
import tempfile
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# 8-pt Grid System
G_1, G_2, G_3, G_4, G_5, G_6 = 8, 16, 24, 32, 40, 48

# Typography Scale
FONT_SIZE_SM = 8   # pt — log box, helper labels
FONT_SIZE_MD = 9   # pt — general UI default
FONT_SIZE_LG = 10  # pt — toolbar icons
FONT_SIZE_OSD = 14 # px — OSD overlay

# Panel Dimensions
PANEL_WIDTH = 320      # px — Dashboard and OSD
DIALOG_WIDTH = 384     # px — HelpWindow
SETTINGS_WIDTH  = 600  # px — SettingsDialog fixed width
SETTINGS_HEIGHT = 400  # px — SettingsDialog fixed height
WIDGET_WIDTH_SM = 80   # px — small button/combobox width in settings_dialog
COMBO_HEIGHT = G_4     # px — mic combo outer height (flush with buttons)
LOG_BOX_HEIGHT = 144   # px — dashboard log widget height
OSD_BOTTOM_MARGIN = 48 # px — OSD bottom offset (taskbar clearance)

# Palettes (Gruvbox Dark)
DARK_PALETTE = {
    # Functional states (Gruvbox Bright Variants)
    "CLR_OK":        "#b8bb26",  # Green
    "CLR_ERR":       "#fb4934",  # Red
    "CLR_WARN":      "#fe8019",  # Orange
    "CLR_WARN_DIM":  "#d65d0e",  # Dark Orange
    "CLR_INFO":      "#83a598",  # Blue
    "CLR_IDLE":      "#928374",  # Gray
    "CLR_FG2":       "#d5c4a1",  # Light Beige (fg2)
    "CLR_FG3":       "#bdae93",  # Beige (fg3)
    "CLR_LEVEL_LOW": "#b8bb26",
    "CLR_LEVEL_MID": "#fabd2f",  # Yellow
    "CLR_YELLOW":    "#d79921",  # mustard yellow (terminal accent)
    # Backgrounds — Gruvbox Hard elevation ladder
    "CLR_BG":          "#282828",  # bg0   (Medium) — main shell/ground
    "CLR_BG_DEEP":     "#1d2021",  # bg0_h (Hard)   — screen/void (terminal)
    "CLR_BG_SURFACE":  "#32302f",  # bg0_s (Soft)   — secondary layers
    "CLR_BG_ELEVATED": "#3c3836",  # bg1             — buttons/panels
    "CLR_BG_HOVER":    "#504945",  # bg2             — hover
    "CLR_BG_ACTIVE":   "#665c54",  # bg3             — pressed/active
    # Text — Gruvbox light hierarchy
    "CLR_TEXT":         "#ebdbb2",  # fg
    "CLR_TEXT_LABEL":   "#d5c4a1",  # fg1
    "CLR_TEXT_CONTENT": "#ebdbb2",  # fg
    "CLR_TEXT_STATUS":  "#a89984",  # fg4 (status text)
    "CLR_TEXT_MUTED":   "#928374",  # gray
    "CLR_TEXT_FAINT":   "#7c6f64",  # bg4
    "CLR_TEXT_CODE":    "#fabd2f",  # yellow
    # Borders
    "CLR_BORDER":       "#32302f",  # bg0_s — very subtle frame
    "CLR_BORDER_LIGHT": "#3c3836",  # bg1
    "CLR_HOVER_BORDER": "#d79921",  # mustard yellow
    "CLR_FOCUS_BORDER": "#fabd2f",  # yellow
    # Interaction
    "CLR_HOVER_BG":   "#504945",  # bg2
    "CLR_PRESSED_BG": "#1d2021",  # hard bg
    # Special backgrounds
    "CLR_TIP_BG":  "#3c3836",  # bg1
    "CLR_WARN_BG": "#32302f",  # bg0_s
    "CLR_CODE_BG": "#1d2021",  # hard bg
}


# Palettes (Gruvbox Light)
LIGHT_PALETTE = {
    # Functional states — Gruvbox Row 2 (bright) light, koyu temanın tam karşılığı
    "CLR_OK":        "#79740e",  # bright green light  ↔ #b8bb26 dark
    "CLR_ERR":       "#9d0006",  # bright red light    ↔ #fb4934 dark
    "CLR_WARN":      "#af3a03",  # bright orange light ↔ #fe8019 dark
    "CLR_WARN_DIM":  "#d65d0e",  # dark orange (aynı)
    "CLR_INFO":      "#076678",  # bright blue light   ↔ #83a598 dark
    "CLR_IDLE":      "#928374",  # gray (aynı)
    "CLR_FG2":       "#504945",  # fg2 light           ↔ #d5c4a1 dark
    "CLR_FG3":       "#665c54",  # fg3 light           ↔ #bdae93 dark
    "CLR_LEVEL_LOW": "#79740e",  # bright green light  ↔ #b8bb26 dark
    "CLR_LEVEL_MID": "#b57614",  # bright yellow light ↔ #fabd2f dark
    "CLR_YELLOW":    "#d79921",  # yellow row-1 (her iki modda aynı)
    # Backgrounds — scroll tutacağı (CLR_BG_ELEVATED) track'ten (CLR_BG_DEEP) koyu olmalı
    "CLR_BG":          "#fbf1c7",  # bg0   — main shell/ground
    "CLR_BG_DEEP":     "#f9f5d7",  # bg0_h — scroll track, log bg (çok açık)
    "CLR_BG_SURFACE":  "#f2e5bc",  # bg0_s — secondary layers
    "CLR_BG_ELEVATED": "#ebdbb2",  # bg1   — scroll handle, buttons (track'ten koyu = görünür)
    "CLR_BG_HOVER":    "#d5c4a1",  # bg2   — hover
    "CLR_BG_ACTIVE":   "#bdae93",  # bg3   — pressed/active
    # Text (dark on light)
    "CLR_TEXT":         "#3c3836",  # fg1
    "CLR_TEXT_LABEL":   "#504945",  # fg2
    "CLR_TEXT_CONTENT": "#3c3836",  # fg1
    "CLR_TEXT_STATUS":  "#7c6f64",  # fg4
    "CLR_TEXT_MUTED":   "#928374",  # gray
    "CLR_TEXT_FAINT":   "#a89984",  # bg4
    "CLR_TEXT_CODE":    "#b57614",  # yellow
    # Borders
    "CLR_BORDER":       "#f2e5bc",  # bg0_s light ↔ #32302f dark
    "CLR_BORDER_LIGHT": "#ebdbb2",  # bg1 light   ↔ #3c3836 dark
    "CLR_HOVER_BORDER": "#d79921",  # yellow row-1 (dark ile aynı)
    "CLR_FOCUS_BORDER": "#b57614",  # bright yellow light ↔ #fabd2f dark
    # Interaction
    "CLR_HOVER_BG":   "#d5c4a1",  # bg2 light ↔ #504945 dark
    "CLR_PRESSED_BG": "#f9f5d7",  # bg0_h light ↔ #1d2021 dark
    # Special backgrounds
    "CLR_TIP_BG":  "#f2e5bc",  # bg0_s
    "CLR_WARN_BG": "#f2e5bc",  # bg0_s
    "CLR_CODE_BG": "#ebdbb2",  # bg1
}


# Theme Manager
class ThemeManager:
    def __init__(self):
        self.is_dark = True
        self.palette = DARK_PALETTE

    def _resolve_is_dark(self, theme: str) -> bool:
        if theme == "light":
            return False
        if theme == "dark":
            return True
        scheme = QApplication.styleHints().colorScheme()
        return scheme != Qt.ColorScheme.Light

    def apply_theme(self, app: QApplication, theme: str = "system"):
        self.is_dark = self._resolve_is_dark(theme)
        self.palette = DARK_PALETTE if self.is_dark else LIGHT_PALETTE

        pal = app.palette()
        pal.setColor(QPalette.ColorRole.Window,     QColor(self.palette["CLR_BG"]))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(self.palette["CLR_TEXT"]))
        pal.setColor(QPalette.ColorRole.Base,       QColor(self.palette["CLR_BG_DEEP"]))
        pal.setColor(QPalette.ColorRole.Text,       QColor(self.palette["CLR_TEXT_CONTENT"]))
        app.setPalette(pal)
        app.setStyleSheet(self._generate_stylesheet())

    def _generate_stylesheet(self) -> str:
        p = self.palette

        suffix = "dark" if self.is_dark else "light"

        def _get_cached_svg(name: str, svg_str: str) -> str:
            cache_dir = Path(tempfile.gettempdir()) / "katib_theme_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            file_path = cache_dir / f"{name}_{suffix}.svg"
            if not file_path.exists() or file_path.read_text(encoding="utf-8") != svg_str:
                file_path.write_text(svg_str, encoding="utf-8")
            return f"url('{file_path.as_posix()}')"

        from ui.icons import ICN_TICK, ICN_DOWN, ICN_UP

        url_tick_yellow = _get_cached_svg("tick_yellow", ICN_TICK.replace("{color}", p['CLR_YELLOW']))
        url_down = _get_cached_svg("down", ICN_DOWN.replace("{color}", p['CLR_FG3']))
        url_down_disabled = _get_cached_svg("down_disabled", ICN_DOWN.replace("{color}", p['CLR_TEXT_MUTED']))
        url_down_hover = _get_cached_svg("down_hover", ICN_DOWN.replace("{color}", p['CLR_FG2']))
        url_up = _get_cached_svg("up", ICN_UP.replace("{color}", p['CLR_TEXT_MUTED']))

        return f"""
        * {{ font-family: 'Segoe UI', system-ui, sans-serif; font-size: {FONT_SIZE_MD}pt; outline: none; }}
        QWidget {{ color: {p['CLR_TEXT']}; }}
        QLabel, QCheckBox, QRadioButton {{ background: transparent; }}
        QFrame {{ border: none; }}

        QPushButton {{ background-color: {p['CLR_BG_ELEVATED']}; border: none; border-radius: 2px; padding: 4px 12px; color: {p['CLR_TEXT']}; min-height: 20px; }}
        QPushButton:hover {{ background-color: {p['CLR_BG_HOVER']}; }}
        QPushButton:pressed {{ background-color: {p['CLR_PRESSED_BG']}; }}
        QPushButton:disabled {{ color: {p['CLR_TEXT_MUTED']}; background-color: {p['CLR_BG_DEEP']}; }}
        QPushButton[isIconBtn="true"] {{ padding: 5px; }}

        QToolTip {{
            background-color: {p['CLR_BG_ELEVATED']};
            color: {p['CLR_TEXT_CONTENT']};
            border: 1px solid {p['CLR_BORDER_LIGHT']};
            border-radius: 2px;
            padding: 4px;
        }}

        QComboBox {{ background-color: {p['CLR_BG']}; border: 1px solid {p['CLR_BG_ACTIVE']}; border-radius: 2px; padding: 2px 24px 2px 8px; color: {p['CLR_FG3']}; min-height: 20px; combobox-popup: 0; }}
        QComboBox:hover {{ background-color: {p['CLR_BG_DEEP']}; border-color: {p['CLR_TEXT_STATUS']}; color: {p['CLR_FG2']}; }}
        QComboBox:focus {{ background-color: {p['CLR_BG_DEEP']}; border-color: {p['CLR_FOCUS_BORDER']}; color: {p['CLR_TEXT']}; }}
        QComboBox:disabled {{ color: {p['CLR_TEXT_MUTED']}; border-color: {p['CLR_BORDER']}; }}
        QComboBox:pressed {{ background-color: {p['CLR_PRESSED_BG']}; border-color: {p['CLR_TEXT_MUTED']}; color: {p['CLR_TEXT']}; }}
        QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 24px; border: none; }}
        QComboBox::down-arrow {{ image: {url_down}; width: 14px; height: 14px; }}
        QComboBox::down-arrow:hover, QComboBox::down-arrow:on, QComboBox::down-arrow:focus {{ image: {url_down_hover}; width: 14px; height: 14px; }}
        QComboBox::down-arrow:disabled {{ image: {url_down_disabled}; width: 14px; height: 14px; }}
        
        /* --- DROPDOWN MENU (Tactile / Floating Chip) --- */
        QComboBox QAbstractItemView {{ background-color: {p['CLR_BG_ELEVATED']}; border: 1px solid {p['CLR_BG_ACTIVE']}; border-radius: 2px; outline: none; padding: 0px; show-decoration-selected: 1; }}
        QComboBox QAbstractItemView::item {{ min-height: {G_3}px; max-height: {G_3}px; padding-left: {G_1}px; color: {p['CLR_TEXT']}; border-radius: 0px; margin: 0px; }}
        QComboBox QAbstractItemView::item:hover {{ background-color: {p['CLR_BG_HOVER']}; }}
        QComboBox QAbstractItemView::item:selected {{ background-color: {p['CLR_BG_ACTIVE']}; color: {p['CLR_TEXT']}; font-weight: bold; border-left: 2px solid {p['CLR_YELLOW']}; }}
        QComboBox QAbstractItemView::item:pressed {{ background-color: {p['CLR_PRESSED_BG']}; color: {p['CLR_TEXT']}; }}
        QComboBox QAbstractItemView QScrollBar:vertical {{ background-color: {p['CLR_BG_DEEP']}; }}

        QSpinBox, QDoubleSpinBox {{ background-color: {p['CLR_BG_ELEVATED']}; border: 1px solid {p['CLR_BORDER']}; border-radius: 2px; padding: 2px 4px; min-height: 20px; }}
        QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: {p['CLR_HOVER_BORDER']}; }}
        QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {p['CLR_FOCUS_BORDER']}; }}
        QSpinBox:pressed, QDoubleSpinBox:pressed {{ background-color: {p['CLR_PRESSED_BG']}; border-color: {p['CLR_TEXT_MUTED']}; }}

        QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right; width: 16px; border-left: 1px solid {p['CLR_BORDER']}; background-color: {p['CLR_BG_ELEVATED']}; }}
        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: {url_up}; width: 12px; height: 12px; }}
        QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right; width: 16px; border-left: 1px solid {p['CLR_BORDER']}; border-top: 1px solid {p['CLR_BORDER']}; background-color: {p['CLR_BG_ELEVATED']}; }}
        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: {url_down}; width: 12px; height: 12px; }}

        #log_box {{ 
            background-color: {p['CLR_BG_DEEP']}; 
            color: {p['CLR_TEXT_CONTENT']};
            border: 1px solid {p['CLR_BORDER_LIGHT']};
            border-radius: 2px;
        }}
        #log_box:hover {{ border-color: {p['CLR_TEXT_STATUS']}; }}

        QLineEdit, QTextEdit, QPlainTextEdit {{ 
            font-family: Consolas, 'Courier New', monospace; 
            font-size: {FONT_SIZE_SM}pt; 
            background-color: {p['CLR_BG_DEEP']}; 
            color: {p['CLR_TEXT_CONTENT']}; 
            border: 1px solid {p['CLR_BORDER_LIGHT']}; 
            border-radius: 2px; 
            padding: 4px 6px; 
            selection-background-color: {p['CLR_INFO']}; 
            selection-color: #ffffff; 
        }}
        QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{ border-color: {p['CLR_HOVER_BORDER']}; }}
        QPlainTextEdit:focus, QTextEdit:focus, QLineEdit:focus {{ border-color: {p['CLR_FOCUS_BORDER']}; }}

        QProgressBar {{ border: 1px solid {p['CLR_BORDER']}; border-radius: 2px; background: {p['CLR_BG_DEEP']}; text-align: center; }}
        QProgressBar::chunk {{ background-color: {p['CLR_LEVEL_LOW']}; border-radius: 2px; }}

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

        QTabWidget::pane {{ border: 1px solid {p['CLR_BORDER_LIGHT']}; border-radius: 2px; background-color: {p['CLR_BG']}; top: -1px; }}
        QTabBar::tab {{ background-color: {p['CLR_BG_ELEVATED']}; color: {p['CLR_TEXT_MUTED']}; border: 1px solid {p['CLR_BORDER']}; border-bottom: none; border-top-left-radius: 3px; border-top-right-radius: 3px; padding: 6px 16px; margin-right: 2px; }}
        QTabBar::tab:selected {{ background-color: {p['CLR_BG']}; color: {p['CLR_TEXT']}; border: 1px solid {p['CLR_BORDER_LIGHT']}; border-bottom: 1px solid {p['CLR_BG']}; font-weight: bold; }}
        QTabBar::tab:hover:!selected {{ background-color: {p['CLR_HOVER_BG']}; color: {p['CLR_TEXT']}; }}

        QCheckBox {{ spacing: 6px; }}
        QCheckBox::indicator {{ width: 13px; height: 13px; border: 1px solid {p['CLR_BORDER']}; border-radius: 2px; background-color: {p['CLR_BG_ELEVATED']}; }}
        QCheckBox::indicator:hover {{ border-color: {p['CLR_TEXT_STATUS']}; }}
        QCheckBox::indicator:checked {{ background-color: {p['CLR_BG_DEEP']}; border-color: transparent; image: {url_tick_yellow}; }}

        /* --- DASHBOARD BUTTON STATES --- */
        QPushButton#btn_settings[isActive="true"], QPushButton#btn_toggle_log[isActive="true"] {{ 
            background-color: {p['CLR_PRESSED_BG']}; 
        }}

        /* --- COMPONENTS (Settings Card) --- */
        QLabel#settingCardTitle {{ color: {p['CLR_YELLOW']}; font-weight: bold; font-size: {FONT_SIZE_SM}pt; letter-spacing: 1px; }}
        QFrame#settingCard {{ background-color: {p['CLR_BG']}; border-radius: 2px; border: 1px solid {p['CLR_BORDER_LIGHT']}; }}

        QFrame#settingCard QPushButton {{ background-color: {p['CLR_BG_ELEVATED']}; }}
        QFrame#settingCard QPushButton:hover {{ background-color: {p['CLR_BG_HOVER']}; }}
        QFrame#settingCard QPushButton:pressed {{ background-color: {p['CLR_PRESSED_BG']}; }}
        QFrame#settingCard QPushButton:disabled {{ background-color: {p['CLR_BG_DEEP']}; color: {p['CLR_TEXT_MUTED']}; }}
        QFrame#settingCard QSpinBox, QFrame#settingCard QDoubleSpinBox {{ background-color: {p['CLR_BG_DEEP']}; border: 1px solid {p['CLR_BORDER']}; }}
        QFrame#settingCard QSpinBox:hover, QFrame#settingCard QDoubleSpinBox:hover {{ background-color: {p['CLR_BG_DEEP']}; border-color: {p['CLR_HOVER_BORDER']}; }}
        QFrame#settingCard QSpinBox:focus, QFrame#settingCard QDoubleSpinBox:focus {{ background-color: {p['CLR_BG_DEEP']}; border-color: {p['CLR_FOCUS_BORDER']}; }}
        QFrame#settingCard QLineEdit {{ border: 1px solid {p['CLR_BORDER']}; }}
        QFrame#settingCard QLineEdit:hover {{ border-color: {p['CLR_HOVER_BORDER']}; }}
        QFrame#settingCard QLineEdit:focus {{ border-color: {p['CLR_FOCUS_BORDER']}; }}

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
            border-radius: 2px;
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
            background-color: {p['CLR_BORDER']};
            margin: 4px 8px;
        }}

        /* --- FINAL ENFORCEMENT --- */
        #DashboardWindow {{ background-color: {p['CLR_BG']}; }}
        #log_box {{ background-color: {p['CLR_BG_DEEP']}; }}
        #top_panel, #log_widget {{ background: transparent; }}
        """

theme_manager = ThemeManager()
