import asyncio
import pytest
from unittest.mock import MagicMock
import flet as ft
from src.repositories.hino_repository import HinoRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.views.home_view import HomeView


@pytest.mark.asyncio
async def test_home_view_build(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    home_view_obj = HomeView(hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)

    view = await home_view_obj.build(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/"
    assert len(view.controls) > 0
    assert home_view_obj.list_container is not None
    assert home_view_obj.main_content_container is not None
    assert home_view_obj.main_content_container.content == home_view_obj.list_container


@pytest.mark.asyncio
async def test_home_view_tab_switch(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    home_view_obj = HomeView(hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)
    await home_view_obj.build(mock_page)

    # Simula seleção da aba "Explorar"
    mock_event = MagicMock()
    mock_event.control.selected = ["explorar"]
    await home_view_obj._on_filter_select(mock_event)

    assert home_view_obj.main_content_container.content == home_view_obj.explore_container

    # Simula retorno para a aba "Todos"
    mock_event.control.selected = ["todos"]
    await home_view_obj._on_filter_select(mock_event)

    assert home_view_obj.main_content_container.content == home_view_obj.list_container


@pytest.mark.asyncio
async def test_home_view_tile_click_triggers_navigation(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    home_view_obj = HomeView(hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)
    mock_page.push_route = MagicMock()

    await home_view_obj.build(mock_page)

    # Simula renderização de um hino fictício
    from src.models.hino import Hino
    hino_sample = Hino(id=1, numero="1", titulo="Test Hymn")
    home_view_obj._render_hino_tiles([hino_sample])

    # Dispara o evento on_click do ListTile gerado
    assert home_view_obj.list_container is not None
    tile = home_view_obj.list_container.controls[0]
    assert isinstance(tile, ft.ListTile)
    mock_event = MagicMock(spec=ft.ControlEvent)
    on_click_handler = tile.on_click
    assert callable(on_click_handler)
    on_click_handler(mock_event)  # type: ignore

@pytest.mark.asyncio
async def test_home_view_search_persistence_and_clear(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    home_view_obj = HomeView(hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)

    await home_view_obj.build(mock_page)

    # Simula busca de usuário
    mock_event = MagicMock()
    mock_event.control.value = "Santo"
    home_view_obj._on_search_change(mock_event)
    assert home_view_obj.current_search == "Santo"
    assert home_view_obj.search_field is not None
    assert home_view_obj.search_field.suffix is not None

    # Simula reconstrução da view ao voltar do hino
    view = await home_view_obj.build(mock_page)
    assert home_view_obj.current_search == "Santo"
    assert home_view_obj.search_field is not None
    assert home_view_obj.search_field.value == "Santo"

@pytest.mark.asyncio
async def test_home_view_sorting_modes(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    home_view_obj = HomeView(hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)

    await home_view_obj.build(mock_page)

    hinos = await hino_repo.get_all()

    # num_asc (default)
    sorted_asc = home_view_obj._sort_hinos(hinos)
    assert sorted_asc[0].numero == "1"

    # num_desc
    home_view_obj.current_sort = "num_desc"
    sorted_desc = home_view_obj._sort_hinos(hinos)
    assert sorted_desc[0].numero == "3"

    # title_asc
    home_view_obj.current_sort = "title_asc"
    sorted_title_asc = home_view_obj._sort_hinos(hinos)
    assert sorted_title_asc[0].titulo.startswith("Ó") # Ó Adorai o Senhor vem antes de O Deus...
    assert sorted_title_asc[1].titulo.startswith("O")
    assert sorted_title_asc[2].titulo.startswith("Santo")

    # title_desc
    home_view_obj.current_sort = "title_desc"
    sorted_title_desc = home_view_obj._sort_hinos(hinos)
    assert sorted_title_desc[0].titulo.startswith("Santo")
    assert sorted_title_desc[1].titulo.startswith("O")
    assert sorted_title_desc[2].titulo.startswith("Ó")

    # Validação de parse_hino_number e format_hino_number para 587_A / 587_B
    from src.views.home_view import parse_hino_number, format_hino_number
    assert parse_hino_number("587") == 587.0
    assert parse_hino_number("587_A") == 587.1
    assert parse_hino_number("587_B") == 587.2
    assert parse_hino_number("588") == 588.0

    assert format_hino_number("587_A") == "587A"
    assert format_hino_number("587_B") == "587B"

    from src.models.hino import Hino
    hino_587 = Hino(id=587, numero="587", titulo="Hino 587")
    hino_587a = Hino(id=588, numero="587_A", titulo="Hino 587A")
    hino_587b = Hino(id=589, numero="587_B", titulo="Hino 587B")
    hino_588 = Hino(id=590, numero="588", titulo="Hino 588")

    sample_list = [hino_587a, hino_588, hino_587, hino_587b]

    home_view_obj.current_sort = "num_asc"
    sorted_sample_asc = home_view_obj._sort_hinos(sample_list)
    assert [h.numero for h in sorted_sample_asc] == ["587", "587_A", "587_B", "588"]

    home_view_obj.current_sort = "num_desc"
    sorted_sample_desc = home_view_obj._sort_hinos(sample_list)
    assert [h.numero for h in sorted_sample_desc] == ["588", "587_B", "587_A", "587"]


@pytest.mark.asyncio
async def test_home_view_category_filter(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    home_view_obj = HomeView(hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)

    await home_view_obj.build(mock_page)

    await home_view_obj._filter_by_categoria("Adoração")
    assert home_view_obj.current_filter == "categoria"
    assert home_view_obj.active_category == "Adoração"

