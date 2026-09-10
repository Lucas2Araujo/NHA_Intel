import asyncio
from unittest.mock import AsyncMock, MagicMock

import flet as ft
import pytest

from src.database.connection import DatabaseConnection
from src.repositories.biblia_repository import BibliaRepository
from src.services.theme_service import ThemeService
from src.views.biblia_view import (
    BibliaView,
    build_bible_version_button,
    update_bible_version_button,
)


@pytest.mark.asyncio
async def test_biblia_view_build_and_render_in_memory():
    db_conn = DatabaseConnection(db_path=":memory:", read_only=True)
    conn = await db_conn.get_connection()
    await conn.execute("""
        CREATE TABLE book (
            id INTEGER PRIMARY KEY,
            book_reference_id INTEGER,
            testament_reference_id INTEGER,
            name VARCHAR(50)
        );
    """)
    await conn.execute("""
        CREATE TABLE verse (
            id INTEGER PRIMARY KEY,
            book_id INTEGER,
            chapter INTEGER,
            verse INTEGER,
            text TEXT
        );
    """)
    await conn.executemany(
        "INSERT INTO book VALUES (?, ?, ?, ?);",
        [
            (1, 1, 1, "Gênesis"),
            (19, 19, 1, "Salmos"),
            (40, 40, 2, "Mateus"),
        ],
    )
    await conn.executemany(
        "INSERT INTO verse VALUES (?, ?, ?, ?, ?);",
        [
            (1, 1, 1, 1, "No princípio criou Deus os céus e a terra."),
            (2, 1, 1, 2, "E a terra era sem forma e vazia."),
            (3, 1, 2, 1, "Assim foram acabados os céus e a terra."),
            (4, 19, 23, 1, "O SENHOR é o meu pastor."),
        ],
    )
    await conn.commit()

    repo = BibliaRepository(db_conn)
    theme_service = ThemeService(db_conn)
    view_instance = BibliaView(repo, theme_service=theme_service)

    mock_page = MagicMock(spec=ft.Page)
    mock_page.update = MagicMock()
    mock_page.height = 700
    mock_page.show_dialog = MagicMock()
    mock_page.pop_dialog = MagicMock()
    mock_page.push_route = AsyncMock()

    view = await view_instance.build(mock_page, initial_book_id=1, initial_chapter=1)
    assert isinstance(view, ft.View)
    assert view.route == "/biblia"
    assert view.appbar is not None
    assert len(view.controls) > 0

    # Aguarda carregar os versículos
    await asyncio.sleep(0.1)

    assert view_instance.current_passagem is not None
    assert view_instance.current_passagem.referencia == "Gênesis 1"
    assert len(view_instance.current_passagem.versiculos) == 2

    # Testa navegação para próximo capítulo
    await view_instance._navigate_next_chapter()
    assert view_instance.current_chapter == 2
    assert view_instance.current_passagem.referencia == "Gênesis 2"
    assert len(view_instance.current_passagem.versiculos) == 1

    # Testa navegação para capítulo anterior
    await view_instance._navigate_prev_chapter()
    assert view_instance.current_chapter == 1
    assert view_instance.current_passagem.referencia == "Gênesis 1"

    # Testa zoom in e zoom out
    initial_font = view_instance.font_size
    view_instance._zoom_in()
    assert view_instance.font_size == initial_font + 2
    view_instance._zoom_out()
    assert view_instance.font_size == initial_font

    # Testa abertura do seletor em tela cheia (Plano B)
    view_instance._show_selector_dialog()
    assert view_instance.active_screen == "livros"
    assert view_instance.view.appbar.title.value == "Selecionar Livro"

    await repo.close()


@pytest.mark.asyncio
async def test_biblia_repository_helper_methods():
    db_conn = DatabaseConnection(db_path=":memory:", read_only=True)
    conn = await db_conn.get_connection()
    await conn.execute("CREATE TABLE book (id INTEGER PRIMARY KEY, testament_reference_id INTEGER, name VARCHAR(50));")
    await conn.execute("CREATE TABLE verse (id INTEGER PRIMARY KEY, book_id INTEGER, chapter INTEGER, verse INTEGER, text TEXT);")
    await conn.execute("INSERT INTO book VALUES (1, 1, 'Gênesis');")
    await conn.execute("INSERT INTO book VALUES (40, 2, 'Mateus');")
    await conn.executemany("INSERT INTO verse VALUES (?, 1, 1, ?, 'Texto');", [(1, 1), (2, 2)])
    await conn.executemany("INSERT INTO verse VALUES (?, 1, 2, ?, 'Texto');", [(3, 1), (4, 2)])
    await conn.commit()

    repo = BibliaRepository(db_conn)
    livros = await repo.listar_livros()
    assert len(livros) >= 2
    assert livros[0]["name"] == "Gênesis"
    assert livros[0]["testament"] == "AT"
    assert livros[1]["name"] == "Mateus"
    assert livros[1]["testament"] == "NT"

    total = await repo.get_total_capitulos(1)
    assert total == 2

    cap = await repo.buscar_capitulo(1, 1)
    assert cap is not None
    assert len(cap.versiculos) == 2
    assert cap.versiculos[0].numero == 1

    await repo.close()


@pytest.mark.asyncio
async def test_biblia_view_marcador_and_copy():
    from src.views.biblia_view import CANONICAL_BOOK_ABBREVIATIONS

    # Verifica o catálogo canônico de 66 livros
    assert len(CANONICAL_BOOK_ABBREVIATIONS) == 66
    assert CANONICAL_BOOK_ABBREVIATIONS[1] == "Gn"
    assert CANONICAL_BOOK_ABBREVIATIONS[19] == "Sl"
    assert CANONICAL_BOOK_ABBREVIATIONS[40] == "Mt"
    assert CANONICAL_BOOK_ABBREVIATIONS[43] == "Jo"
    assert CANONICAL_BOOK_ABBREVIATIONS[66] == "Ap"

    db_conn = DatabaseConnection(db_path=":memory:", read_only=False)
    conn = await db_conn.get_connection()
    await conn.execute("CREATE TABLE IF NOT EXISTS preferencias (chave TEXT PRIMARY KEY, valor TEXT);")
    await conn.execute("CREATE TABLE book (id INTEGER PRIMARY KEY, testament_reference_id INTEGER, name VARCHAR(50));")
    await conn.execute("CREATE TABLE verse (id INTEGER PRIMARY KEY, book_id INTEGER, chapter INTEGER, verse INTEGER, text TEXT);")
    await conn.execute("INSERT INTO book VALUES (1, 1, 'Gênesis');")
    await conn.execute("INSERT INTO verse VALUES (1, 1, 1, 1, 'No princípio criou Deus os céus e a terra.');")
    await conn.commit()

    repo = BibliaRepository(db_conn)
    theme_service = ThemeService(db_conn)
    view_instance = BibliaView(repo, theme_service=theme_service)

    mock_page = MagicMock(spec=ft.Page)
    mock_page.update = MagicMock()
    mock_page.show_dialog = MagicMock()
    mock_page.pop_dialog = MagicMock()

    await view_instance.build(mock_page, initial_book_id=1, initial_chapter=1)
    await asyncio.sleep(0.05)

    # 1. Testar toggle de marcador
    assert len(view_instance.marcadores) == 0
    await view_instance._toggle_marcador(1, "No princípio criou Deus os céus e a terra.")
    assert len(view_instance.marcadores) == 1
    marcador_key = "1_1_1"
    assert marcador_key in view_instance.marcadores
    assert view_instance.marcadores[marcador_key]["book_name"] == "Gênesis"
    assert view_instance.marcadores[marcador_key]["verse"] == 1

    # 2. Testar abertura do modal de marcadores
    view_instance._show_marcadores_dialog()
    mock_page.show_dialog.assert_called()

    # 3. Testar cópia de versículo com versão
    await view_instance._copiar_versiculo(1, "No princípio criou Deus os céus e a terra.")

    # 4. Testar cópia de capítulo completo com versão
    await view_instance._copiar_capitulo()

    # 5. Testar remoção de marcador
    await view_instance._remover_marcador_por_id(marcador_key)
    assert len(view_instance.marcadores) == 0

    # 6. Testar persistência de leitura entre sessões
    await view_instance._save_preferences()
    new_view = BibliaView(repo, theme_service=theme_service)
    await new_view.build(mock_page, initial_book_id=None, initial_chapter=None)
    assert new_view.current_book_id == 1
    assert new_view.current_chapter == 1
    assert new_view.font_size == view_instance.font_size

    # 7. Testar menu de contexto por toque longo / botão direito no versículo
    mock_page.show_dialog.reset_mock()
    view_instance._show_verse_context_menu(1, "No princípio criou Deus os céus e a terra.")
    mock_page.show_dialog.assert_called_once()
    context_bs = mock_page.show_dialog.call_args[0][0]
    assert isinstance(context_bs, ft.BottomSheet)

    # 8. Testar navegação sequencial em tela cheia (Plano B)
    # Abre seleção de livros
    view_instance._show_selector_dialog()
    assert view_instance.active_screen == "livros"
    assert view_instance.view.appbar.title.value == "Selecionar Livro"

    # Seleciona um livro -> transiciona para seleção de capítulos
    view_instance._open_chapters_selection(1, "Gênesis")
    assert view_instance.active_screen == "capitulos"
    assert "Gênesis • Capítulos" in view_instance.view.appbar.title.value

    # Volta aos livros pelo botão do appbar
    view_instance._open_book_selection()
    assert view_instance.active_screen == "livros"

    # Volta ao leitor
    view_instance._back_to_leitor()
    assert view_instance.active_screen == "leitor"

    # Seleciona capítulo diretamente
    view_instance._select_chapter(1, 1)
    assert view_instance.active_screen == "leitor"

    # 9. Verificar que versículos usam GestureDetector e não botões laterais à direita
    # controls[0] é o cabeçalho do capítulo, controls[1] é o primeiro versículo
    assert len(view_instance.verses_list.controls) > 1
    verse_ctrl = view_instance.verses_list.controls[1]
    assert isinstance(verse_ctrl, ft.GestureDetector)
    inner_row = verse_ctrl.content.content
    assert isinstance(inner_row, ft.Row)
    # Tem apenas o número e o texto (2 controles), sem botões na margem direita
    assert len(inner_row.controls) == 2
    assert isinstance(inner_row.controls[1], ft.Text)

    await repo.close()


def test_format_verse_numbers_and_citation():
    from src.views.biblia_view import format_verse_citation, format_verse_numbers

    # 1. format_verse_numbers
    assert format_verse_numbers([]) == ""
    assert format_verse_numbers([5]) == "5"
    assert format_verse_numbers([1, 2, 3]) == "1-3"
    assert format_verse_numbers([1, 3, 8, 10]) == "1, 3, 8, 10"
    assert format_verse_numbers([1, 2, 3, 7, 10, 11, 12]) == "1-3, 7, 10-12"
    # Ordem e duplicatas
    assert format_verse_numbers([12, 1, 3, 2, 7, 11, 10, 1, 2]) == "1-3, 7, 10-12"

    # 2. format_verse_citation
    assert format_verse_citation("Gênesis", 1, [], "ARA") == ""

    # Versículo único
    cit_single = format_verse_citation("João", 3, [(16, "Porque Deus amou o mundo...")], "ARA")
    assert cit_single == '"Porque Deus amou o mundo..."\n— João 3:16 (ARA)'

    # Versículos contíguos / sequenciais (texto corrido)
    verses_seq = [
        (1, "No princípio criou Deus os céus e a terra."),
        (2, "E a terra era sem forma e vazia."),
        (3, "E disse Deus: Haja luz."),
    ]
    cit_seq = format_verse_citation("Gênesis", 1, verses_seq, "ARA")
    assert "— Gênesis 1:1-3 (ARA)" in cit_seq
    assert "No princípio criou Deus os céus e a terra. E a terra era sem forma e vazia. E disse Deus: Haja luz." in cit_seq

    # Versículos não sequenciais / intercalados (prefixados com número)
    verses_non_seq = [
        (1, "No princípio criou Deus os céus e a terra."),
        (3, "E disse Deus: Haja luz."),
        (8, "E chamou Deus à expansão Céus."),
    ]
    cit_non_seq = format_verse_citation("Gênesis", 1, verses_non_seq, "NVI")
    assert "— Gênesis 1:1, 3, 8 (NVI)" in cit_non_seq
    assert "1 No princípio" in cit_non_seq
    assert "3 E disse Deus" in cit_non_seq
    assert "8 E chamou Deus" in cit_non_seq


@pytest.mark.asyncio
async def test_multi_verse_selection_and_batch_actions():
    db_conn = DatabaseConnection(db_path=":memory:", read_only=False)
    conn = await db_conn.get_connection()
    await conn.execute("CREATE TABLE IF NOT EXISTS preferencias (chave TEXT PRIMARY KEY, valor TEXT);")
    await conn.execute("CREATE TABLE book (id INTEGER PRIMARY KEY, testament_reference_id INTEGER, name VARCHAR(50));")
    await conn.execute("CREATE TABLE verse (id INTEGER PRIMARY KEY, book_id INTEGER, chapter INTEGER, verse INTEGER, text TEXT);")
    await conn.execute("INSERT INTO book VALUES (40, 2, 'Mateus');")
    await conn.executemany(
        "INSERT INTO verse VALUES (?, 40, 13, ?, ?);",
        [
            (1, 1, "Tendo Jesus saído de casa..."),
            (2, 2, "E ajuntou-se muita gente junto dele..."),
            (3, 3, "E falou-lhes de muitas coisas por parábolas..."),
            (4, 7, "E outra parte caiu entre espinhos..."),
            (5, 10, "E, chegando-se a ele os discípulos..."),
        ],
    )
    await conn.commit()

    repo = BibliaRepository(db_conn)
    theme_service = ThemeService(db_conn)
    view_instance = BibliaView(repo, theme_service=theme_service)

    mock_page = MagicMock(spec=ft.Page)
    mock_page.update = MagicMock()
    mock_page.show_dialog = MagicMock()
    mock_page.pop_dialog = MagicMock()
    mock_page.set_clipboard = MagicMock()

    view = await view_instance.build(mock_page, initial_book_id=40, initial_chapter=13)
    await asyncio.sleep(0.05)

    assert not view_instance.is_selection_mode
    assert len(view_instance.selected_verses) == 0

    # 1. Entrar no modo de seleção ao tocar longamente em um versículo
    view_instance._on_verse_long_press(1, "Tendo Jesus saído de casa...")
    assert view_instance.is_selection_mode is True
    assert 1 in view_instance.selected_verses
    # A AppBar do View deve agora ser a AppBar de seleção
    assert view.appbar is not view_instance.normal_appbar
    assert "1 versículo selecionado" in view.appbar.title.value

    # 2. Alternar versículos com toque simples
    view_instance._on_verse_tap(2)
    view_instance._on_verse_tap(3)
    assert view_instance.selected_verses == {1, 2, 3}
    assert "3 versículos selecionados" in view.appbar.title.value

    # 3. Adicionar versículo não sequencial
    view_instance._on_verse_tap(7)
    assert view_instance.selected_verses == {1, 2, 3, 7}

    # 4. Marcar em lote os versículos selecionados
    await view_instance._toggle_marcadores_selected()
    # Modo de seleção deve ser encerrado após a ação
    assert not view_instance.is_selection_mode
    assert len(view_instance.selected_verses) == 0
    assert view.appbar is view_instance.normal_appbar

    # Todos os 4 versículos devem estar em marcadores
    assert "40_13_1" in view_instance.marcadores
    assert "40_13_2" in view_instance.marcadores
    assert "40_13_3" in view_instance.marcadores
    assert "40_13_7" in view_instance.marcadores

    # 5. Selecionar todos os versículos do capítulo
    view_instance._enter_selection_mode(1)
    view_instance._select_all_verses()
    assert len(view_instance.selected_verses) == 5

    # 6. Copiar versículos selecionados
    await view_instance._copy_selected_verses()
    assert not view_instance.is_selection_mode
    mock_page.set_clipboard.assert_called()
    copied_text = mock_page.set_clipboard.call_args[0][0]
    assert "Mateus 13:" in copied_text

    # 7. Desmarcar todos os selecionados em lote
    view_instance._enter_selection_mode(1)
    view_instance._on_verse_tap(2)
    view_instance._on_verse_tap(3)
    view_instance._on_verse_tap(7)
    # Como 1, 2, 3 e 7 já estão marcados, toggle deve desmarcá-los
    await view_instance._toggle_marcadores_selected()
    assert "40_13_1" not in view_instance.marcadores
    assert "40_13_2" not in view_instance.marcadores
    assert "40_13_3" not in view_instance.marcadores
    assert "40_13_7" not in view_instance.marcadores

    # 8. Cancelar modo de seleção via _exit_selection_mode
    view_instance._enter_selection_mode(10)
    assert view_instance.is_selection_mode is True
    view_instance._exit_selection_mode()
    assert view_instance.is_selection_mode is False
    assert len(view_instance.selected_verses) == 0
    assert view.appbar is view_instance.normal_appbar

    # 9. Troca de versão via _select_version
    assert view_instance.version_btn is not None
    await view_instance._select_version("ARA")
    assert view_instance.selected_version == "ARA"

    await repo.close()


def test_build_bible_version_button_and_update():
    mock_repo = MagicMock(spec=BibliaRepository)
    mock_repo.get_available_versions.return_value = ["ARA", "NVI", "NTLH"]

    selected_calls = []

    def on_select(ver: str):
        selected_calls.append(ver)

    btn = build_bible_version_button(
        biblia_repository=mock_repo,
        current_version="ARA",
        on_version_selected=on_select,
    )
    assert isinstance(btn, ft.PopupMenuButton)
    assert len(btn.items) == 3
    # Verifica que o item ativo possui o checkmark
    assert "ARA  ✓" in btn.items[0].content
    assert "NVI" in btn.items[1].content

    # Dispara callback ao clicar no item 1
    btn.items[1].on_click(None)
    assert selected_calls == ["NVI"]

    # Atualiza o botão para NVI
    update_bible_version_button(btn, "NVI", mock_repo, on_select)
    assert "NVI  ✓" in btn.items[1].content
    assert "ARA  ✓" not in btn.items[0].content


def test_build_bible_version_button_simplified_mode_disabled():
    mock_repo = MagicMock(spec=BibliaRepository)
    mock_repo.get_available_versions.return_value = ["ARA"]
    mock_repo.has_installed_bibles.return_value = False

    btn = build_bible_version_button(
        biblia_repository=mock_repo,
        current_version="ARA",
        on_version_selected=lambda ver: None,
    )
    assert isinstance(btn, ft.PopupMenuButton)
    assert btn.visible is False
    assert btn.disabled is True

    # Teste de atualização mantendo desativado/oculto
    update_bible_version_button(btn, "ARA", mock_repo, lambda ver: None)
    assert btn.visible is False
    assert btn.disabled is True


@pytest.mark.asyncio
async def test_biblia_view_plan_b_full_screen_flow():
    db_conn = DatabaseConnection(db_path=":memory:", read_only=False)
    conn = await db_conn.get_connection()
    await conn.execute("CREATE TABLE IF NOT EXISTS preferencias (chave TEXT PRIMARY KEY, valor TEXT);")
    await conn.execute("CREATE TABLE book (id INTEGER PRIMARY KEY, testament_reference_id INTEGER, name VARCHAR(50));")
    await conn.execute("CREATE TABLE verse (id INTEGER PRIMARY KEY, book_id INTEGER, chapter INTEGER, verse INTEGER, text TEXT);")
    await conn.execute("INSERT INTO book VALUES (1, 1, 'Gênesis');")
    await conn.execute("INSERT INTO book VALUES (40, 2, 'Mateus');")
    await conn.execute("INSERT INTO verse VALUES (1, 1, 1, 1, 'No princípio...');")
    await conn.execute("INSERT INTO verse VALUES (2, 1, 2, 1, 'Assim os céus...');")
    await conn.commit()

    repo = BibliaRepository(db_conn)
    theme_service = ThemeService(db_conn)
    view_instance = BibliaView(repo, theme_service=theme_service)

    mock_page = MagicMock(spec=ft.Page)
    mock_page.update = MagicMock()

    await view_instance.build(mock_page, initial_book_id=1, initial_chapter=1)

    # 1. Inicia na tela 'leitor'
    assert view_instance.active_screen == "leitor"
    assert view_instance.view.appbar is view_instance.normal_appbar

    # 2. Abre tela de livros
    view_instance._open_book_selection()
    assert view_instance.active_screen == "livros"
    assert view_instance.view.appbar.title.value == "Selecionar Livro"
    assert view_instance.books_grid_container is not None

    # 3. Volta ao leitor
    view_instance._back_to_leitor()
    assert view_instance.active_screen == "leitor"
    assert view_instance.view.appbar is view_instance.normal_appbar

    # 4. Transiciona para seleção de capítulos
    view_instance._open_chapters_selection(1, "Gênesis")
    assert view_instance.active_screen == "capitulos"
    assert "Gênesis • Capítulos" in view_instance.view.appbar.title.value
    await asyncio.sleep(0.05)
    assert view_instance.chapters_grid_container is not None

    # 5. Volta da tela de capítulos para os livros
    view_instance._open_book_selection()
    assert view_instance.active_screen == "livros"

    # 6. Seleciona um capítulo diretamente -> volta ao leitor e carrega versículos
    view_instance._select_chapter(1, 2)
    assert view_instance.active_screen == "leitor"
    assert view_instance.current_book_id == 1
    assert view_instance.current_chapter == 2
    await asyncio.sleep(0.05)
    assert view_instance.current_chapter == 2

    await repo.close()


@pytest.mark.asyncio
async def test_biblia_view_font_accessibility_modal():
    db_conn = DatabaseConnection(db_path=":memory:", read_only=True)
    conn = await db_conn.get_connection()
    await conn.execute("CREATE TABLE book (id INTEGER PRIMARY KEY, testament_reference_id INTEGER, name VARCHAR(50));")
    await conn.execute("CREATE TABLE verse (id INTEGER PRIMARY KEY, book_id INTEGER, chapter INTEGER, verse INTEGER, text TEXT);")
    await conn.execute("INSERT INTO book VALUES (1, 1, 'Gênesis');")
    await conn.execute("INSERT INTO verse VALUES (1, 1, 1, 1, 'No princípio');")
    await conn.commit()

    repo = BibliaRepository(db_conn)
    view_instance = BibliaView(repo)
    mock_page = MagicMock(spec=ft.Page)
    mock_page.show_dialog = MagicMock()
    mock_page.pop_dialog = MagicMock()
    mock_page.update = MagicMock()

    await view_instance.build(mock_page, initial_book_id=1, initial_chapter=1)

    # 1. Verifica se o item "Aparência e Fonte do Texto" existe no popup menu
    popup_menu = None
    for act in view_instance.normal_appbar.actions:
        if isinstance(act, ft.PopupMenuButton) and act.icon == ft.Icons.MORE_VERT:
            popup_menu = act
            break
    assert popup_menu is not None
    font_item = None
    for it in popup_menu.items:
        if isinstance(it, ft.PopupMenuItem) and (
            getattr(it, "text", None) == "Aparência e Fonte do Texto"
            or getattr(it, "content", None) == "Aparência e Fonte do Texto"
        ):
            font_item = it
            break
    assert font_item is not None
    assert font_item.icon == ft.Icons.FORMAT_SIZE

    # 2. Abre o modal de acessibilidade de fonte
    view_instance._show_font_accessibility_modal(mock_page)
    mock_page.show_dialog.assert_called_once()
    bs = mock_page.show_dialog.call_args[0][0]
    assert isinstance(bs, ft.BottomSheet)
    assert view_instance.font_accessibility_bs is bs

    # 3. Testa alteração do tamanho e reset
    initial_font = view_instance.font_size
    assert initial_font == 17
    view_instance._zoom_in()
    assert view_instance.font_size == 19
    view_instance._zoom_out()
    assert view_instance.font_size == 17

    # 4. Encontra controles no modal (botões de aumento, diminuição, reset e radio de fonte)
    container_col = bs.content.content
    assert isinstance(container_col, ft.Column)

    # Encontra o RadioGroup de fontes
    radio_group = None
    for ctrl in container_col.controls:
        if isinstance(ctrl, ft.RadioGroup):
            radio_group = ctrl
            break
    assert radio_group is not None
    assert radio_group.value == view_instance.font_family
    assert len(radio_group.content.controls) == 6

    # Simula troca de fonte para 'Merriweather'
    ev_radio = MagicMock()
    ev_radio.control.value = "Merriweather"
    radio_group.on_change(ev_radio)
    assert view_instance.font_family == "Merriweather"

    # Encontra botões de tamanho (stepper)
    row_stepper = None
    for ctrl in container_col.controls:
        if isinstance(ctrl, ft.Row) and len(ctrl.controls) >= 4:
            row_stepper = ctrl
            break
    assert row_stepper is not None
    btn_diminuir = row_stepper.controls[0]
    btn_aumentar = row_stepper.controls[2]
    btn_reset = row_stepper.controls[3]

    btn_aumentar.on_click(None)
    assert view_instance.font_size == 19
    btn_diminuir.on_click(None)
    assert view_instance.font_size == 17
    btn_aumentar.on_click(None)
    btn_aumentar.on_click(None)
    assert view_instance.font_size == 21
    btn_reset.on_click(None)
    assert view_instance.font_size == 17

    await repo.close()


@pytest.mark.asyncio
async def test_biblia_view_pesquisa_flow():
    """Valida o fluxo completo de pesquisa da Bíblia (Sprint 4)."""
    db_conn = DatabaseConnection(db_path=":memory:", read_only=True)
    conn = await db_conn.get_connection()
    await conn.execute(
        "CREATE TABLE book (id INTEGER PRIMARY KEY, testament_reference_id INTEGER, name VARCHAR(50));"
    )
    await conn.execute(
        "CREATE TABLE verse (id INTEGER PRIMARY KEY, book_id INTEGER, chapter INTEGER, verse INTEGER, text TEXT);"
    )
    await conn.executemany(
        "INSERT INTO book VALUES (?, ?, ?);",
        [
            (1, 1, "Gênesis"),
            (19, 1, "Salmos"),
            (43, 2, "João"),
        ],
    )
    await conn.executemany(
        "INSERT INTO verse VALUES (?, ?, ?, ?, ?);",
        [
            (1, 1, 1, 3, "Disse Deus: Haja luz; e houve luz."),
            (2, 19, 23, 1, "O SENHOR é o meu pastor; nada me faltará."),
            (3, 43, 8, 12, "Eu sou a luz do mundo."),
        ],
    )
    await conn.commit()

    repo = BibliaRepository(db_conn)
    theme_service = ThemeService(db_conn)
    view_instance = BibliaView(repo, theme_service=theme_service)

    mock_page = MagicMock(spec=ft.Page)
    mock_page.dialogs = []
    mock_page.update = MagicMock()
    mock_page.show_dialog = MagicMock(side_effect=lambda d: mock_page.dialogs.append(d))

    await view_instance.build(mock_page)

    # 1. Abre a pesquisa
    view_instance._abrir_pesquisa()
    assert view_instance.active_screen == "pesquisa"
    assert view_instance.search_input is not None
    assert isinstance(view_instance.view.appbar, ft.AppBar)

    # 2. Executa pesquisa textual
    await view_instance._executar_pesquisa("luz")
    assert len(view_instance.search_results) == 2
    assert view_instance.search_results[0]["referencia"] == "Gênesis 1:3"
    assert view_instance.search_results[1]["referencia"] == "João 8:12"

    # 3. Navega para um resultado selecionado
    await view_instance._navegar_para_resultado_pesquisa(43, 8, 12)
    assert view_instance.active_screen == "leitor"
    assert view_instance.current_book_id == 43
    assert view_instance.current_chapter == 8

    # 4. Testa botão de retorno ao leitor
    view_instance._abrir_pesquisa()
    assert view_instance.active_screen == "pesquisa"
    view_instance._back_to_leitor()
    assert view_instance.active_screen == "leitor"

    await repo.close()


@pytest.mark.asyncio
async def test_biblia_view_comparador_versoes_flow():
    """Valida o comparador multiversões da Bíblia a partir de múltiplos gatilhos (Sprint 4)."""
    db_conn = DatabaseConnection(db_path=":memory:", read_only=True)
    conn = await db_conn.get_connection()
    await conn.execute("CREATE TABLE book (id INTEGER PRIMARY KEY, name VARCHAR(50));")
    await conn.execute(
        "CREATE TABLE verse (id INTEGER PRIMARY KEY, book_id INTEGER, chapter INTEGER, verse INTEGER, text TEXT);"
    )
    await conn.execute("INSERT INTO book VALUES (43, 'João');")
    await conn.execute(
        "INSERT INTO verse VALUES (1, 43, 3, 16, 'Porque Deus amou ao mundo de tal maneira...');"
    )
    await conn.commit()

    repo = BibliaRepository(db_conn)
    theme_service = ThemeService(db_conn)
    view_instance = BibliaView(repo, theme_service=theme_service)

    mock_page = MagicMock(spec=ft.Page)
    mock_page.dialogs = []
    mock_page.update = MagicMock()
    mock_page.show_dialog = MagicMock(side_effect=lambda d: mock_page.dialogs.append(d))

    await view_instance.build(mock_page)

    # 1. Abertura direta do comparador
    await view_instance._abrir_comparador_versoes(43, 3, 16)
    assert len(mock_page.dialogs) == 1
    modal = mock_page.dialogs[-1]
    assert isinstance(modal, ft.BottomSheet)
    assert modal.scrollable is True

    # 2. Gatilho via menu de contexto de versículo
    view_instance._show_verse_context_menu(16, "Porque Deus amou ao mundo...")
    assert len(mock_page.dialogs) == 2
    context_bs = mock_page.dialogs[-1]
    # Encontra o ListTile de Comparar Versões
    column_ctrl = context_bs.content.content
    compare_tile = None
    for ctrl in column_ctrl.controls:
        if isinstance(ctrl, ft.ListTile) and hasattr(ctrl.title, "value") and ctrl.title.value == "Comparar Versões":
            compare_tile = ctrl
            break
    assert compare_tile is not None

    # 3. Gatilho via barra contextual de seleção (1 versículo selecionado)
    view_instance.selected_verses = {16}
    view_instance._update_appbar_for_selection()
    selection_appbar = view_instance.view.appbar
    assert selection_appbar is not None
    # Verifica presença do botão de comparação
    compare_btn = None
    for act in selection_appbar.actions:
        if isinstance(act, ft.IconButton) and act.icon == ft.Icons.COMPARE_ARROWS:
            compare_btn = act
            break
    assert compare_btn is not None

    await repo.close()


@pytest.mark.asyncio
async def test_make_hymn_context_bar():
    from src.views.biblia_view import (
        ContextoHino,
        ReferenciaRelacionada,
        make_hymn_context_bar,
    )

    clicked = []

    def on_select(livro, cap, ver):
        clicked.append((livro, cap, ver))

    hino_ctx = ContextoHino(
        numero="42",
        referencias_relacionadas=[
            ReferenciaRelacionada("Sl 23:1", "Salmos", 23, 1),
            ReferenciaRelacionada("Jo 3:16", "João", 3, 16),
        ],
    )

    bar = make_hymn_context_bar(hino_ctx, on_select)
    assert isinstance(bar, ft.Container)
    assert bar.content is not None
    row = bar.content
    assert isinstance(row, ft.Row)

    # Verifica ícone, texto e chips
    icon = row.controls[0]
    label = row.controls[1]
    chips_row = row.controls[2]
    assert isinstance(icon, ft.Icon)
    assert label.value == "Textos do Hino 42:"
    assert len(chips_row.controls) == 2

    # Dispara o clique no primeiro chip
    chips_row.controls[0].on_click(MagicMock())
    assert clicked == [("Salmos", 23, 1)]


@pytest.mark.asyncio
async def test_biblia_view_with_hino_origem_id_and_jump():
    from src.models.hino import Hino
    from src.views.biblia_view import BibliaView

    db_conn = DatabaseConnection(db_path=":memory:", read_only=True)
    conn = await db_conn.get_connection()
    await conn.execute("CREATE TABLE book (id INTEGER PRIMARY KEY, name VARCHAR(50));")
    await conn.execute(
        "CREATE TABLE verse (id INTEGER PRIMARY KEY, book_id INTEGER, chapter INTEGER, verse INTEGER, text TEXT);"
    )
    await conn.execute("INSERT INTO book VALUES (19, 'Salmos'), (43, 'João');")
    await conn.execute(
        "INSERT INTO verse VALUES (1, 19, 23, 1, 'O SENHOR é o meu pastor...'), (2, 43, 3, 16, 'Porque Deus amou...');"
    )
    await conn.commit()

    biblia_repo = BibliaRepository(db_conn)

    mock_hino_repo = MagicMock()
    mock_hino = Hino(
        id=10,
        numero="10",
        titulo="Pastor Divino",
        letra="...",
        texto_base="Salmos 23:1",
    )
    mock_hino_repo.get_by_id = AsyncMock(return_value=mock_hino)
    mock_hino_repo.get_metadados_relacionados = AsyncMock(
        return_value={"textos_biblicos": ["João 3:16"]}
    )

    view_instance = BibliaView(
        biblia_repo,
        hino_repository=mock_hino_repo,
    )

    mock_page = MagicMock(spec=ft.Page)
    mock_page.update = MagicMock()
    mock_page.height = 700

    view = await view_instance.build(
        mock_page,
        livro="Salmos",
        capitulo=23,
        versiculo_foco=1,
        hino_origem_id=10,
    )

    assert isinstance(view, ft.View)
    await asyncio.sleep(0.1)
    assert view_instance.hymn_context_bar is not None
    assert view_instance.current_book_id == 19
    assert view_instance.current_chapter == 23
    assert view_instance.versiculo_foco == 1

    # Testa salto rápido através de _jump_to_ref
    await view_instance._jump_to_ref("João", 3, 16)
    assert view_instance.current_book_id == 43
    assert view_instance.current_chapter == 3
    assert view_instance.versiculo_foco == 16

    await biblia_repo.close()


def test_main_parse_bible_route_query():
    from main import _parse_bible_route_query

    livro, cap, ver, hino_id = _parse_bible_route_query(
        "/biblia?livro=Salmos&cap=23&ver=1&hino_id=42"
    )
    assert livro == "Salmos"
    assert cap == 23
    assert ver == 1
    assert hino_id == 42

    # Rota simples sem query
    livro2, cap2, ver2, hino_id2 = _parse_bible_route_query("/biblia")
    assert livro2 is None
    assert cap2 is None
    assert ver2 is None
    assert hino_id2 is None





