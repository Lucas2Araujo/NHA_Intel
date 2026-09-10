import asyncio
from typing import Optional

import flet as ft

from src.services.content_manager import ContentManager
from src.services.theme_service import ThemeService
from src.services.updater_service import UpdaterService
from src.theme.glass_styles import (
    get_card_decoration,
    get_liquid_glass_background_gradient,
)
from src.theme.palette import ThemeModeType, get_palette
from src.theme.theme_engine import ThemeEngine
from src.views.settings_dialog import show_settings_dialog

try:
    from src.version import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = "0.2.2"

ROUTE_DOWNLOADS = "/downloads"


class SelecaoView:
    """
    Tela inicial (Hub de Entrada) do aplicativo Hinário Inteligente.
    Apresenta uma interface moderna e acolhedora para o usuário escolher entre
    o Hinário Novo (2022) e o Hinário Tradicional/Antigo (1996), além de
    atalhos para o Agente de Cultos e Gerenciador de Downloads.
    Totalmente adaptável aos temas globais (Material You, Liquid Glass e Classic Book)
    com contraste estrito WCAG AAA e suporte a efeitos de vidro líquido.
    """

    def __init__(
        self,
        theme_service: ThemeService,
        updater_service: UpdaterService | None = None,
        content_manager: ContentManager | None = None,
        theme_engine: ThemeEngine | None = None,
    ):
        self.theme_service = theme_service
        self.updater_service = updater_service or UpdaterService()
        self.content_manager = content_manager or ContentManager()
        self.theme_engine = (
            theme_engine
            or getattr(theme_service, "theme_engine", None)
            or ThemeEngine()
        )
        self.page: ft.Page | None = None

    async def _navigate(self, page: ft.Page, route: str) -> None:
        await page.push_route(route)

    def _show_about_dialog(self, page: ft.Page | None = None, e=None):
        """Abre o modal de Configurações, Temas e Sobre o App."""
        target_page = page if isinstance(page, ft.Page) else self.page
        if not target_page:
            return
        show_settings_dialog(
            page=target_page,
            theme_service=self.theme_service,
            updater_service=self.updater_service,
            edition="novo",
        )

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
        text_primary: str,
        text_secondary: str,
    ) -> ft.Container:
        """Constrói um card interativo com estética adaptada ao tema ativo."""
        dec = get_card_decoration(self.theme_engine)
        is_glass = self.theme_engine.theme_style == ThemeModeType.LIQUID_GLASS
        is_dark = self.theme_engine.is_dark

        # Container do ícone à esquerda
        if is_glass:
            icon_container = ft.Container(
                content=ft.Icon(icon, size=28, color=badge_color),
                gradient=ft.LinearGradient(
                    begin=ft.Alignment.TOP_LEFT,
                    end=ft.Alignment.BOTTOM_RIGHT,
                    colors=[
                        ft.Colors.with_opacity(0.85, "#FFFFFF" if not is_dark else "#334155"),
                        ft.Colors.with_opacity(0.40, "#F1F5F9" if not is_dark else "#1E293B"),
                    ],
                ),
                border=ft.Border.all(
                    1.0,
                    ft.Colors.with_opacity(0.60 if not is_dark else 0.20, ft.Colors.WHITE),
                ),
                border_radius=14,
                padding=ft.Padding.all(12),
            )
            badge_container = ft.Container(
                content=ft.Text(
                    badge_text,
                    size=10,
                    weight=ft.FontWeight.BOLD,
                    color=badge_color,
                ),
                bgcolor=ft.Colors.with_opacity(0.18, badge_color),
                border=ft.Border.all(1.0, ft.Colors.with_opacity(0.35, badge_color)),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            )
        else:
            icon_container = ft.Container(
                content=ft.Icon(icon, size=28, color=badge_color),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border_radius=12,
                padding=ft.Padding.all(12),
            )
            badge_container = ft.Container(
                content=ft.Text(
                    badge_text,
                    size=10,
                    weight=ft.FontWeight.BOLD,
                    color=badge_color,
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border_radius=6,
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            icon_container,
                            ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Text(
                                                title,
                                                size=18,
                                                weight=ft.FontWeight.BOLD,
                                                color=text_primary,
                                            ),
                                            badge_container,
                                        ],
                                        spacing=8,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Text(
                                        subtitle,
                                        size=13,
                                        color=text_secondary,
                                        weight=ft.FontWeight.W_500,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Icon(
                                ft.Icons.ARROW_FORWARD_IOS,
                                size=16,
                                color=text_secondary,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=ft.Text(
                            description,
                            size=12,
                            color=text_secondary,
                        ),
                        padding=ft.Padding.only(top=8),
                    ),
                ],
                spacing=0,
            ),
            bgcolor=dec.get("bgcolor"),
            gradient=dec.get("gradient"),
            border=dec.get("border"),
            border_radius=dec.get("border_radius", 16),
            shadow=dec.get("shadow"),
            blur=dec.get("blur"),
            padding=ft.Padding.all(16),
            ink=True,
            on_click=lambda e: asyncio.create_task(self._navigate(page, route)),
        )

    def build(self, page: ft.Page) -> ft.View:
        self.page = page

        # Aplica o tema configurado
        self.theme_service.apply_theme(page, edition="novo")

        palette = self.theme_engine.get_current_palette()
        is_glass = self.theme_engine.theme_style == ThemeModeType.LIQUID_GLASS
        is_material = self.theme_engine.theme_style == ThemeModeType.MATERIAL_YOU

        # Resolução de cores de texto com alto contraste WCAG AAA
        if is_material:
            text_primary = ft.Colors.ON_SURFACE
            text_secondary = ft.Colors.ON_SURFACE_VARIANT
            header_icon_color = ft.Colors.PRIMARY
            novo_badge_color = ft.Colors.PRIMARY
            antigo_badge_color = ft.Colors.TERTIARY
            biblia_badge_color = ft.Colors.SECONDARY
            header_icon_bg = ft.Colors.SURFACE_CONTAINER_HIGHEST
        else:
            text_primary = palette.text_primary
            text_secondary = palette.text_secondary
            header_icon_color = palette.primary
            novo_badge_color = palette.primary
            antigo_badge_color = palette.primary if not is_glass else "#F59E0B"
            biblia_badge_color = palette.primary if not is_glass else "#10B981"
            header_icon_bg = (
                ft.Colors.with_opacity(0.15, palette.primary)
                if is_glass
                else palette.surface_container_high
            )

        header = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.LIBRARY_MUSIC,
                            size=42,
                            color=header_icon_color,
                        ),
                        bgcolor=header_icon_bg,
                        border=(
                            ft.Border.all(
                                1.0,
                                ft.Colors.with_opacity(0.35, ft.Colors.WHITE),
                            )
                            if is_glass
                            else None
                        ),
                        border_radius=20,
                        padding=ft.Padding.all(16),
                    ),
                    ft.Text(
                        "Hinário Inteligente",
                        size=24,
                        weight=ft.FontWeight.BOLD,
                        color=text_primary,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "Selecione a edição do hinário para começar:",
                        size=14,
                        color=text_secondary,
                        weight=ft.FontWeight.W_500,
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
            badge_color=novo_badge_color,
            route="/novo",
            text_primary=text_primary,
            text_secondary=text_secondary,
        )

        has_antigo = self.content_manager.is_module_installed("hinario_antigo")
        card_antigo = self._build_edition_card(
            page=page,
            title="Hinário Tradicional",
            subtitle="Edição Clássica (1996) • 613 Hinos"
            if has_antigo
            else "Módulo adicional • Baixar para ler",
            description="Todas as poesias tradicionais com comparativo automático da nova edição.",
            badge_text="CLÁSSICO" if has_antigo else "BAIXAR",
            icon=ft.Icons.MENU_BOOK,
            badge_color=antigo_badge_color,
            route="/antigo" if has_antigo else ROUTE_DOWNLOADS,
            text_primary=text_primary,
            text_secondary=text_secondary,
        )

        has_biblia = self.content_manager.has_any_bible_installed()
        installed_bibles = self.content_manager.get_installed_bible_ids()
        bibles_summary = ", ".join(installed_bibles[:4]) if installed_bibles else "ARA, NVI..."

        card_biblia = self._build_edition_card(
            page=page,
            title="Bíblia Sagrada",
            subtitle=f"{bibles_summary} • 66 Livros"
            if has_biblia
            else "Nenhuma tradução instalada • Baixe para ler",
            description="Leitura completa das Escrituras Sagradas com navegação rápida por livro e capítulo.",
            badge_text="BÍBLIA" if has_biblia else "BAIXAR TRADUÇÃO",
            icon=ft.Icons.AUTO_STORIES,
            badge_color=biblia_badge_color,
            route="/biblia" if has_biblia else ROUTE_DOWNLOADS,
            text_primary=text_primary,
            text_secondary=text_secondary,
        )

        quick_actions = ft.Container(
            content=ft.Row(
                controls=[
                    ft.OutlinedButton(
                        "Agente de Cultos",
                        icon=ft.Icons.SMART_TOY_OUTLINED,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=12),
                            color=text_primary,
                        ),
                        on_click=lambda e: asyncio.create_task(
                            self._navigate(page, "/agente")
                        ),
                        expand=True,
                    ),
                    ft.OutlinedButton(
                        "Downloads",
                        icon=ft.Icons.DOWNLOAD_OUTLINED,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=12),
                            color=text_primary,
                        ),
                        on_click=lambda e: asyncio.create_task(
                            self._navigate(page, ROUTE_DOWNLOADS)
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

        root_container = ft.Container(
            content=content_column,
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            alignment=ft.Alignment.TOP_CENTER,
            gradient=(
                get_liquid_glass_background_gradient(self.theme_engine.is_dark)
                if is_glass
                else None
            ),
            expand=True,
        )

        appbar_bg = (
            palette.surface
            if not is_material
            else ft.Colors.SURFACE_CONTAINER_HIGHEST
        )

        return ft.View(
            route="/",
            bgcolor=palette.background if not is_material else ft.Colors.SURFACE,
            appbar=ft.AppBar(
                title=ft.Text(
                    "Hinário Inteligente",
                    weight=ft.FontWeight.BOLD,
                    color=text_primary,
                ),
                center_title=True,
                bgcolor=appbar_bg,
                actions=[
                    ft.IconButton(
                        icon=ft.Icons.INFO_OUTLINE,
                        icon_color=text_primary,
                        tooltip="Sobre o App e Configurações",
                        on_click=lambda e: self._show_about_dialog(page),
                    ),
                ],
            ),
            controls=[
                ft.SafeArea(
                    maintain_bottom_view_padding=True,
                    content=root_container,
                    expand=True,
                )
            ],
        )
