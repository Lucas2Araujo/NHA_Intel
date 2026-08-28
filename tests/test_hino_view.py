import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import flet as ft
from src.repositories.hino_repository import HinoRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.models.hino import Hino
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
    assert view.bgcolor == ft.Colors.SURFACE
    assert len(view.controls) > 0
    assert isinstance(view.controls[0], ft.SafeArea)
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


@pytest.mark.asyncio
async def test_hino_view_open_youtube_link(in_memory_db):
    import dataclasses

    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    view_obj = HinoView(1, hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)
    mock_page.overlay = []

    hino = await hino_repo.get_by_id(1)
    assert hino is not None
    hino_with_video = dataclasses.replace(hino, link_video="https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    with patch("flet.UrlLauncher.launch_url", new_callable=AsyncMock) as mock_launch:
        await view_obj._open_youtube_link(mock_page, hino_with_video)
        mock_launch.assert_called_once_with("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    # Test empty link_video
    hino_empty = dataclasses.replace(hino, link_video="")
    await view_obj._open_youtube_link(mock_page, hino_empty)
    assert view_obj._snackbar is not None
    assert "indisponível" in view_obj._snackbar.content.value or "não possui link" in view_obj._snackbar.content.value


@pytest.mark.asyncio
async def test_hino_view_abrir_modal_leitura_biblica_success(in_memory_db):
    from src.models.biblia import PassagemBiblica, Versiculo

    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    mock_biblia_repo = MagicMock()
    passagem = PassagemBiblica(
        referencia="João 3:16",
        livro="João",
        capitulo=3,
        versiculos=[
            Versiculo(
                livro="João",
                capitulo=3,
                versiculo=16,
                texto="Porque Deus amou ao mundo de tal maneira...",
            )
        ],
    )
    mock_biblia_repo.buscar_passagem = AsyncMock(return_value=passagem)

    view_obj = HinoView(
        1,
        hino_repo,
        fav_repo,
        hist_repo,
        biblia_repository=mock_biblia_repo,
    )
    mock_page = MagicMock(spec=ft.Page)
    mock_page.height = 800

    hino = await hino_repo.get_by_id(1)

    # Teste 1: Aberto direto da tela do hino (from_info_modal=False)
    await view_obj._abrir_modal_leitura_biblica(mock_page, "João 3:16", from_info_modal=False, hino=hino)

    mock_page.show_dialog.assert_called_once()
    dialog_arg = mock_page.show_dialog.call_args[0][0]
    assert isinstance(dialog_arg, ft.BottomSheet)
    mock_biblia_repo.buscar_passagem.assert_called_once_with("João 3:16")
    
    # Verifica que não há botão de fechar no topo (cabeçalho)
    header_row = dialog_arg.content.content.controls[0]
    assert not any(isinstance(ctrl, ft.IconButton) and ctrl.icon == ft.Icons.CLOSE for ctrl in header_row.controls)
    
    # Verifica que o botão do rodapé é "Fechar"
    footer_row = dialog_arg.content.content.controls[-1]
    assert isinstance(footer_row.controls[0], ft.TextButton)
    assert footer_row.controls[0].content == "Fechar"

    # Teste 2: Aberto a partir do modal de informações (from_info_modal=True)
    mock_page.show_dialog.reset_mock()
    with patch.object(view_obj, "_show_info_modal") as mock_show_info:
        await view_obj._abrir_modal_leitura_biblica(mock_page, "João 3:16", from_info_modal=True, hino=hino)
        dialog_arg_info = mock_page.show_dialog.call_args[0][0]
        footer_btn = dialog_arg_info.content.content.controls[-1].controls[0]
        assert footer_btn.content == "Voltar para Informações"
        assert footer_btn.icon == ft.Icons.ARROW_BACK
        
        # Dispara clique no botão voltar
        footer_btn.on_click(MagicMock())
        mock_page.pop_dialog.assert_called()
        mock_show_info.assert_called_once_with(mock_page, hino)


@pytest.mark.asyncio
async def test_hino_view_abrir_modal_leitura_biblica_not_found(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    mock_biblia_repo = MagicMock()
    mock_biblia_repo.buscar_passagem = AsyncMock(return_value=None)

    view_obj = HinoView(
        1,
        hino_repo,
        fav_repo,
        hist_repo,
        biblia_repository=mock_biblia_repo,
    )
    mock_page = MagicMock(spec=ft.Page)
    mock_page.height = 800

    await view_obj._abrir_modal_leitura_biblica(mock_page, "ReferenciaInvalida 99:99")

    mock_page.show_dialog.assert_called_once()
    mock_page.update.assert_called()


@pytest.mark.asyncio
async def test_hino_view_info_modal_biblia_chips(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    view_obj = HinoView(1, hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)
    await view_obj.build(mock_page)

    hino = await hino_repo.get_by_id(1)
    assert hino is not None

    view_obj._show_info_modal(mock_page, hino)
    mock_page.show_dialog.assert_called()

    # Testa _on_biblia_click passando from_info_modal=True
    view_obj._on_biblia_click(mock_page, "Apocalipse 4:8", from_info_modal=True, hino=hino)
    mock_page.pop_dialog.assert_called_once()
    mock_page.run_task.assert_called_once_with(
        view_obj._abrir_modal_leitura_biblica, mock_page, "Apocalipse 4:8", True, hino
    )

    # Testa com referência vazia
    mock_page.overlay = []
    await view_obj._abrir_modal_leitura_biblica(mock_page, "")
    assert view_obj._snackbar is not None
    assert "inválida" in view_obj._snackbar.content.value.lower()


@pytest.mark.asyncio
async def test_hino_view_nav_buttons_push_route(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    view_obj = HinoView(1, hino_repo, fav_repo, hist_repo, hino_ids_list=[1, 2, 3])
    mock_page = MagicMock(spec=ft.Page)
    mock_page.push_route = AsyncMock()

    prev_btn, next_btn = view_obj._build_nav_buttons(mock_page)
    assert prev_btn.disabled is True
    assert next_btn.disabled is False

    await next_btn.on_click(MagicMock())
    mock_page.push_route.assert_called_once_with("/hino/2")


@pytest.mark.asyncio
async def test_hino_view_comparativo_identico(in_memory_db):
    import json
    from src.models.comparativo import HinoComparativo

    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    mock_comp_repo = MagicMock()
    comp_identico = HinoComparativo(
        id=1,
        numero_novo="1",
        numero_antigo="18",
        titulo_novo="Santo, Santo, Santo!",
        titulo_antigo="Santo! Santo! Santo!",
        status_comparacao="IDENTICO",
        similaridade_pct=100.0,
        resumo_alteracoes="Letra idêntica",
        diff_json=json.dumps({"similaridade_pct": 100.0, "estatisticas": {}, "blocos": []}),
    )
    mock_comp_repo.get_by_numero_novo = AsyncMock(return_value=comp_identico)

    mock_antigo_repo = MagicMock()
    mock_antigo_hino = Hino(id=18, numero="18", titulo="Santo! Santo! Santo!", letra="Letra antiga do hino 18.")
    mock_antigo_repo.get_by_numero = AsyncMock(return_value=mock_antigo_hino)

    view_obj = HinoView(
        1,
        hino_repo,
        fav_repo,
        hist_repo,
        comparativo_repository=mock_comp_repo,
        antigo_repository=mock_antigo_repo,
    )
    mock_page = MagicMock(spec=ft.Page)

    built_view = await view_obj.build(mock_page)
    assert isinstance(built_view, ft.View)
    assert view_obj.comparativo is not None
    assert view_obj.comparativo.status_comparacao == "IDENTICO"
    assert view_obj.hino_antigo is not None
    assert view_obj.segmented_button is not None

    # Teste de alternância para o Hinário Antigo
    view_obj._on_segment_change(mock_page, ["antigo"])
    assert view_obj.selected_view_mode == "antigo"
    antigo_ctrl = view_obj._render_current_mode_content()
    assert isinstance(antigo_ctrl, ft.Column)

    # Teste de alternância de volta para o Novo
    view_obj._on_segment_change(mock_page, ["novo"])
    assert view_obj.selected_view_mode == "novo"
    novo_ctrl = view_obj._render_current_mode_content()
    assert novo_ctrl == view_obj.letra_text


@pytest.mark.asyncio
async def test_hino_view_comparativo_modificado_and_diff_rendering(in_memory_db):
    import json
    from src.models.comparativo import HinoComparativo

    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    sample_diff = {
        "similaridade_pct": 85.0,
        "estatisticas": {
            "linhas_adicionadas": 1,
            "linhas_removidas": 1,
            "linhas_alteradas": 2,
            "linhas_iguais": 4,
        },
        "blocos": [
            {"tipo": "igual", "texto": "Linha inalterada"},
            {"tipo": "modificado", "antigo": ["Linha Antiga 1"], "novo": ["Linha Nova 1"]},
            {"tipo": "adicionado", "texto": "Linha Nova Adicionada"},
            {"tipo": "removido", "texto": "Linha Velha Removida"},
        ],
    }

    mock_comp_repo = MagicMock()
    comp_mod = HinoComparativo(
        id=3,
        numero_novo="3",
        numero_antigo="3",
        titulo_novo="O Deus Eterno Reina",
        titulo_antigo="O Deus Eterno Reina",
        status_comparacao="MODIFICADO",
        modificado=1,
        similaridade_pct=85.0,
        resumo_alteracoes="2 linha(s) modificada(s)",
        diff_json=json.dumps(sample_diff),
    )
    mock_comp_repo.get_by_numero_novo = AsyncMock(return_value=comp_mod)

    view_obj = HinoView(
        3,
        hino_repo,
        fav_repo,
        hist_repo,
        comparativo_repository=mock_comp_repo,
    )
    mock_page = MagicMock(spec=ft.Page)

    await view_obj.build(mock_page)
    assert view_obj.comparativo.status_comparacao == "MODIFICADO"

    # Clicar no chip aciona o modo de comparação
    view_obj._on_chip_comparativo_click(mock_page)
    assert view_obj.selected_view_mode == "comparacao"

    diff_ctrl = view_obj._render_current_mode_content()
    assert isinstance(diff_ctrl, ft.Column)
    assert len(diff_ctrl.controls) > 1

    # Atualização de fontes atualiza o modo comparativo também
    view_obj._increase_font(mock_page)
    assert view_obj.font_size == 20
    assert view_obj.content_container is not None


@pytest.mark.asyncio
async def test_hino_view_comparativo_inedito(in_memory_db):
    from src.models.comparativo import HinoComparativo

    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    mock_comp_repo = MagicMock()
    comp_inedito = HinoComparativo(
        id=11,
        numero_novo="1",
        numero_antigo=None,
        titulo_novo="Hino Inedito",
        titulo_antigo=None,
        status_comparacao="NOVO_INEDITO",
        modificado=1,
    )
    mock_comp_repo.get_by_numero_novo = AsyncMock(return_value=comp_inedito)

    view_obj = HinoView(
        1,
        hino_repo,
        fav_repo,
        hist_repo,
        comparativo_repository=mock_comp_repo,
    )
    mock_page = MagicMock(spec=ft.Page)

    await view_obj.build(mock_page)
    assert view_obj.comparativo.status_comparacao == "NOVO_INEDITO"
    assert view_obj.segmented_button is None  # Não exibe segmented button para inédito
