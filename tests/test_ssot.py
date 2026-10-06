"""Single-source-of-truth guards: values that must come from ui/theme.py, not from literals."""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).parent.parent


class TestFontSizeSM:
    def test_font_size_sm_constant_exists(self):
        from ui.theme import FONT_SIZE_SM
        assert FONT_SIZE_SM == 8

    @pytest.mark.parametrize("path", ["ui/theme.py", "ui/settings_window.py", "ui/help_window.py"])
    def test_no_hardcoded_8pt(self, path):
        src = (ROOT / path).read_text(encoding="utf-8")
        assert "font-size: 8pt" not in src, f"{path}: use FONT_SIZE_SM instead of the 8pt literal"


class TestColours:
    @pytest.mark.parametrize("path", ["main.py", "ui/settings_window.py", "ui/help_window.py",
                                      "ui/osd.py", "ui/tray_app.py", "ui/components.py"])
    def test_no_colour_literals_outside_the_palette(self, path):
        import re
        src = (ROOT / path).read_text(encoding="utf-8")
        assert re.findall(r"#[0-9a-fA-F]{6}\b", src) == [], f"{path}: take colours from ui/theme.py"
