import pytest
from unittest.mock import MagicMock
import flet as ft
from src.services.theme_service import (
    ThemeService,
    PREF_THEME_KEY,
    AMOLED_BG_COLOR,
    AMOLED_SURFACE_COLOR,
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
    assert mock_page.dark_theme is None


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
