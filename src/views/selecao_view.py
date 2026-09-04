import asyncio

import flet as ft

from src.services.theme_service import ThemeService
from src.services.updater_service import UpdaterService

try:
    from src.version import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = "0.1.0"


class SelecaoView:
    """
    Tela inicial (Hub de Entrada) do aplicativo Hinário Inteligente.
    Apresenta uma interface moderna e acolhedora para o usuário escolher entre
    o Hinário Novo (2022) e o Hinário Tradicional/Antigo (1996), além de
    atalhos para o Agente de Cultos e Gerenciador de Downloads.
    """

    def __init__(
        self,
        theme_service: ThemeService,
        updater_service: UpdaterService | None = None,
    ):
        self.theme_service = theme_service
        self.updater_service = updater_service or UpdaterService()
        self.page: ft.Page | None = None

    async def _navigate(self, page: ft.Page, route: str) -> None:
        await page.push_route(route)

    def _show_about_dialog(self, page: ft.Page, e=None):
        """Abre o modal Sobre o App com atalho para o modo AMOLED."""
        amoled_switch = ft.Switch(
            value=self.theme_service.is_amoled,
            active_color=ft.Colors.BLUE_400,
            on_change=lambda ev: asyncio.create_task(
                self.theme_service.toggle_amoled(page, ev.control.value)
            ),
        )

        dialog = ft.AlertDialog(
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.LIBRARY_MUSIC, color=ft.Colors.BLUE_400, size=24),
                    ft.Text("Hinário Inteligente", weight=ft.FontWeight.BOLD),
                ],
                spacing=10,
            ),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            f"Versão: {APP_VERSION} (Alfa)",
                            size=13,
                            color=ft.Colors.GREY_400,
                        ),
                        ft.Divider(height=10),
                        ft.Text(
                            "Aplicativo cristão com busca inteligente, letras, comparação de hinários e ferramentas de culto.",
                            size=13,
                        ),
                        ft.Divider(height=10),
                        ft.Row(
                            controls=[
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            "Modo AMOLED",
                                            weight=ft.FontWeight.BOLD,
                                            size=14,
                                        ),
                                        ft.Text(
                                            "Preto absoluto para telas OLED",
                                            size=12,
                                            color=ft.Colors.GREY_400,
                                        ),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                amoled_switch,
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    ],
                    tight=True,
                    spacing=8,
                ),
                width=320,
            ),
            actions=[
                ft.TextButton("Fechar", on_click=lambda ev: page.pop_dialog()),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dialog)

    def _build_edition_card(
        self,
        page: ft.Page,
        title: str,
        subtitle: str,
        description: str,
        badge_text: str,
        icon: ft.IconData,
        badge_color: str,
        route: str,
    ) -> ft.Container:
        """Constrói um card interativo com efeito de toque para a seleção de edição."""
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Icon(icon, size=28, color=badge_color),
                                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                                border_radius=12,
                                padding=ft.Padding.all(12),
                            ),
                            ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Text(
                                                title,
                                                size=18,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Container(
                                                content=ft.Text(
                                                    badge_text,
                                                    size=10,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=badge_color,
                                                ),
                                                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                                                border_radius=6,
                                                padding=ft.Padding.symmetric(
                                                    horizontal=8, vertical=3
                                                ),
                                            ),
                                        ],
                                        spacing=8,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Text(
                                        subtitle, size=13, color=ft.Colors.GREY_400
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Icon(
                                ft.Icons.ARROW_FORWARD_IOS,
                                size=16,
                                color=ft.Colors.GREY_400,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Text(
                            description,
                            size=12,
                            color=ft.Colors.GREY_400,
                        ),
                        padding=ft.Padding.only(top=8),
                    ),
                ],
                spacing=0,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border_radius=16,
            padding=ft.Padding.all(16),
            ink=True,
            on_click=lambda e: asyncio.create_task(self._navigate(page, route)),
        )

    def build(self, page: ft.Page) -> ft.View:
        self.page = page

        # Aplica o tema neutro / base da seleção
        self.theme_service.apply_theme(page, edition="novo")

        header = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.LIBRARY_MUSIC,
                            size=42,
                            color=ft.Colors.BLUE_400,
                        ),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        border_radius=20,
                        padding=ft.Padding.all(16),
                    ),
                    ft.Text(
                        "Hinário Inteligente",
                        size=24,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "Selecione a edição do hinário para começar:",
                        size=14,
                        color=ft.Colors.GREY_400,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.symmetric(vertical=16),
        )

        card_novo = self._build_edition_card(
            page=page,
            title="Hinário Novo",
            subtitle="Edição Atual (2022) • 601 Hinos",
            description="Busca inteligente, letras oficiais, novos arranjos e referências bíblicas.",
            badge_text="NOVO",
            icon=ft.Icons.AUTO_AWESOME,
            badge_color=ft.Colors.BLUE_400,
            route="/novo",
        )

        card_antigo = self._build_edition_card(
            page=page,
            title="Hinário Tradicional",
            subtitle="Edição Clássica (1996) • 613 Hinos",
            description="Todas as poesias tradicionais com comparativo automático da nova edição.",
            badge_text="CLÁSSICO",
            icon=ft.Icons.MENU_BOOK,
            badge_color=ft.Colors.AMBER_400,
            route="/antigo",
        )

        card_biblia = self._build_edition_card(
            page=page,
            title="Bíblia Sagrada",
            subtitle="ARA, NVI, NTLH, KJA • 66 Livros",
            description="Leitura completa das Escrituras Sagradas com navegação rápida por livro e capítulo.",
            badge_text="BÍBLIA",
            icon=ft.Icons.AUTO_STORIES,
            badge_color=ft.Colors.EMERALD_400 if hasattr(ft.Colors, "EMERALD_400") else ft.Colors.GREEN_400,
            route="/biblia",
        )

        quick_actions = ft.Container(
            content=ft.Row(
                controls=[
                    ft.OutlinedButton(
                        "Agente de Cultos",
                        icon=ft.Icons.SMART_TOY_OUTLINED,
                        on_click=lambda e: asyncio.create_task(
                            self._navigate(page, "/agente")
                        ),
                        expand=True,
                    ),
                    ft.OutlinedButton(
                        "Downloads",
                        icon=ft.Icons.DOWNLOAD_OUTLINED,
                        on_click=lambda e: asyncio.create_task(
                            self._navigate(page, "/downloads")
                        ),
                        expand=True,
                    ),
                ],
                spacing=10,
            ),
            padding=ft.Padding.only(top=10),
        )

        content_column = ft.Column(
            controls=[
                header,
                ft.Container(height=8),
                card_novo,
                ft.Container(height=12),
                card_antigo,
                ft.Container(height=12),
                card_biblia,
                ft.Container(height=16),
                quick_actions,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
            expand=True,
        )

        return ft.View(
            route="/",
            bgcolor=ft.Colors.SURFACE,
            appbar=ft.AppBar(
                title=ft.Text("Hinário Inteligente", weight=ft.FontWeight.BOLD),
                center_title=True,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                actions=[
                    ft.IconButton(
                        icon=ft.Icons.INFO_OUTLINE,
                        tooltip="Sobre o App / Modo AMOLED",
                        on_click=lambda e: self._show_about_dialog(page),
                    ),
                ],
            ),
            controls=[
                ft.SafeArea(
                    maintain_bottom_view_padding=True,
                    content=ft.Container(
                        content=content_column,
                        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                        alignment=ft.Alignment.TOP_CENTER,
                        expand=True,
                    ),
                    expand=True,
                )
            ],
        )
