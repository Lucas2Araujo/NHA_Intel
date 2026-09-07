from unittest.mock import AsyncMock, MagicMock
import flet as ft
import pytest

from src.database.connection import DatabaseConnection
from src.services.theme_service import COLOR_SEEDS, FONT_FAMILIES, ThemeService
from src.views.settings_dialog import (
    SettingsDialogController,
    show_settings_dialog,
)


@pytest.mark.asyncio
async def test_settings_dialog_build_and_structure(in_memory_db):
    theme_service = ThemeService(in_memory_db)
    mock_page = MagicMock(spec=ft.Page)

    controller = SettingsDialogController(
        page=mock_page,
        theme_service=theme_service,
        edition="novo",
    )
    bs = controller.build_bottom_sheet()

    assert isinstance(bs, ft.BottomSheet)
    assert bs.scrollable is True
    assert bs.show_drag_handle is True
    assert bs.use_safe_area is True
    assert bs.maintain_bottom_view_insets_padding is True

    col = bs.content.content
    assert isinstance(col, ft.Column)
    assert col.scroll == ft.ScrollMode.AUTO

    # Verifica se os componentes principais foram construídos
    assert controller.theme_mode_segmented is not None
    assert controller.seed_chips_row is not None
    assert len(controller.seed_chips_row.controls) == 4
    assert controller.amoled_switch is not None
    assert controller.font_dropdown is not None
    assert len(controller.font_dropdown.options) == len(FONT_FAMILIES)


@pytest.mark.asyncio
async def test_settings_dialog_theme_mode_change(in_memory_db):
    theme_service = ThemeService(in_memory_db)
    mock_page = MagicMock(spec=ft.Page)

    controller = SettingsDialogController(
        page=mock_page,
        theme_service=theme_service,
    )
    controller.build_bottom_sheet()

    # Simula mudança para Dark
    mock_ev = MagicMock()
    mock_ev.control.selected = {"dark"}
    await controller._on_theme_mode_change(mock_ev)

    assert theme_service.theme_mode == "dark"
    assert controller.theme_mode_segmented.selected == ["dark"]
    mock_page.update.assert_called()


@pytest.mark.asyncio
async def test_settings_dialog_seed_selection(in_memory_db):
    theme_service = ThemeService(in_memory_db)
    mock_page = MagicMock(spec=ft.Page)

    controller = SettingsDialogController(
        page=mock_page,
        theme_service=theme_service,
    )
    controller.build_bottom_sheet()

    # Seleciona Verde Bíblico (emerald)
    await controller._on_seed_select("emerald")

    assert theme_service.current_seed == "emerald"
    assert theme_service.get_accent_color() == COLOR_SEEDS["emerald"]["hex"]
    assert mock_page.theme.color_scheme_seed == COLOR_SEEDS["emerald"]["hex"]
    mock_page.update.assert_called()


@pytest.mark.asyncio
async def test_settings_dialog_amoled_toggle(in_memory_db):
    theme_service = ThemeService(in_memory_db)
    mock_page = MagicMock(spec=ft.Page)

    controller = SettingsDialogController(
        page=mock_page,
        theme_service=theme_service,
        edition="novo",
    )
    controller.build_bottom_sheet()

    # Liga o modo AMOLED
    await controller._on_amoled_toggle(True)
    assert theme_service.is_amoled is True
    assert controller.amoled_switch.value is True

    # Desliga o modo AMOLED
    await controller._on_amoled_toggle(False)
    assert theme_service.is_amoled is False
    assert controller.amoled_switch.value is False


@pytest.mark.asyncio
async def test_settings_dialog_font_change(in_memory_db):
    theme_service = ThemeService(in_memory_db)
    mock_page = MagicMock(spec=ft.Page)

    controller = SettingsDialogController(
        page=mock_page,
        theme_service=theme_service,
    )
    controller.build_bottom_sheet()

    # Seleciona Montserrat
    await controller._on_font_change("Montserrat")
    assert theme_service.font_family == "Montserrat"
    assert controller.font_dropdown.value == "Montserrat"
    assert mock_page.theme.font_family == "Montserrat"


def test_show_settings_dialog_helper(in_memory_db):
    theme_service = ThemeService(in_memory_db)
    mock_page = MagicMock(spec=ft.Page)
    mock_page.show_dialog = MagicMock()

    show_settings_dialog(mock_page, theme_service)
    mock_page.show_dialog.assert_called_once()
    bs = mock_page.show_dialog.call_args[0][0]
    assert isinstance(bs, ft.BottomSheet)


@pytest.mark.asyncio
async def test_settings_dialog_tabs_switching(in_memory_db):
    theme_service = ThemeService(in_memory_db)
    mock_page = MagicMock(spec=ft.Page)

    controller = SettingsDialogController(
        page=mock_page,
        theme_service=theme_service,
        initial_tab="sobre",
    )
    controller.build_bottom_sheet()

    # Inicialmente na aba Sobre
    assert controller.active_tab == "sobre"
    assert controller.sobre_container.visible is True
    assert controller.aparencia_container.visible is False

    # Muda para aba Aparência
    mock_ev = MagicMock()
    mock_ev.control.selected = {"aparencia"}
    controller._on_tab_change(mock_ev)

    assert controller.active_tab == "aparencia"
    assert controller.sobre_container.visible is False
    assert controller.aparencia_container.visible is True
    mock_page.update.assert_called()

    # Retorna para aba Sobre
    mock_ev.control.selected = {"sobre"}
    controller._on_tab_change(mock_ev)
    assert controller.active_tab == "sobre"
    assert controller.sobre_container.visible is True
    assert controller.aparencia_container.visible is False


@pytest.mark.asyncio
async def test_settings_dialog_amoled_conditional_dependency(in_memory_db):
    theme_service = ThemeService(in_memory_db)
    mock_page = MagicMock(spec=ft.Page)

    controller = SettingsDialogController(
        page=mock_page,
        theme_service=theme_service,
    )
    controller.build_bottom_sheet()

    # 1. Quando o tema é Claro (light), AMOLED deve ser desabilitado
    mock_ev_light = MagicMock()
    mock_ev_light.control.selected = {"light"}
    await controller._on_theme_mode_change(mock_ev_light)

    assert theme_service.theme_mode == "light"
    assert controller.amoled_switch.disabled is True
    assert controller.amoled_switch.value is False
    assert "apenas quando o modo escuro" in controller.amoled_subtitle.value

    # 2. Quando o tema é Escuro (dark), AMOLED deve ser habilitado
    mock_ev_dark = MagicMock()
    mock_ev_dark.control.selected = {"dark"}
    await controller._on_theme_mode_change(mock_ev_dark)

    assert theme_service.theme_mode == "dark"
    assert controller.amoled_switch.disabled is False
    assert "Preto puro" in controller.amoled_subtitle.value


def test_settings_dialog_github_button(in_memory_db):
    theme_service = ThemeService(in_memory_db)
    mock_page = MagicMock(spec=ft.Page)

    controller = SettingsDialogController(
        page=mock_page,
        theme_service=theme_service,
        initial_tab="sobre",
    )
    bs = controller.build_bottom_sheet()

    # Procura botão com URL do GitHub nos controles da aba sobre
    found_github = False
    candidates = []
    if controller.about_actions:
        candidates.append(controller.about_actions)
    if hasattr(controller.sobre_container.content, "controls"):
        candidates.extend(controller.sobre_container.content.controls)
    elif controller.sobre_container.content:
        candidates.append(controller.sobre_container.content)

    for ctrl in candidates:
        if (
            isinstance(ctrl, (ft.ElevatedButton, ft.OutlinedButton, ft.TextButton))
            and "github.com/Lucas2Araujo/NHA_Intel" in (ctrl.url or "")
        ):
            found_github = True
            break
        if hasattr(ctrl, "controls"):
            for sub in ctrl.controls:
                if (
                    isinstance(sub, (ft.ElevatedButton, ft.OutlinedButton, ft.TextButton))
                    and "github.com/Lucas2Araujo/NHA_Intel" in (sub.url or "")
                ):
                    found_github = True
                    break
    assert found_github is True


def test_show_settings_dialog_real_flet_page(in_memory_db):
    """
    Testa que show_settings_dialog funciona com uma instância real de ft.Page
    sem levantar RuntimeError('Dialogs Control must be added to the page first').
    """
    from flet.controls.page import Page

    sess = MagicMock()
    page = Page(sess=sess, test=True)
    theme_service = ThemeService(in_memory_db)

    show_settings_dialog(page, theme_service)
    assert len(page._dialogs.controls) == 1
    opened_dialog = page._dialogs.controls[0]
    assert isinstance(opened_dialog, ft.BottomSheet)
    assert opened_dialog.open is True


