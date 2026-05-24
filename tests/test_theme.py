from ui.theme import theme_manager, DARK_PALETTE, LIGHT_PALETTE


class TestThemeManager:
    def test_light_palette_has_all_dark_palette_keys(self):
        missing = set(DARK_PALETTE) - set(LIGHT_PALETTE)
        assert not missing, f"LIGHT_PALETTE eksik anahtarlar: {missing}"

    def test_apply_theme_dark_uses_dark_palette(self, qapp):
        theme_manager.apply_theme(qapp, "dark")
        assert theme_manager.is_dark is True
        assert theme_manager.palette is DARK_PALETTE

    def test_apply_theme_light_uses_light_palette(self, qapp):
        theme_manager.apply_theme(qapp, "light")
        assert theme_manager.is_dark is False
        assert theme_manager.palette is LIGHT_PALETTE

    def test_svg_cache_uses_dark_suffix(self, qapp, tmp_path, monkeypatch):
        monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
        theme_manager.apply_theme(qapp, "dark")
        cache = tmp_path / "katib_theme_cache"
        assert any("_dark" in f.name for f in cache.iterdir())

    def test_svg_cache_uses_light_suffix(self, qapp, tmp_path, monkeypatch):
        monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
        theme_manager.apply_theme(qapp, "light")
        cache = tmp_path / "katib_theme_cache"
        assert any("_light" in f.name for f in cache.iterdir())

    def test_settings_theme_default_is_system(self):
        from core.settings import SettingsManager
        sm = SettingsManager(in_memory=True)
        assert sm.get("theme") == "system"
