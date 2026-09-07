from unittest.mock import MagicMock

import flet as ft
import pytest

from src.services.theme_service import (
    AMOLED_BG_COLOR,
    ThemeService,
)


@pytest.mark.asyncio
async def test_theme_service_default_state(in_memory_db):
    service = ThemeService(in_memory_db)
    is_amoled = await service.load_preferences()
    assert is_amoled is False
    assert service.is_amoled is False


@pytest.mark.asyncio
async def test_theme_service_save_and_load_amoled_preference(in_memory_db):
    service = ThemeService(in_memory_db)
    await service.save_preferences(True)
    assert service.is_amoled is True

    # Cria nova instância com mesmo banco para testar persistência
    service2 = ThemeService(in_memory_db)
    is_amoled_loaded = await service2.load_preferences()
    assert is_amoled_loaded is True
    assert service2.is_amoled is True

    # Desativa e salva
    await service2.save_preferences(False)
    assert service2.is_amoled is False

    service3 = ThemeService(in_memory_db)
    assert await service3.load_preferences() is False


def test_theme_service_apply_theme_system(in_memory_db):
    service = ThemeService(in_memory_db)
    service.is_amoled = False
    mock_page = MagicMock(spec=ft.Page)

    service.apply_theme(mock_page)

    assert mock_page.theme_mode == ft.ThemeMode.SYSTEM
    assert mock_page.bgcolor is None
    assert mock_page.theme is not None
    assert mock_page.theme.use_material3 is True
    assert mock_page.theme.color_scheme_seed == "#6750A4"
    assert mock_page.dark_theme is not None
    assert mock_page.dark_theme.use_material3 is True
    assert mock_page.dark_theme.color_scheme_seed == "#6750A4"
    assert "Helvetica" in mock_page.fonts
    assert "Montserrat" in mock_page.fonts
    assert "OpenDyslexic" in mock_page.fonts
    assert "Roboto" in mock_page.fonts
    assert "Inter" in mock_page.fonts


def test_theme_service_apply_theme_amoled(in_memory_db):
    service = ThemeService(in_memory_db)
    service.is_amoled = True
    mock_page = MagicMock(spec=ft.Page)

    service.apply_theme(mock_page)

    assert mock_page.theme_mode == ft.ThemeMode.DARK
    assert mock_page.bgcolor == AMOLED_BG_COLOR
    assert mock_page.dark_theme is not None
    assert mock_page.dark_theme.color_scheme.surface == AMOLED_BG_COLOR
    assert mock_page.dark_theme.system_overlay_style is not None
    assert mock_page.dark_theme.system_overlay_style.status_bar_color == AMOLED_BG_COLOR
    assert mock_page.theme is not None
    assert mock_page.theme != mock_page.dark_theme


@pytest.mark.asyncio
async def test_theme_service_toggle_amoled(in_memory_db):
    service = ThemeService(in_memory_db)
    mock_page = MagicMock(spec=ft.Page)

    await service.toggle_amoled(mock_page, True)
    assert service.is_amoled is True
    assert mock_page.theme_mode == ft.ThemeMode.DARK
    assert mock_page.bgcolor == AMOLED_BG_COLOR
    mock_page.update.assert_called_once()

    mock_page.reset_mock()
    await service.toggle_amoled(mock_page, False)
    assert service.is_amoled is False
    assert mock_page.theme_mode == ft.ThemeMode.SYSTEM
    assert mock_page.bgcolor is None
    mock_page.update.assert_called_once()


def test_theme_service_apply_theme_antigo_edition(in_memory_db):
    from src.services.theme_service import (
        ANTIGO_AMOLED_BG,
        ANTIGO_DARK_BG,
        ANTIGO_DARK_PRIMARY,
        ANTIGO_LIGHT_BG,
        ANTIGO_LIGHT_PRIMARY,
        EDITION_ANTIGO,
    )

    service = ThemeService(in_memory_db)
    mock_page = MagicMock(spec=ft.Page)

    # 1. Modo Sistema Hinário Antigo (Claro e Escuro configurados)
    service.is_amoled = False
    service.apply_theme(mock_page, edition=EDITION_ANTIGO)
    assert mock_page.theme_mode == ft.ThemeMode.SYSTEM
    assert mock_page.theme.color_scheme.surface == ANTIGO_LIGHT_BG
    assert mock_page.theme.color_scheme.primary == ANTIGO_LIGHT_PRIMARY
    assert mock_page.dark_theme.color_scheme.surface == ANTIGO_DARK_BG
    assert mock_page.dark_theme.color_scheme.primary == ANTIGO_DARK_PRIMARY

    # 2. Modo AMOLED Hinário Antigo (Preto Absoluto)
    service.is_amoled = True
    service.apply_theme(mock_page, edition=EDITION_ANTIGO)
    assert mock_page.theme_mode == ft.ThemeMode.DARK
    assert mock_page.bgcolor == ANTIGO_AMOLED_BG
    assert mock_page.dark_theme.color_scheme.surface == ANTIGO_AMOLED_BG
    assert mock_page.dark_theme.color_scheme.primary == ANTIGO_DARK_PRIMARY


@pytest.mark.asyncio
async def test_theme_service_seed_selection_and_persistence(in_memory_db):
    from src.services.theme_service import COLOR_SEEDS

    service = ThemeService(in_memory_db)
    mock_page = MagicMock(spec=ft.Page)

    assert service.current_seed == "purple"
    assert service.get_accent_color() == COLOR_SEEDS["purple"]["hex"]

    # Altera para Dourado Sacro
    await service.set_seed("gold", mock_page)
    assert service.current_seed == "gold"
    assert service.get_accent_color() == COLOR_SEEDS["gold"]["hex"]
    assert mock_page.theme.color_scheme_seed == COLOR_SEEDS["gold"]["hex"]
    mock_page.update.assert_called()

    # Verifica persistência ao recriar o serviço
    service2 = ThemeService(in_memory_db)
    await service2.load_preferences()
    assert service2.current_seed == "gold"
    assert service2.get_accent_color() == COLOR_SEEDS["gold"]["hex"]


@pytest.mark.asyncio
async def test_theme_service_theme_mode_selection(in_memory_db):
    service = ThemeService(in_memory_db)
    mock_page = MagicMock(spec=ft.Page)

    # Modo Claro
    await service.set_theme_mode("light", mock_page)
    assert service.theme_mode == "light"
    assert mock_page.theme_mode == ft.ThemeMode.LIGHT
    assert mock_page.bgcolor is None

    # Modo Escuro
    await service.set_theme_mode("dark", mock_page)
    assert service.theme_mode == "dark"
    assert mock_page.theme_mode == ft.ThemeMode.DARK

    # Persistência
    service2 = ThemeService(in_memory_db)
    await service2.load_preferences()
    assert service2.theme_mode == "dark"


@pytest.mark.asyncio
async def test_theme_service_font_family_selection(in_memory_db):
    service = ThemeService(in_memory_db)
    mock_page = MagicMock(spec=ft.Page)

    assert service.font_family == "Roboto"

    # Seleciona OpenDyslexic
    await service.set_font_family("OpenDyslexic", mock_page)
    assert service.font_family == "OpenDyslexic"
    assert mock_page.theme.font_family == "OpenDyslexic"
    assert mock_page.dark_theme.font_family == "OpenDyslexic"

    # Persistência
    service2 = ThemeService(in_memory_db)
    await service2.load_preferences()
    assert service2.font_family == "OpenDyslexic"

