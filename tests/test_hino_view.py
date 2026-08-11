import pytest
from unittest.mock import MagicMock
import flet as ft
from src.repositories.hino_repository import HinoRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.views.hino_view import (
    HinoView,
    DEFAULT_FONT_FAMILY,
    TIMES_NEW_ROMAN_FONT_FAMILY,
    OPENDYSLEXIC_FONT_FAMILY,
)


@pytest.mark.asyncio
async def test_hino_view_build_success(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    view_obj = HinoView(1, hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)

    view = await view_obj.build(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/hino/1"
    assert view_obj.letra_text is not None
    assert view_obj.font_size == 18


@pytest.mark.asyncio
async def test_hino_view_build_not_found(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    view_obj = HinoView(999, hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)

    view = await view_obj.build(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/hino/999"


@pytest.mark.asyncio
async def test_hino_view_font_accessibility_methods(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    view_obj = HinoView(1, hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)
    await view_obj.build(mock_page)

    view_obj._show_accessibility_modal(mock_page)
    assert view_obj.font_size_text is not None
    assert view_obj.font_size_text.value == "18pt"

    view_obj._increase_font(mock_page)
    assert view_obj.font_size == 20
    assert view_obj.font_size_text.value == "20pt"
    assert view_obj.is_custom_font is True
    mock_page.update.assert_called()

    view_obj._decrease_font(mock_page)
    assert view_obj.font_size == 18
    assert view_obj.font_size_text.value == "18pt"

    view_obj._set_font_family(mock_page, OPENDYSLEXIC_FONT_FAMILY)
    assert view_obj.selected_font == OPENDYSLEXIC_FONT_FAMILY

    view_obj._set_font_family(mock_page, TIMES_NEW_ROMAN_FONT_FAMILY)
    assert view_obj.selected_font == TIMES_NEW_ROMAN_FONT_FAMILY

    view_obj._reset_font(mock_page)
    assert view_obj.selected_font == DEFAULT_FONT_FAMILY
    assert view_obj.is_custom_font is False


def test_responsive_font_size_calculation(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    view_obj = HinoView(1, hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)

    # Celular (altura 600px) -> ~18pt
    mock_page.height = 600
    assert view_obj._calculate_responsive_font_size(mock_page) == 18

    # Tablet (altura 900px) -> ~23pt
    mock_page.height = 900
    assert view_obj._calculate_responsive_font_size(mock_page) == 23

    # Desktop / Monitor 4K (altura 1200px) -> ~31pt
    mock_page.height = 1200
    assert view_obj._calculate_responsive_font_size(mock_page) == 31


