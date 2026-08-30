from unittest.mock import AsyncMock, MagicMock
import flet as ft
import pytest

from src.database.connection import DatabaseConnection
from src.services.theme_service import ThemeService
from src.views.selecao_view import SelecaoView


@pytest.mark.asyncio
async def test_selecao_view_build():
    db_conn = DatabaseConnection(db_path=":memory:")
    theme_service = ThemeService(db_conn)
    selecao_view = SelecaoView(theme_service=theme_service)

    mock_page = MagicMock(spec=ft.Page)
    view = selecao_view.build(mock_page)

    assert isinstance(view, ft.View)
    assert view.route == "/"
    assert view.appbar is not None
    assert len(view.controls) > 0
    assert isinstance(view.controls[0], ft.SafeArea)


@pytest.mark.asyncio
async def test_selecao_view_navigation():
    db_conn = DatabaseConnection(db_path=":memory:")
    theme_service = ThemeService(db_conn)
    selecao_view = SelecaoView(theme_service=theme_service)

    mock_page = MagicMock(spec=ft.Page)
    mock_page.push_route = AsyncMock()

    await selecao_view._navigate(mock_page, "/novo")
    mock_page.push_route.assert_called_once_with("/novo")

    mock_page.push_route.reset_mock()
    await selecao_view._navigate(mock_page, "/antigo")
    mock_page.push_route.assert_called_once_with("/antigo")


def test_selecao_view_about_dialog():
    db_conn = DatabaseConnection(db_path=":memory:")
    theme_service = ThemeService(db_conn)
    selecao_view = SelecaoView(theme_service=theme_service)

    mock_page = MagicMock(spec=ft.Page)
    mock_page.show_dialog = MagicMock()

    selecao_view._show_about_dialog(mock_page)
    mock_page.show_dialog.assert_called_once()
