import asyncio
from unittest.mock import AsyncMock, MagicMock

import flet as ft
import pytest

from src.database.connection import DatabaseConnection
from src.repositories.biblia_repository import BibliaRepository
from src.services.theme_service import ThemeService
from src.views.biblia_view import BibliaView


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

    # Testa abertura do modal de seleção
    view_instance._show_selector_dialog()
    mock_page.show_dialog.assert_called_once()

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
