"""
SSOT/DRY refactoring tests.
Issue #4: FONT_SIZE_SM, Issue #5: WIDGET_WIDTH_SM, Issue #6: log level mapping.
"""
import pathlib
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt

ROOT = pathlib.Path(__file__).parent.parent


def _dummy_icon() -> QIcon:
    px = QPixmap(16, 16)
    px.fill(Qt.GlobalColor.transparent)
    return QIcon(px)


class TestFontSizeSM:
    """Issue #4: 8pt string literal → FONT_SIZE_SM constant."""

    def test_font_size_sm_constant_exists(self):
        from ui.theme import FONT_SIZE_SM
        assert FONT_SIZE_SM == 8

    def test_no_hardcoded_8pt_in_theme_stylesheet(self):
        src = (ROOT / "ui" / "theme.py").read_text(encoding="utf-8")
        assert "font-size: 8pt" not in src, \
            "ui/theme.py: use FONT_SIZE_SM constant instead of the 8pt literal"

    def test_no_hardcoded_8pt_in_settings_dialog(self):
        src = (ROOT / "ui" / "settings_dialog.py").read_text(encoding="utf-8")
        assert "font-size: 8pt" not in src, \
            "ui/settings_dialog.py: use FONT_SIZE_SM constant instead of the 8pt literal"


class TestWidgetWidthSM:
    """Issue #5: setFixedWidth(80) → WIDGET_WIDTH_SM constant."""

    def test_widget_width_sm_constant_exists(self):
        from ui.theme import WIDGET_WIDTH_SM
        assert WIDGET_WIDTH_SM == 80

    def test_no_hardcoded_width_80_in_settings_dialog(self):
        src = (ROOT / "ui" / "settings_dialog.py").read_text(encoding="utf-8")
        assert "setFixedWidth(80)" not in src, \
            "ui/settings_dialog.py: do not hardcode 80 — use WIDGET_WIDTH_SM or the grid system"


class TestLevelPaletteMapping:
    """Issue #6: Log level → color/CSS mapping must be derived from a single source."""

    def test_level_palette_key_constant_exists(self):
        import ui.dashboard as mod
        assert hasattr(mod, "_LEVEL_PALETTE_KEY"), \
            "ui/dashboard.py: _LEVEL_PALETTE_KEY must be a module-level constant"

    def test_level_palette_key_covers_all_levels(self):
        from ui.dashboard import _LEVEL_PALETTE_KEY
        expected = {"OK", "ERR", "WARN", "WRN", "IDLE", "...", "INFO", "↓"}
        assert expected == set(_LEVEL_PALETTE_KEY.keys())

    def test_level_palette_key_values_are_valid_palette_keys(self):
        from ui.dashboard import _LEVEL_PALETTE_KEY
        from ui.theme import DARK_PALETTE
        for level, palette_key in _LEVEL_PALETTE_KEY.items():
            assert palette_key in DARK_PALETTE, \
                f"_LEVEL_PALETTE_KEY[{level!r}] = {palette_key!r} is not present in the palette"

    def test_set_status_colors_match_level_palette_key(self, qapp, mock_settings):
        from ui.dashboard import DashboardWindow as Dashboard, _LEVEL_PALETTE_KEY
        from ui.theme import theme_manager
        from unittest.mock import patch
        with patch("ui.utils.colorize_svg_icon") as mock_colorize:
            mock_colorize.return_value = _dummy_icon()
            d = Dashboard(mock_settings, icon_idle=_dummy_icon())
            p = theme_manager.palette
            for level, palette_key in _LEVEL_PALETTE_KEY.items():
                d.set_status("test", level)
                expected_color = p[palette_key]
                assert mock_colorize.call_args[0][1] == expected_color, \
                    f"set_status(level={level!r}) did not produce the expected icon color ({expected_color})"

    def test_make_log_html_line_produces_inline_styles_for_all_levels(self, qapp, mock_settings):
        from ui.dashboard import DashboardWindow as Dashboard, _LEVEL_PALETTE_KEY
        d = Dashboard(mock_settings, icon_idle=_dummy_icon())
        for level in _LEVEL_PALETTE_KEY:
            html = d._make_log_html_line(level, "TST", "message", "00:00:00")
            assert "style=" in html and "color:" in html, \
                f"_make_log_html_line(level={level!r}) did not produce inline color styles"
