"""The one colour scheme (ui/theme.py): dark blue-grey, no light theme, no theme setting."""
import re
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QPalette

import ui.theme as theme
from ui.theme import PALETTE, theme_manager

ROOT = Path(__file__).resolve().parent.parent
BACKGROUNDS = [key for key in PALETTE if "_BG" in key] + ["CLR_BORDER", "CLR_BORDER_LIGHT"]
TEXTS = ["CLR_TEXT", "CLR_FG2", "CLR_FG3", "CLR_TEXT_STATUS"]
SIGNALS = ["CLR_OK", "CLR_ERR", "CLR_WARN", "CLR_INFO", "CLR_ACCENT"]
GREYS = TEXTS + ["CLR_TEXT_MUTED", "CLR_TEXT_FAINT"]


def _luminance(colour: str) -> float:
    """Relative luminance (WCAG 2)."""
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    q = QColor(colour)
    return 0.2126 * channel(q.red()) + 0.7152 * channel(q.green()) + 0.0722 * channel(q.blue())


def _contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


class TestOneDarkPalette:
    def test_the_manager_serves_the_one_palette(self):
        assert theme_manager.palette is PALETTE

    def test_there_is_no_light_theme(self):
        assert not hasattr(theme, "LIGHT_PALETTE")
        assert not hasattr(theme, "DARK_PALETTE")
        assert not hasattr(theme_manager, "is_dark")

    def test_theme_is_not_a_setting(self):
        from core.settings import DEFAULTS
        assert "theme" not in DEFAULTS

    @pytest.mark.parametrize("key", BACKGROUNDS)
    def test_backgrounds_are_dark(self, key):
        assert _luminance(PALETTE[key]) < 0.08, f"{key} is not a dark tone"

    @pytest.mark.parametrize("key", BACKGROUNDS)
    def test_backgrounds_lean_blue_not_brown(self, key):
        colour = QColor(PALETTE[key])
        assert colour.blue() > colour.green() >= colour.red(), f"{key} is not a blue-grey"

    @pytest.mark.parametrize("key", GREYS)
    def test_greys_for_text_lean_blue_too(self, key):
        colour = QColor(PALETTE[key])
        assert colour.blue() > colour.red()

    @pytest.mark.parametrize("key", TEXTS + SIGNALS)
    @pytest.mark.parametrize("ground", ["CLR_BG_DEEP", "CLR_BG", "CLR_BG_ELEVATED"])
    def test_text_and_state_colours_are_readable(self, key, ground):
        assert _contrast(PALETTE[key], PALETTE[ground]) >= 4.5, f"{key} on {ground}"

    @pytest.mark.parametrize("ground", ["CLR_BG_DEEP", "CLR_BG"])
    def test_secondary_text_is_readable_where_it_is_used(self, ground):
        assert _contrast(PALETTE["CLR_TEXT_MUTED"], PALETTE[ground]) >= 4.5

    def test_every_colour_is_a_hex_value(self):
        assert all(re.fullmatch(r"#[0-9a-f]{6}", value) for value in PALETTE.values())


class TestPaletteIsTheSingleSource:
    """A colour the code asks for must exist (a missing one fails only when that widget is
    built), and a colour nobody asks for must not stay in the palette."""

    @staticmethod
    def _used() -> set[str]:
        used = set()
        for source in [ROOT / "main.py", *(ROOT / "ui").glob("*.py")]:
            text = source.read_text(encoding="utf-8")
            if source.name == "theme.py":
                text = text.split("class ThemeManager", 1)[1]  # skip the definitions
            used.update(re.findall(r"CLR_[A-Z0-9_]+", text))
        return used

    def test_every_colour_the_code_uses_is_defined(self):
        assert self._used() - set(PALETTE) == set()

    def test_every_defined_colour_is_used(self):
        assert set(PALETTE) - self._used() == set()


class TestApplyTheme:
    def test_installs_the_palette_and_a_stylesheet(self, qapp):
        theme_manager.apply_theme(qapp)
        assert qapp.palette().color(QPalette.ColorRole.Window).name() == PALETTE["CLR_BG"]
        assert qapp.palette().color(QPalette.ColorRole.WindowText).name() == PALETTE["CLR_TEXT"]
        assert PALETTE["CLR_ACCENT"] in qapp.styleSheet()

    def test_arrow_icons_are_written_once_not_per_theme(self, qapp, tmp_path, monkeypatch):
        monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
        theme_manager.apply_theme(qapp)
        names = sorted(f.name for f in (tmp_path / "katib_theme_cache").iterdir())
        assert names == ["down.svg", "down_disabled.svg", "down_hover.svg"]
        assert PALETTE["CLR_FG3"] in (tmp_path / "katib_theme_cache" / "down.svg").read_text(encoding="utf-8")

    def test_the_stylesheet_names_no_colour_outside_the_palette(self, qapp):
        theme_manager.apply_theme(qapp)
        assert set(re.findall(r"#[0-9a-fA-F]{6}\b", qapp.styleSheet())) <= set(PALETTE.values())
