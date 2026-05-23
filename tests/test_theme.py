from ui.theme import theme_manager, DARK_PALETTE

class TestThemeManager:
    def test_always_dark(self, qapp):
        theme_manager.apply_theme(qapp)
        assert theme_manager.is_dark is True
        assert theme_manager.palette is DARK_PALETTE
