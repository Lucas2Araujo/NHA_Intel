"""
Modal de Configurações, Temas e Sobre o Aplicativo.
Oferece interface Material 3 com duas abas dedicadas:
1. Aba "Sobre o App":
   - Informações do projeto (nome, versão, descrição)
   - Botão de acesso ao repositório GitHub (https://github.com/Lucas2Araujo/NHA_Intel)
   - Botão para verificação de atualizações
2. Aba "Aparência":
   - Modo de Tema: Claro, Escuro, Padrão do Sistema (Automático)
   - Modo Telas AMOLED com dependência condicional (ativo apenas no modo escuro)
   - Sementes de Cor M3: Violeta M3, Dourado Sacro, Verde Bíblico, Azul Safira
   - Tipografia Global: Roboto, Montserrat, Inter, Merriweather, OpenDyslexic
"""

import asyncio
from typing import Any
import weakref

import flet as ft

from src.services.theme_service import COLOR_SEEDS, FONT_FAMILIES, ThemeService
from src.services.updater_service import UpdaterService

try:
    from src.version import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = "0.5.0"


def ensure_page_dialogs(page: ft.Page | None) -> None:
    """
    Garante que os contêineres internos _dialogs e _overlay do Flet estejam
    corretamente vinculados à Page através de weakref, contornando a limitação
    de inicialização do Flet onde 'self.page' falha em _dialogs.update().
    """
    if not page:
        return
    if hasattr(page, "_dialogs") and getattr(page._dialogs, "parent", None) is None:
        try:
            page._dialogs._parent = weakref.ref(page)
        except Exception:
            pass
    if hasattr(page, "_overlay") and getattr(page._overlay, "parent", None) is None:
        try:
            page._overlay._parent = weakref.ref(page)
        except Exception:
            pass


class SettingsDialogController:
    """Controlador do Modal em Abas de Configurações, Temas e Sobre."""

    def __init__(
        self,
        page: ft.Page | None,
        theme_service: ThemeService,
        updater_service: UpdaterService | None = None,
        edition: str | None = None,
        on_check_updates: Any | None = None,
        initial_tab: str = "sobre",
    ):
        self.page = page
        self.theme_service = theme_service
        self.updater_service = updater_service
        self.edition = edition
        self.on_check_updates = on_check_updates
        self.active_tab = initial_tab
        self.bottom_sheet: ft.BottomSheet | None = None

        # Controles da navegação em abas
        self.tab_selector: ft.SegmentedButton | None = None
        self.sobre_container: ft.Container | None = None
        self.about_actions: ft.Row | None = None
        self.aparencia_container: ft.Container | None = None
        self.amoled_tile: ft.Container | None = None
        self.aparencia_font_container: ft.Container | None = None

        # Controles reativos da aba Aparência
        self.theme_mode_segmented: ft.SegmentedButton | None = None
        self.seed_chips_row: ft.Row | None = None
        self.amoled_switch: ft.Switch | None = None
        self.amoled_subtitle: ft.Text | None = None
        self.font_dropdown: ft.Dropdown | None = None

    def _close_dialog(self, _e=None) -> None:
        if self.page:
            try:
                self.page.pop_dialog()
            except Exception:
                pass
        if self.bottom_sheet:
            self.bottom_sheet.open = False
            try:
                self.bottom_sheet.update()
            except Exception:
                pass

    def _on_tab_change(self, e: ft.ControlEvent) -> None:
        selected_set = e.control.selected
        if selected_set:
            self.active_tab = next(iter(selected_set))
            self._update_tab_visibility()
            if self.page:
                self.page.update()

    def _update_tab_visibility(self) -> None:
        is_sobre = self.active_tab == "sobre"
        if self.sobre_container:
            self.sobre_container.visible = is_sobre
        if self.about_actions:
            self.about_actions.visible = is_sobre
        if self.aparencia_container:
            self.aparencia_container.visible = not is_sobre
        if self.amoled_tile:
            self.amoled_tile.visible = not is_sobre
        if self.aparencia_font_container:
            self.aparencia_font_container.visible = not is_sobre
        if self.tab_selector:
            self.tab_selector.selected = [self.active_tab]

    async def _on_theme_mode_change(self, e: ft.ControlEvent) -> None:
        selected_set = e.control.selected
        if selected_set:
            mode = next(iter(selected_set))
            await self.theme_service.set_theme_mode(mode, self.page)
            self._update_controls_state()

    async def _on_seed_select(self, seed_key: str) -> None:
        await self.theme_service.set_seed(seed_key, self.page)
        self._update_controls_state()

    async def _on_amoled_toggle(self, enabled: bool) -> None:
        if self.theme_service.theme_mode == "light":
            if self.amoled_switch:
                self.amoled_switch.value = False
            return
        await self.theme_service.toggle_amoled(
            self.page, enabled, edition=self.edition
        )
        self._update_controls_state()

    async def _on_font_change(self, font_family: str) -> None:
        if font_family:
            await self.theme_service.set_font_family(font_family, self.page)
            self._update_controls_state()

    def _update_controls_state(self) -> None:
        """Atualiza os controles visuais dentro da aba de Aparência."""
        if self.theme_mode_segmented:
            self.theme_mode_segmented.selected = [self.theme_service.theme_mode]
        if self.amoled_switch:
            self.amoled_switch.value = self.theme_service.is_amoled
        if self.font_dropdown:
            self.font_dropdown.value = self.theme_service.font_family
        if self.seed_chips_row:
            self.seed_chips_row.controls = self._build_seed_chips()
        self._update_amoled_state()
        if self.page:
            self.page.update()

    def _update_amoled_state(self) -> None:
        """Gerencia a dependência condicional do switch AMOLED conforme o modo de tema."""
        is_light = self.theme_service.theme_mode == "light"
        if self.amoled_switch:
            if is_light:
                self.amoled_switch.disabled = True
                self.amoled_switch.value = False
            else:
                self.amoled_switch.disabled = False
                self.amoled_switch.value = self.theme_service.is_amoled

        if self.amoled_subtitle:
            if is_light:
                self.amoled_subtitle.value = (
                    "Disponível apenas quando o modo escuro estiver ativo."
                )
            else:
                self.amoled_subtitle.value = (
                    "Preto puro (#000000) e economia em telas OLED"
                )

    def _build_seed_chips(self) -> list[ft.Container]:
        chips: list[ft.Container] = []
        current_seed = self.theme_service.current_seed

        for key, info in COLOR_SEEDS.items():
            is_active = key == current_seed
            chip_color = info["hex"]
            chip_name = info["name"]

            chip = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Container(
                            width=26,
                            height=26,
                            border_radius=13,
                            bgcolor=chip_color,
                            alignment=ft.Alignment.CENTER,
                            border=ft.Border.all(
                                2,
                                ft.Colors.PRIMARY
                                if is_active
                                else ft.Colors.TRANSPARENT,
                            ),
                        ),
                        ft.Text(
                            chip_name,
                            size=10,
                            weight=ft.FontWeight.BOLD
                            if is_active
                            else ft.FontWeight.NORMAL,
                            color=ft.Colors.PRIMARY
                            if is_active
                            else ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                            no_wrap=True,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
                padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                border_radius=12,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST
                if is_active
                else ft.Colors.SURFACE_CONTAINER_LOW,
                border=ft.Border.all(
                    1.5 if is_active else 1,
                    ft.Colors.PRIMARY if is_active else ft.Colors.OUTLINE_VARIANT,
                ),
                ink=True,
                on_click=lambda _e, k=key: asyncio.create_task(self._on_seed_select(k)),
            )
            chips.append(chip)
        return chips

    def build_bottom_sheet(self) -> ft.BottomSheet:
        # 1. Header com título e botão Fechar
        header = ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.INFO_OUTLINE,
                            size=20,
                            color=ft.Colors.PRIMARY,
                        ),
                        ft.Text(
                            "Configurações e Sobre",
                            weight=ft.FontWeight.BOLD,
                            size=17,
                        ),
                    ],
                    spacing=8,
                ),
                ft.IconButton(
                    ft.Icons.CLOSE,
                    tooltip="Fechar",
                    on_click=self._close_dialog,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # 2. Seletor de Abas (SegmentedButton)
        self.tab_selector = ft.SegmentedButton(
            segments=[
                ft.Segment(
                    value="sobre",
                    label=ft.Text("Sobre o App", size=12),
                    icon=ft.Icon(ft.Icons.INFO_OUTLINE, size=16),
                ),
                ft.Segment(
                    value="aparencia",
                    label=ft.Text("Aparência", size=12),
                    icon=ft.Icon(ft.Icons.PALETTE_OUTLINED, size=16),
                ),
            ],
            selected=[self.active_tab],
            allow_multiple_selection=False,
            on_change=self._on_tab_change,
        )

        # 3. Conteúdo da Aba SOBRE
        about_card = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(
                                    ft.Icons.LIBRARY_MUSIC,
                                    size=28,
                                    color=ft.Colors.PRIMARY,
                                ),
                                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                                border_radius=10,
                                padding=ft.Padding.all(8),
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        "Hinário Inteligente",
                                        weight=ft.FontWeight.BOLD,
                                        size=15,
                                    ),
                                    ft.Text(
                                        f"Versão {APP_VERSION}",
                                        size=12,
                                        color=ft.Colors.PRIMARY,
                                        weight=ft.FontWeight.W_600,
                                    ),
                                ],
                                spacing=2,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        "Aplicação cristã moderna com busca inteligente, letras oficiais, bíblia integrada, "
                        "comparação entre hinários (2022 e 1996), áudios offline e agente litúrgico de cultos.",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=8,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=10,
            padding=ft.Padding.all(12),
        )

        self.about_actions = ft.Row(
            controls=[
                ft.OutlinedButton(
                    "GitHub do Projeto",
                    icon=ft.Icons.CODE,
                    url="https://github.com/Lucas2Araujo/NHA_Intel",
                    on_click=lambda _e: asyncio.create_task(
                        self._open_url("https://github.com/Lucas2Araujo/NHA_Intel")
                    ),
                    expand=True,
                ),
                ft.FilledTonalButton(
                    "Verificar Atualizações",
                    icon=ft.Icons.SYSTEM_UPDATE_ALT,
                    on_click=lambda _e: asyncio.create_task(
                        self._trigger_check_updates()
                    ),
                    expand=True,
                ),
            ],
            spacing=10,
            visible=(self.active_tab == "sobre"),
        )

        self.sobre_container = ft.Container(
            content=about_card,
            visible=(self.active_tab == "sobre"),
        )

        # 4. Conteúdo da Aba APARÊNCIA
        # 4.1 Seletor de Modo de Tema
        self.theme_mode_segmented = ft.SegmentedButton(
            segments=[
                ft.Segment(
                    value="light",
                    label=ft.Text("Claro", size=12),
                    icon=ft.Icon(ft.Icons.LIGHT_MODE_OUTLINED, size=16),
                ),
                ft.Segment(
                    value="dark",
                    label=ft.Text("Escuro", size=12),
                    icon=ft.Icon(ft.Icons.DARK_MODE_OUTLINED, size=16),
                ),
                ft.Segment(
                    value="system",
                    label=ft.Text("Sistema", size=12),
                    icon=ft.Icon(ft.Icons.BRIGHTNESS_AUTO, size=16),
                ),
            ],
            selected=[self.theme_service.theme_mode],
            allow_multiple_selection=False,
            on_change=lambda e: asyncio.create_task(self._on_theme_mode_change(e)),
        )

        # 4.2 Seletor de Seeds M3
        self.seed_chips_row = ft.Row(
            controls=self._build_seed_chips(),
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            spacing=6,
        )

        # 4.3 Switch AMOLED com dependência condicional
        self.amoled_subtitle = ft.Text(
            "Preto puro (#000000) e economia em telas OLED",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        self.amoled_switch = ft.Switch(
            value=self.theme_service.is_amoled,
            on_change=lambda ev: asyncio.create_task(
                self._on_amoled_toggle(ev.control.value)
            ),
        )
        self._update_amoled_state()

        self.amoled_tile = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.DARK_MODE_OUTLINED,
                                size=22,
                                color=ft.Colors.AMBER_300,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        "Modo Telas AMOLED",
                                        weight=ft.FontWeight.BOLD,
                                        size=13,
                                    ),
                                    ft.Text(
                                        "Preto puro (#000000) e máxima economia em telas OLED",
                                        size=11,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                    self.amoled_subtitle,
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=10,
                        expand=True,
                    ),
                    self.amoled_switch,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=10,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            visible=(self.active_tab == "aparencia"),
        )

        # 4.4 Seletor de Fonte
        self.font_dropdown = ft.Dropdown(
            options=[
                ft.dropdown.Option(
                    key=f,
                    text=(
                        f"{f} (Padrão M3)"
                        if f == "Roboto"
                        else (
                            f"{f} (Acessibilidade)"
                            if f == "OpenDyslexic"
                            else f
                        )
                    ),
                )
                for f in FONT_FAMILIES
            ],
            value=self.theme_service.font_family,
            dense=True,
            border_radius=10,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            on_select=lambda ev: asyncio.create_task(
                self._on_font_change(ev.control.value)
            ),
        )

        self.aparencia_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Modo de Tema",
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.PRIMARY,
                    ),
                    self.theme_mode_segmented,
                    ft.Container(height=4),
                    ft.Text(
                        "Paleta Harmônica (Material 3 Seed)",
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.PRIMARY,
                    ),
                    self.seed_chips_row,
                ],
                spacing=8,
            ),
            visible=(self.active_tab == "aparencia"),
        )

        self.aparencia_font_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.TEXT_FIELDS, size=18, color=ft.Colors.PRIMARY),
                            ft.Text(
                                "Tipografia Global do App",
                                size=13,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.PRIMARY,
                            ),
                        ],
                        spacing=6,
                    ),
                    self.font_dropdown,
                ],
                spacing=8,
            ),
            visible=(self.active_tab == "aparencia"),
        )

        # Montagem Principal do Conteúdo
        content_column = ft.Column(
            controls=[
                header,
                ft.Divider(height=1),
                self.tab_selector,
                ft.Container(height=6),
                self.sobre_container,
                self.about_actions,
                self.aparencia_container,
                self.amoled_tile,
                self.aparencia_font_container,
            ],
            scroll=ft.ScrollMode.AUTO,
            tight=True,
            spacing=8,
        )

        self.bottom_sheet = ft.BottomSheet(
            scrollable=True,
            show_drag_handle=True,
            use_safe_area=True,
            maintain_bottom_view_insets_padding=True,
            content=ft.Container(
                content=content_column,
                padding=ft.Padding.only(left=20, top=10, right=20, bottom=30),
            ),
        )
        return self.bottom_sheet

    async def _open_url(self, url: str) -> None:
        try:
            await ft.UrlLauncher().launch_url(url)
        except Exception:
            pass

    async def _trigger_check_updates(self) -> None:
        if self.on_check_updates and callable(self.on_check_updates):
            if asyncio.iscoroutinefunction(self.on_check_updates):
                await self.on_check_updates()
            else:
                self.on_check_updates()
        elif self.updater_service and self.page:
            from src.views.update_dialog import show_update_dialog

            try:
                update_info = await self.updater_service.check_for_updates()
                if update_info and update_info.get("has_update"):
                    show_update_dialog(self.page, update_info, self.updater_service)
                else:
                    self._show_snack("Você já está na versão mais recente!")
            except Exception as ex:
                self._show_snack(f"Não foi possível verificar atualizações: {ex}")

    def _show_snack(self, message: str) -> None:
        if not self.page:
            return
        snack = ft.SnackBar(ft.Text(message), duration=3000)
        try:
            if hasattr(self.page, "open"):
                self.page.open(snack)
            elif hasattr(self.page, "show_snack_bar"):
                self.page.show_snack_bar(snack)
        except Exception:
            pass


def show_settings_dialog(
    page: ft.Page,
    theme_service: ThemeService,
    updater_service: UpdaterService | None = None,
    edition: str | None = None,
    on_check_updates: Any | None = None,
    initial_tab: str = "sobre",
) -> None:
    """Abre o modal unificado de configurações e temas."""
    if not page:
        return
    ensure_page_dialogs(page)
    controller = SettingsDialogController(
        page=page,
        theme_service=theme_service,
        updater_service=updater_service,
        edition=edition,
        on_check_updates=on_check_updates,
        initial_tab=initial_tab,
    )
    bs = controller.build_bottom_sheet()
    try:
        page.show_dialog(bs)
    except Exception as ex:
        import logging

        logging.getLogger("flet").warning(
            "Primeira tentativa de show_dialog falhou (%s), reaplicando vínculos...", ex
        )
        try:
            ensure_page_dialogs(page)
            page.show_dialog(bs)
        except Exception as final_ex:
            logging.getLogger("flet").error("Erro ao exibir modal de configurações: %s", final_ex)
