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


def test_selecao_view_conditional_module_badges():
    db_conn = DatabaseConnection(db_path=":memory:")
    theme_service = ThemeService(db_conn)

    mock_cm = MagicMock()
    # Caso 1: Módulos NÃO instalados
    mock_cm.is_module_installed.return_value = False
    mock_cm.has_any_bible_installed.return_value = False
    mock_cm.get_installed_bible_ids.return_value = []

    selecao_uninstalled = SelecaoView(
        theme_service=theme_service, content_manager=mock_cm
    )
    mock_page = MagicMock(spec=ft.Page)
    view_uninstalled = selecao_uninstalled.build(mock_page)
    assert isinstance(view_uninstalled, ft.View)

    # Caso 2: Módulos INSTALADOS
    mock_cm.is_module_installed.return_value = True
    mock_cm.has_any_bible_installed.return_value = True
    mock_cm.get_installed_bible_ids.return_value = ["ARA", "NVI"]

    selecao_installed = SelecaoView(
        theme_service=theme_service, content_manager=mock_cm
    )
    view_installed = selecao_installed.build(mock_page)
    assert isinstance(view_installed, ft.View)


@pytest.mark.asyncio
async def test_selecao_view_contrast_no_grey_400():
    """Garante que nenhum texto na SelecaoView utilize GREY_400 estático."""
    db_conn = DatabaseConnection(db_path=":memory:")
    theme_service = ThemeService(db_conn)
    selecao_view = SelecaoView(theme_service=theme_service)

    mock_page = MagicMock(spec=ft.Page)
    view = selecao_view.build(mock_page)

    # Função recursiva para inspecionar todos os controles
    def check_no_grey_400(ctrl):
        if isinstance(ctrl, ft.Text):
            assert ctrl.color != ft.Colors.GREY_400, f"Texto '{ctrl.value}' usa GREY_400 (baixo contraste)!"
        content = getattr(ctrl, "content", None)
        if content:
            check_no_grey_400(content)
        controls = getattr(ctrl, "controls", None)
        if controls:
            for child in controls:
                check_no_grey_400(child)

    for ctrl in view.controls:
        check_no_grey_400(ctrl)


@pytest.mark.asyncio
async def test_selecao_view_liquid_glass_adaptation():
    """Valida a aplicação de gradiente ambiente fluido e cartões vítreos na SelecaoView."""
    from src.theme.palette import ThemeModeType
    from src.theme.theme_engine import ThemeEngine

    db_conn = DatabaseConnection(db_path=":memory:")
    theme_service = ThemeService(db_conn)
    engine = ThemeEngine(db_conn)
    engine.theme_style = ThemeModeType.LIQUID_GLASS
    engine.is_dark = False

    selecao = SelecaoView(theme_service=theme_service, theme_engine=engine)
    mock_page = MagicMock(spec=ft.Page)
    view = selecao.build(mock_page)

    # O container raiz dentro de SafeArea deve possuir o gradiente fluido
    safe_area = view.controls[0]
    root_container = safe_area.content
    assert root_container.gradient is not None
    assert isinstance(root_container.gradient, ft.LinearGradient)

    # O primeiro cartão de edição (Hinário Novo) deve possuir gradiente e borda vítrea
    content_col = root_container.content
    # header = 0, spacer = 1, card_novo = 2
    card_novo = content_col.controls[2]
    assert card_novo.gradient is not None
    assert card_novo.border is not None
    assert card_novo.border_radius == 20

