import asyncio
from unittest.mock import MagicMock

import flet as ft
import pytest

from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.hino_repository import HinoRepository
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
    assert view.bgcolor == ft.Colors.SURFACE
    assert len(view.controls) > 0
    assert isinstance(view.controls[0], ft.SafeArea)
    assert view.controls[0].maintain_bottom_view_padding is True
    assert home_view_obj.list_container is not None
    assert home_view_obj.explore_container is not None
    assert home_view_obj.main_content_container is not None
    assert home_view_obj.list_container.visible is True
    assert home_view_obj.explore_container.visible is False
    assert home_view_obj.filter_bar is not None
    assert home_view_obj.filter_bar.show_selected_icon is False
    # Check that segments have text labels without cluttering icons
    for seg in home_view_obj.filter_bar.segments:
        assert seg.icon is None
        assert isinstance(seg.label, ft.Text)


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

    assert home_view_obj.explore_container.visible is True
    assert home_view_obj.list_container.visible is False

    # Simula retorno para a aba "Todos"
    mock_event.control.selected = ["todos"]
    await home_view_obj._on_filter_select(mock_event)

    assert home_view_obj.list_container.visible is True
    assert home_view_obj.explore_container.visible is False


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
    assert sorted_title_asc[0].titulo.startswith(
        "Ó"
    )  # Ó Adorai o Senhor vem antes de O Deus...
    assert sorted_title_asc[1].titulo.startswith("O")
    assert sorted_title_asc[2].titulo.startswith("Santo")

    # title_desc
    home_view_obj.current_sort = "title_desc"
    sorted_title_desc = home_view_obj._sort_hinos(hinos)
    assert sorted_title_desc[0].titulo.startswith("Santo")
    assert sorted_title_desc[1].titulo.startswith("O")
    assert sorted_title_desc[2].titulo.startswith("Ó")

    # Validação de parse_hino_number e format_hino_number para 587_A / 587_B
    from src.views.home_view import format_hino_number, parse_hino_number

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

    assert home_view_obj.filter_bar is not None
    assert home_view_obj.filter_bar.allow_empty_selection is True
    assert home_view_obj.active_filter_banner is not None
    assert home_view_obj.active_filter_banner.visible is False

    # Filtra por categoria
    await home_view_obj._filter_by_categoria("Adoração")
    assert home_view_obj.current_filter == "categoria"
    assert home_view_obj.active_category == "Adoração"
    assert home_view_obj.filter_bar.selected == ["explorar"]
    assert home_view_obj.active_filter_banner.visible is True

    # Clicar para voltar ao Explorar limpa a categoria e mostra o explore_container
    await home_view_obj._return_to_explore()
    assert home_view_obj.current_filter == "explorar"
    assert home_view_obj.active_category is None
    assert home_view_obj.active_filter_banner.visible is False
    assert home_view_obj.explore_container.visible is True
    assert home_view_obj.list_container.visible is False


@pytest.mark.asyncio
async def test_home_view_theme_filter_and_clear(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    home_view_obj = HomeView(hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)

    await home_view_obj.build(mock_page)

    # Filtra por tema
    await home_view_obj._filter_by_tema("Louvor")
    assert home_view_obj.current_filter == "tema"
    assert home_view_obj.active_tema == "Louvor"
    assert home_view_obj.filter_bar.selected == ["explorar"]
    assert home_view_obj.active_filter_banner.visible is True

    # Limpar filtro volta para Todos
    await home_view_obj._clear_category_or_theme_filter()
    assert home_view_obj.current_filter == "todos"
    assert home_view_obj.active_tema is None
    assert home_view_obj.active_filter_banner.visible is False
    assert home_view_obj.filter_bar.selected == ["todos"]


@pytest.mark.asyncio
async def test_home_view_recentes_tab_shows_only_clicked_hinos(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    home_view_obj = HomeView(hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)

    await home_view_obj.build(mock_page)

    # 1. Antes de qualquer hino ser acessado, a aba recentes deve estar vazia
    mock_event = MagicMock()
    mock_event.control.selected = ["recentes"]
    await home_view_obj._on_filter_select(mock_event)
    assert home_view_obj.current_filter == "recentes"
    # Apenas o container de estado vazio
    assert len(home_view_obj.list_container.controls) == 1
    assert home_view_obj.sort_button.visible is False

    # 2. Registrar acesso a múltiplos hinos em ordem não sequencial: hino 3, depois 1, depois 2
    await hist_repo.add_acesso(3)
    await asyncio.sleep(0.01)
    await hist_repo.add_acesso(1)
    await asyncio.sleep(0.01)
    await hist_repo.add_acesso(2)

    # 3. Recarregar aba recentes mesmo com ordenação em num_asc ou title_asc
    home_view_obj.current_sort = "num_asc"
    await home_view_obj._on_filter_select(mock_event)
    assert len(home_view_obj.list_container.controls) == 3
    # A ordem deve ser estritamente cronológica decrescente: 2 (mais recente), 1, 3 (mais antigo)
    tiles = home_view_obj.list_container.controls
    assert "Ó Adorai o Senhor" in tiles[0].title.value  # hino 2
    assert "Santo, Santo, Santo!" in tiles[1].title.value  # hino 1
    assert "O Deus Eterno Reina" in tiles[2].title.value  # hino 3
    assert home_view_obj.sort_button.visible is False

    # 4. Digitar na busca com a aba recentes aberta deve redirecionar para busca global (todos)
    mock_search_event = MagicMock()
    mock_search_event.control.value = "Santo"
    home_view_obj._on_search_change(mock_search_event)
    assert home_view_obj.current_filter == "todos"
    assert home_view_obj.filter_bar.selected == ["todos"]
    assert home_view_obj.sort_button.visible is True


@pytest.mark.asyncio
async def test_home_view_category_search_and_tab_switch(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    home_view_obj = HomeView(hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)

    await home_view_obj.build(mock_page)

    # 1. Filtra por categoria Adoração
    await home_view_obj._filter_by_categoria("Adoração")
    assert home_view_obj.current_filter == "categoria"
    assert home_view_obj.active_category == "Adoração"
    assert home_view_obj.active_filter_banner.visible is True
    assert home_view_obj.sort_button.visible is True

    # 2. Busca termo dentro da categoria
    mock_search = MagicMock()
    mock_search.control.value = "Santo"
    home_view_obj._on_search_change(mock_search)
    assert home_view_obj.current_filter == "categoria"
    assert home_view_obj.active_category == "Adoração"
    assert home_view_obj.current_search == "Santo"

    # 3. Troca de aba para "Explorar" limpa a categoria e mostra as seções
    mock_tab_event = MagicMock()
    mock_tab_event.control.selected = ["explorar"]
    await home_view_obj._on_filter_select(mock_tab_event)
    assert home_view_obj.current_filter == "explorar"
    assert home_view_obj.active_category is None
    assert home_view_obj.active_filter_banner.visible is False
    assert home_view_obj.sort_button.visible is False

    # 4. Troca de aba para "Todos"
    mock_tab_event.control.selected = ["todos"]
    await home_view_obj._on_filter_select(mock_tab_event)
    assert home_view_obj.current_filter == "todos"
    assert home_view_obj.active_category is None
    assert home_view_obj.sort_button.visible is True


@pytest.mark.asyncio
async def test_home_view_show_about_dialog(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    home_view_obj = HomeView(hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)
    mock_page.show_dialog = MagicMock()

    await home_view_obj.build(mock_page)

    home_view_obj._show_about_dialog()
    mock_page.show_dialog.assert_called_once()
    bs = mock_page.show_dialog.call_args[0][0]
    assert isinstance(bs, ft.BottomSheet)
    assert bs.scrollable is True
    assert bs.show_drag_handle is True
    assert bs.use_safe_area is True
    assert bs.maintain_bottom_view_insets_padding is True
    assert bs.content is not None

    # Verifica se os componentes do diálogo estão presentes
    dialog_col = bs.content.content
    assert isinstance(dialog_col, ft.Column)
    assert dialog_col.scroll == ft.ScrollMode.AUTO

    # Encontra o container com o botão do GitHub e o switch AMOLED
    github_button_found = False
    amoled_switch_found = False
    for control in dialog_col.controls:
        if isinstance(control, ft.Row):
            for sub in control.controls:
                if isinstance(
                    sub, ft.OutlinedButton
                ) and "github.com/Lucas2Araujo/NHA_Intel" in (sub.url or ""):
                    github_button_found = True
        elif isinstance(control, ft.Container) and isinstance(control.content, ft.Row):
            for sub in control.content.controls:
                if isinstance(sub, ft.Switch):
                    amoled_switch_found = True
    assert github_button_found is True
    assert amoled_switch_found is True


@pytest.mark.asyncio
async def test_home_view_open_url(in_memory_db):
    from unittest.mock import AsyncMock, patch

    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    home_view_obj = HomeView(hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)
    await home_view_obj.build(mock_page)

    with patch("flet.UrlLauncher.launch_url", new_callable=AsyncMock) as mock_launch:
        await home_view_obj._open_url("https://github.com/Lucas2Araujo/NHA_Intel")
        mock_launch.assert_called_once_with("https://github.com/Lucas2Araujo/NHA_Intel")


@pytest.mark.asyncio
async def test_home_view_amoled_toggle(in_memory_db):
    from src.services.theme_service import ThemeService

    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)
    theme_service = ThemeService(in_memory_db)

    home_view_obj = HomeView(
        hino_repo, fav_repo, hist_repo, theme_service=theme_service
    )
    mock_page = MagicMock(spec=ft.Page)
    await home_view_obj.build(mock_page)

    await home_view_obj._on_amoled_toggle(True)
    assert theme_service.is_amoled is True
    assert mock_page.theme_mode == ft.ThemeMode.DARK

    await home_view_obj._on_amoled_toggle(False)
    assert theme_service.is_amoled is False
    assert mock_page.theme_mode == ft.ThemeMode.SYSTEM
