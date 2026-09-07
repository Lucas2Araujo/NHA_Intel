from unittest.mock import AsyncMock, MagicMock, patch

import flet as ft
import pytest

from src.models.hino import Hino
from src.repositories.biblia_repository import BibliaRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.hino_repository import HinoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.views.hino_view import (
    DEFAULT_FONT_FAMILY,
    HELVETICA_FONT_FAMILY,
    MONTSERRAT_FONT_FAMILY,
    OPENDYSLEXIC_FONT_FAMILY,
    TIMES_NEW_ROMAN_FONT_FAMILY,
    HinoView,
    _BibliaModalSession,
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
    assert view.route == "/novo/hino/1"
    assert view.bgcolor == ft.Colors.SURFACE
    assert len(view.controls) > 0
    assert isinstance(view.controls[0], ft.SafeArea)
    assert view.controls[0].maintain_bottom_view_padding is True
    assert view_obj.letra_text is not None
    assert view_obj.font_size == 18


@pytest.mark.asyncio
async def test_hino_view_build_antigo_edition(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    view_obj = HinoView(1, hino_repo, fav_repo, hist_repo, edition="antigo")
    mock_page = MagicMock(spec=ft.Page)

    view = await view_obj.build(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/antigo/hino/1"


@pytest.mark.asyncio
async def test_hino_view_build_not_found(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    view_obj = HinoView(999, hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)

    view = await view_obj.build(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/novo/hino/999"


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

    view_obj._set_font_family(mock_page, HELVETICA_FONT_FAMILY)
    assert view_obj.selected_font == HELVETICA_FONT_FAMILY

    view_obj._set_font_family(mock_page, MONTSERRAT_FONT_FAMILY)
    assert view_obj.selected_font == MONTSERRAT_FONT_FAMILY

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
    hino_with_video = dataclasses.replace(
        hino, link_video="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )

    with patch("flet.UrlLauncher.launch_url", new_callable=AsyncMock) as mock_launch:
        await view_obj._open_youtube_link(mock_page, hino_with_video)
        mock_launch.assert_called_once_with(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )

    # Test empty link_video
    hino_empty = dataclasses.replace(hino, link_video="")
    await view_obj._open_youtube_link(mock_page, hino_empty)
    assert view_obj._snackbar is not None
    assert (
        "indisponível" in view_obj._snackbar.content.value
        or "não possui link" in view_obj._snackbar.content.value
    )


@pytest.mark.asyncio
async def test_hino_view_abrir_modal_leitura_biblica_success(in_memory_db):
    from src.models.biblia import PassagemBiblica, Versiculo

    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    mock_biblia_repo = MagicMock()
    mock_biblia_repo.get_available_versions.return_value = ["ARA", "NVI"]
    passagem = PassagemBiblica(
        referencia="João 3:16",
        livro="João",
        capitulo=3,
        versiculos=[
            Versiculo(
                livro="João",
                capitulo=3,
                numero=16,
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
    await view_obj._abrir_modal_leitura_biblica(
        mock_page, "João 3:16", from_info_modal=False, hino=hino
    )

    mock_page.show_dialog.assert_called_once()
    dialog_arg = mock_page.show_dialog.call_args[0][0]
    assert isinstance(dialog_arg, ft.BottomSheet)
    mock_biblia_repo.buscar_passagem.assert_called_with("João 3:16", versao="ARA")

    # Verifica que há o seletor M3 pill button no cabeçalho
    header_row = dialog_arg.content.content.controls[0]
    version_btn = header_row.controls[1]
    assert isinstance(version_btn, ft.PopupMenuButton)
    assert len(version_btn.items) == 2

    # Teste 2: Aberto a partir do modal de informações (from_info_modal=True)
    mock_page.show_dialog.reset_mock()
    with patch.object(view_obj, "_show_info_modal") as mock_show_info:
        await view_obj._abrir_modal_leitura_biblica(
            mock_page, "João 3:16", from_info_modal=True, hino=hino
        )
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
    mock_biblia_repo.get_available_versions.return_value = ["ARA"]
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
async def test_hino_view_abrir_modal_leitura_biblica_interactive_features(in_memory_db):
    from src.models.biblia import PassagemBiblica, Versiculo

    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    mock_biblia_repo = MagicMock()
    mock_biblia_repo.get_available_versions.return_value = ["ARA", "NVI"]
    mock_biblia_repo.get_version_name.side_effect = lambda v: (
        "Almeida Revista e Atualizada" if v == "ARA" else v
    )

    passagem_isaias = PassagemBiblica(
        referencia="Isaías 6:1-3",
        livro="Isaías",
        capitulo=6,
        versiculos=[
            Versiculo(
                livro="Isaías",
                capitulo=6,
                numero=1,
                texto="No ano da morte do rei Uzias...",
            ),
            Versiculo(
                livro="Isaías",
                capitulo=6,
                numero=2,
                texto="Serafins estavam por cima dele...",
            ),
            Versiculo(
                livro="Isaías",
                capitulo=6,
                numero=3,
                texto="E clamavam: Santo, santo, santo...",
            ),
        ],
    )
    passagem_isaias_full = PassagemBiblica(
        referencia="Isaías 6",
        livro="Isaías",
        capitulo=6,
        versiculos=[
            Versiculo(
                livro="Isaías",
                capitulo=6,
                numero=1,
                texto="No ano da morte do rei Uzias...",
            ),
            Versiculo(
                livro="Isaías",
                capitulo=6,
                numero=2,
                texto="Serafins estavam por cima dele...",
            ),
            Versiculo(
                livro="Isaías",
                capitulo=6,
                numero=3,
                texto="E clamavam: Santo, santo, santo...",
            ),
            Versiculo(
                livro="Isaías",
                capitulo=6,
                numero=4,
                texto="As bases das portas tremeram...",
            ),
        ],
    )
    passagem_apoc = PassagemBiblica(
        referencia="Apocalipse 4:8",
        livro="Apocalipse",
        capitulo=4,
        versiculos=[
            Versiculo(
                livro="Apocalipse",
                capitulo=4,
                numero=8,
                texto="E os quatro seres viventes...",
            ),
        ],
    )

    mock_biblia_repo.buscar_passagem = AsyncMock(
        side_effect=lambda ref, versao=None: (
            passagem_apoc if "Apocalipse" in ref else passagem_isaias
        )
    )
    mock_biblia_repo.buscar_capitulo_completo = AsyncMock(
        return_value=passagem_isaias_full
    )

    view_obj = HinoView(
        1,
        hino_repo,
        fav_repo,
        hist_repo,
        biblia_repository=mock_biblia_repo,
        edition="antigo",
    )
    view_obj.relacionados = {
        "temas": ["Santidade"],
        "textos_biblicos": ["Apocalipse 4:8"],
    }

    mock_page = MagicMock(spec=ft.Page)
    mock_page.height = 800
    mock_page.overlay = []

    hino = await hino_repo.get_by_id(1)

    await view_obj._abrir_modal_leitura_biblica(
        mock_page, "Isaías 6:1-3", from_info_modal=False, hino=hino
    )

    mock_page.show_dialog.assert_called_once()
    dialog_arg = mock_page.show_dialog.call_args[0][0]
    controls = dialog_arg.content.content.controls

    # 1. Verifica header e barra de chips de múltiplas referências
    header_row = controls[0]
    ref_chips_container = controls[1]
    assert len(ref_chips_container.content.controls) > 0
    chips_row = ref_chips_container.content.controls[0].content.controls[1]
    assert len(chips_row.controls) == 2  # Isaías 6:1-3 (Base) e Apocalipse 4:8

    # 2. Testa alternância de referência ao clicar no chip do Apocalipse
    chip_apoc = chips_row.controls[1]
    await chip_apoc.on_click(MagicMock())
    mock_biblia_repo.buscar_passagem.assert_called_with("Apocalipse 4:8", versao="ARA")

    # 3. Testa ação de copiar passagem para o clipboard
    action_bar = controls[5]
    copy_btn = action_bar.content.controls[0].controls[0]
    with patch("flet.Clipboard.set", new_callable=AsyncMock) as mock_clipboard_set:
        await copy_btn.on_click(MagicMock())
        mock_clipboard_set.assert_called_once()
        assert "Apocalipse 4:8" in mock_clipboard_set.call_args[0][0]
        assert view_obj._snackbar is not None

    # 4. Testa alternância para ver capítulo completo
    chapter_btn = action_bar.content.controls[0].controls[1]
    await chapter_btn.on_click(MagicMock())
    mock_biblia_repo.buscar_capitulo_completo.assert_called()

    # 5. Testa botões de zoom in e zoom out
    font_minus_btn = action_bar.content.controls[1].controls[0]
    font_indicator = action_bar.content.controls[1].controls[1]
    font_plus_btn = action_bar.content.controls[1].controls[2]

    old_font_val = font_indicator.value
    font_plus_btn.on_click(MagicMock())
    assert font_indicator.value != old_font_val

    font_minus_btn.on_click(MagicMock())
    assert font_indicator.value == old_font_val


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

    # Testa _on_biblia_click com referência
    view_obj._on_biblia_click(mock_page, "Apocalipse 4:8")
    mock_page.pop_dialog.assert_called_once()
    mock_page.run_task.assert_called_once_with(
        view_obj._carregar_biblia_passagem, mock_page
    )
    assert view_obj.selected_view_mode == "biblia"
    assert view_obj.active_biblia_ref == "Apocalipse 4:8"

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
    mock_page.push_route.assert_called_once_with("/novo/hino/2")


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
        diff_json=json.dumps(
            {"similaridade_pct": 100.0, "estatisticas": {}, "blocos": []}
        ),
    )
    mock_comp_repo.get_by_numero_novo = AsyncMock(return_value=comp_identico)

    mock_antigo_repo = MagicMock()
    mock_antigo_hino = Hino(
        id=18,
        numero="18",
        titulo="Santo! Santo! Santo!",
        letra="Letra antiga do hino 18.",
    )
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
            {
                "tipo": "modificado",
                "antigo": ["Linha Antiga 1"],
                "novo": ["Linha Nova 1"],
            },
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


@pytest.mark.asyncio
async def test_hino_view_modo_leitura_biblica_imersiva(in_memory_db):
    from src.models.biblia import PassagemBiblica, Versiculo

    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    mock_biblia_repo = MagicMock()
    mock_biblia_repo.get_available_versions.return_value = ["ARA", "NVI"]
    mock_biblia_repo.get_version_name.side_effect = lambda v: (
        "Almeida Revista e Atualizada" if v == "ARA" else v
    )

    passagem_isaias = PassagemBiblica(
        referencia="Isaías 6:1-3",
        livro="Isaías",
        capitulo=6,
        versiculos=[
            Versiculo(
                livro="Isaías",
                capitulo=6,
                numero=1,
                texto="No ano da morte do rei Uzias...",
            ),
            Versiculo(
                livro="Isaías",
                capitulo=6,
                numero=2,
                texto="Serafins estavam por cima dele...",
            ),
        ],
    )
    passagem_cap_full = PassagemBiblica(
        referencia="Isaías 6",
        livro="Isaías",
        capitulo=6,
        versiculos=[
            Versiculo(
                livro="Isaías",
                capitulo=6,
                numero=1,
                texto="No ano da morte do rei Uzias...",
            ),
            Versiculo(
                livro="Isaías",
                capitulo=6,
                numero=2,
                texto="Serafins estavam por cima dele...",
            ),
            Versiculo(
                livro="Isaías", capitulo=6, numero=3, texto="Santo, santo, santo!"
            ),
        ],
    )

    mock_biblia_repo.buscar_passagem = AsyncMock(return_value=passagem_isaias)
    mock_biblia_repo.buscar_capitulo_completo = AsyncMock(
        return_value=passagem_cap_full
    )

    view_obj = HinoView(
        1,
        hino_repo,
        fav_repo,
        hist_repo,
        biblia_repository=mock_biblia_repo,
        edition="novo",
    )
    mock_page = MagicMock(spec=ft.Page)

    await view_obj.build(mock_page)

    # 1. Alterna para o modo biblia através de _on_biblia_click
    view_obj._on_biblia_click(mock_page, "Isaías 6:1-3")
    assert view_obj.selected_view_mode == "biblia"
    assert view_obj.active_biblia_ref == "Isaías 6:1-3"

    # 2. Carrega a passagem
    await view_obj._carregar_biblia_passagem(mock_page)
    assert view_obj.current_biblia_passagem is not None
    assert view_obj.current_biblia_passagem.referencia == "Isaías 6:1-3"

    # 3. Renderiza o conteúdo bíblico em tela cheia
    content = view_obj._build_biblia_content()
    assert isinstance(content, ft.Column)
    header_toolbar = content.controls[0]
    assert isinstance(header_toolbar, ft.Container)

    # 4. Alterna para capítulo completo
    view_obj.is_biblia_full_chapter = True
    await view_obj._carregar_biblia_passagem(mock_page)
    assert len(view_obj.current_biblia_passagem.versiculos) == 3


@pytest.mark.asyncio
async def test_hino_view_directional_navigation(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    view_obj = HinoView(1, hino_repo, fav_repo, hist_repo, hino_ids_list=[1, 2, 3])
    mock_page = MagicMock(spec=ft.Page)
    mock_page.views = []
    mock_page.route = "/novo/hino/1"

    await view_obj.build(mock_page)
    assert view_obj.hino_id == 1
    assert view_obj.prev_btn.disabled is True
    assert view_obj.next_btn.disabled is False
    assert view_obj.animated_container is not None

    # Avança para o próximo hino com animação direcional
    await view_obj._navigate_hino_directional(mock_page, 2, direction="next")
    assert view_obj.hino_id == 2
    assert view_obj.prev_btn.disabled is False
    assert view_obj.next_btn.disabled is False
    assert mock_page.route == "/novo/hino/2"
    assert view_obj.appbar_title.value == "Hino 2"

    # Retorna para o hino anterior com animação direcional
    await view_obj._navigate_hino_directional(mock_page, 1, direction="prev")
    assert view_obj.hino_id == 1
    assert view_obj.prev_btn.disabled is True
    assert view_obj.next_btn.disabled is False
    assert mock_page.route == "/novo/hino/1"
    assert view_obj.appbar_title.value == "Hino 1"


@pytest.mark.asyncio
async def test_hino_view_go_back_hierarchy(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    view_obj = HinoView(1, hino_repo, fav_repo, hist_repo, hino_ids_list=[1, 2])
    mock_page = MagicMock(spec=ft.Page)
    mock_page.on_view_pop = AsyncMock()
    mock_page.pop_dialog = MagicMock(return_value=False)

    view = await view_obj.build(mock_page)
    appbar_leading = view.appbar.leading
    assert appbar_leading is not None

    # Aciona o botão de voltar da AppBar
    await appbar_leading.on_click(MagicMock())
    mock_page.on_view_pop.assert_called_once_with(None)


@pytest.mark.asyncio
async def test_hino_view_navigate_search(in_memory_db):
    import urllib.parse
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    view_obj = HinoView(1, hino_repo, fav_repo, hist_repo, edition="novo")
    mock_page = MagicMock(spec=ft.Page)
    mock_page.pop_dialog = MagicMock(return_value=True)
    mock_page.push_route = AsyncMock()

    await view_obj.build(mock_page)

    await view_obj._navigate_search(mock_page, "Adoração & Louvor")

    expected_query = urllib.parse.quote("Adoração & Louvor")
    expected_route = f"/novo?categoria={expected_query}&from_hino=1"

    mock_page.pop_dialog.assert_called()
    mock_page.push_route.assert_called_once_with(expected_route)


@pytest.mark.asyncio
async def test_hino_view_version_selector_synchronization(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    mock_biblia_repo = MagicMock(spec=BibliaRepository)
    mock_biblia_repo.get_available_versions.return_value = ["ARA", "NVI"]
    mock_biblia_repo.active_version = "ARA"
    mock_biblia_repo.buscar_passagem = AsyncMock(return_value=None)
    mock_biblia_repo.buscar_capitulo = AsyncMock(return_value=None)

    view_obj = HinoView(
        1,
        hino_repo,
        fav_repo,
        hist_repo,
        biblia_repository=mock_biblia_repo,
        edition="novo",
    )
    mock_page = MagicMock(spec=ft.Page)
    mock_page.height = 800
    mock_page.update = MagicMock()
    view_obj.page = mock_page

    # 1. Constrói a barra inline e verifica o botão pill
    toolbar = view_obj._build_biblia_inline_toolbar(accent_color="#6750A4")
    assert isinstance(view_obj.inline_version_btn, ft.PopupMenuButton)
    assert len(view_obj.inline_version_btn.items) == 2

    # 2. Testa seleção inline de versão
    with patch.object(view_obj, "_carregar_biblia_passagem", new_callable=AsyncMock) as mock_carregar:
        await view_obj._on_inline_versao_selected("NVI")
        assert view_obj.selected_biblia_version == "NVI"
        mock_biblia_repo.set_version.assert_called_with("NVI")
        mock_carregar.assert_called_once_with(mock_page)

    # 3. Testa seleção no modal
    state_modal = _BibliaModalSession(view_obj, mock_page, "João 3:16")
    with patch.object(state_modal, "carregar_versiculos", new_callable=AsyncMock) as mock_carregar_modal:
        await state_modal._on_versao_selected("ARA")
        assert state_modal.selected_version == "ARA"
        assert view_obj.selected_biblia_version == "ARA"
        mock_biblia_repo.set_version.assert_called_with("ARA")
        mock_carregar_modal.assert_called_once_with("ARA")


@pytest.mark.asyncio
async def test_edition_feedback_banner_and_soft_colors(in_memory_db):
    """Verifica se o banner de feedback visual da edição selecionada com cores suaves funciona dinamicamente."""
    import json

    from src.models.comparativo import HinoComparativo

    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    mock_comp_repo = MagicMock()
    comp = HinoComparativo(
        id=1,
        numero_novo="1",
        numero_antigo="5",
        titulo_novo="Glória a Deus",
        titulo_antigo="Antigo Glória a Deus",
        status_comparacao="MODIFICADO",
        resumo_alteracoes="Alteração de estrofe",
        diff_json=json.dumps({"similaridade_pct": 85.0, "estatisticas": {}, "blocos": []}),
    )
    mock_comp_repo.get_by_numero_novo = AsyncMock(return_value=comp)

    mock_antigo_repo = MagicMock()
    mock_antigo_repo.get_by_numero = AsyncMock(
        return_value=Hino(
            id=5,
            numero="5",
            titulo="Antigo Glória a Deus",
            letra="Letra antiga do hino",
        )
    )

    view_obj = HinoView(
        1,
        hino_repo,
        fav_repo,
        hist_repo,
        comparativo_repository=mock_comp_repo,
        antigo_repository=mock_antigo_repo,
        edition="novo",
    )
    mock_page = MagicMock(spec=ft.Page)
    mock_page.height = 800
    mock_page.update = MagicMock()

    await view_obj.build(mock_page)

    # 1. Verifica presença inicial do banner de feedback
    assert view_obj.edition_feedback_banner is not None
    assert view_obj.edition_feedback_text is not None
    assert view_obj.edition_feedback_text.value == "Novo Hinário selecionado"
    assert view_obj.edition_feedback_banner.bgcolor == ft.Colors.PRIMARY_CONTAINER

    # 2. Alterna para o Hinário Antigo
    view_obj._on_segment_change(mock_page, ["antigo"])
    assert view_obj.selected_view_mode == "antigo"
    assert view_obj.edition_feedback_text.value == "Hinário Tradicional selecionado"
    assert view_obj.edition_feedback_banner.bgcolor == ft.Colors.SECONDARY_CONTAINER

    # 3. Alterna para Comparação de Mudanças
    view_obj._on_segment_change(mock_page, ["comparacao"])
    assert view_obj.selected_view_mode == "comparacao"
    assert view_obj.edition_feedback_text.value == "Modo de Comparação selecionado"
    assert view_obj.edition_feedback_banner.bgcolor == ft.Colors.TERTIARY_CONTAINER

    # 4. Alterna para o modo Bíblia
    with patch.object(view_obj, "_carregar_biblia_passagem", new_callable=AsyncMock):
        view_obj._on_segment_change(mock_page, ["biblia"])
        assert view_obj.selected_view_mode == "biblia"
        assert view_obj.edition_feedback_text.value == "Texto Bíblico selecionado"
        assert view_obj.edition_feedback_banner.bgcolor == ft.Colors.SURFACE_CONTAINER_HIGHEST

    # 5. Alterna via clique no chip comparativo
    view_obj._on_chip_comparativo_click(mock_page)
    assert view_obj.selected_view_mode == "comparacao"
    assert view_obj.edition_feedback_text.value == "Modo de Comparação selecionado"
    assert view_obj.edition_feedback_banner.bgcolor == ft.Colors.TERTIARY_CONTAINER





