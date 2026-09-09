"""
Serviço centralizado de gerenciamento de temas para o aplicativo Hinário Inteligente.
Suporta temas dinâmicos baseados em Material 3 Color Scheme Seeds (Violeta, Dourado,
Verde Bíblico, Azul Safira), seleção de edições (Hinário Novo e Hinário Tradicional/Antigo),
Modo de Tema (Sistema, Claro, Escuro), Modo AMOLED (True Black #000000) e Tipografia Global
com persistência assíncrona na tabela 'preferencias' do SQLite.
"""

import json

import flet as ft

from src.database.connection import DatabaseConnection

PREF_THEME_KEY = "theme_prefs"

EDITION_NOVO = "novo"
EDITION_ANTIGO = "antigo"

# --- Catálogo de Color Seeds Material 3 ---
COLOR_SEEDS: dict[str, dict[str, str]] = {
    "purple": {"name": "Violeta M3", "hex": "#6750A4"},
    "gold": {"name": "Dourado Sacro", "hex": "#C67D00"},
    "emerald": {"name": "Verde Bíblico", "hex": "#006D5B"},
    "sapphire": {"name": "Azul Safira", "hex": "#006399"},
}

# --- Catálogo de Fontes Tipográficas Globais ---
FONT_FAMILIES: list[str] = [
    "Roboto",
    "Montserrat",
    "Inter",
    "Merriweather",
    "OpenDyslexic",
]

# --- Paleta True Black para Telas AMOLED (Geral / Hinário Novo) ---
AMOLED_BG_COLOR = "#000000"
AMOLED_SURFACE_COLOR = "#0D0D0D"
AMOLED_SURFACE_CONTAINER = "#141414"
AMOLED_SURFACE_CONTAINER_HIGH = "#1A1A1A"
AMOLED_SURFACE_CONTAINER_HIGHEST = "#222222"
AMOLED_DIVIDER_COLOR = "#2D2D2D"

# --- Paleta Hinário Antigo (Edição Tradicional 1996) ---
# Modo Claro: Marrom Pastel Claro / Pergaminho Vintage Aconchegante
ANTIGO_LIGHT_BG = "#F9F6F0"
ANTIGO_LIGHT_SURFACE = "#F2EBE1"
ANTIGO_LIGHT_CONTAINER = "#E8DDD0"
ANTIGO_LIGHT_CONTAINER_HIGH = "#DFD1C1"
ANTIGO_LIGHT_CONTAINER_HIGHEST = "#D5C4B1"
ANTIGO_LIGHT_PRIMARY = "#795548"
ANTIGO_LIGHT_SECONDARY = "#8D6E63"
ANTIGO_LIGHT_ON_SURFACE = "#2D1D13"
ANTIGO_LIGHT_ON_SURFACE_VARIANT = "#5D4037"
ANTIGO_LIGHT_OUTLINE = "#C7B29E"

# Modo Escuro: Roxinho Noturno Suave / Deep Violet
ANTIGO_DARK_BG = "#1A1024"
ANTIGO_DARK_SURFACE = "#221630"
ANTIGO_DARK_CONTAINER = "#2C1D3D"
ANTIGO_DARK_CONTAINER_HIGH = "#37244D"
ANTIGO_DARK_CONTAINER_HIGHEST = "#432C5E"
ANTIGO_DARK_PRIMARY = "#CE93D8"
ANTIGO_DARK_SECONDARY = "#B388FF"
ANTIGO_DARK_ON_SURFACE = "#F3E5F5"
ANTIGO_DARK_ON_SURFACE_VARIANT = "#E1BEE7"
ANTIGO_DARK_OUTLINE = "#4A3266"

# Modo AMOLED Hinário Antigo: Preto Absoluto com Acentos Lilás
ANTIGO_AMOLED_BG = "#000000"
ANTIGO_AMOLED_SURFACE = "#0A050F"
ANTIGO_AMOLED_CONTAINER = "#130A1D"
ANTIGO_AMOLED_CONTAINER_HIGH = "#1D0F2C"
ANTIGO_AMOLED_CONTAINER_HIGHEST = "#27153B"
ANTIGO_AMOLED_PRIMARY = "#CE93D8"
ANTIGO_AMOLED_OUTLINE = "#2C1742"


class ThemeService:
    """
    Controlador de tema do aplicativo.
    Gerencia a ativação do modo AMOLED, seleção de sementes Material 3,
    modo de tema (Sistema, Claro, Escuro) e tipografia global.
    """

    def __init__(self, db_connection: DatabaseConnection):
        self.db_connection = db_connection
        self.is_amoled: bool = False
        self.current_edition: str = EDITION_NOVO
        self.current_seed: str = "purple"
        self.theme_mode: str = "system"
        self.font_family: str = "Roboto"
        self._loaded: bool = False

    async def load_preferences(self) -> bool:
        """Carrega as preferências de tema do banco de dados SQLite."""
        if self._loaded:
            return self.is_amoled
        try:
            conn = await self.db_connection.get_connection()
            async with conn.execute(
                "SELECT valor FROM preferencias WHERE chave = ?", (PREF_THEME_KEY,)
            ) as cursor:
                row = await cursor.fetchone()
            if row and row[0]:
                data = json.loads(row[0])
                self.is_amoled = bool(data.get("is_amoled", False))
                self.current_edition = str(data.get("edition", EDITION_NOVO))
                seed = str(data.get("seed", "purple"))
                self.current_seed = seed if seed in COLOR_SEEDS else "purple"
                mode = str(data.get("theme_mode", "system")).lower()
                self.theme_mode = (
                    mode if mode in ("system", "light", "dark") else "system"
                )
                font = str(data.get("font_family", "Roboto"))
                self.font_family = font if font in FONT_FAMILIES else "Roboto"
        except Exception:
            self.is_amoled = False
            self.current_edition = EDITION_NOVO
            self.current_seed = "purple"
            self.theme_mode = "system"
            self.font_family = "Roboto"
        self._loaded = True
        return self.is_amoled

    async def save_preferences(
        self,
        is_amoled: bool | None = None,
        edition: str | None = None,
        seed: str | None = None,
        theme_mode: str | None = None,
        font_family: str | None = None,
    ) -> None:
        """Salva as preferências de tema no banco de dados SQLite."""
        if is_amoled is not None:
            self.is_amoled = is_amoled
        if edition is not None:
            self.current_edition = edition
        if seed is not None and seed in COLOR_SEEDS:
            self.current_seed = seed
        if theme_mode is not None and theme_mode.lower() in ("system", "light", "dark"):
            self.theme_mode = theme_mode.lower()
        if font_family is not None and font_family in FONT_FAMILIES:
            self.font_family = font_family

        try:
            conn = await self.db_connection.get_connection()
            prefs_json = json.dumps(
                {
                    "is_amoled": self.is_amoled,
                    "edition": self.current_edition,
                    "seed": self.current_seed,
                    "theme_mode": self.theme_mode,
                    "font_family": self.font_family,
                }
            )
            await conn.execute(
                "INSERT OR REPLACE INTO preferencias (chave, valor) VALUES (?, ?)",
                (PREF_THEME_KEY, prefs_json),
            )
            await conn.commit()
        except Exception:
            try:
                conn = await self.db_connection.get_connection()
                await conn.rollback()
            except Exception:
                pass

    async def set_seed(self, seed_key: str, page: ft.Page | None = None) -> None:
        """Define a cor seed M3 ativa, persiste e atualiza o tema."""
        if seed_key in COLOR_SEEDS:
            self.current_seed = seed_key
            await self.save_preferences(seed=seed_key)
            if page:
                self.apply_theme(page)
                page.update()

    async def set_theme_mode(self, mode: str, page: ft.Page | None = None) -> None:
        """Define o modo de tema ('system', 'light', 'dark'), persiste e atualiza o tema."""
        mode_normalized = mode.lower()
        if mode_normalized in ("system", "light", "dark"):
            self.theme_mode = mode_normalized
            await self.save_preferences(theme_mode=mode_normalized)
            if page:
                self.apply_theme(page)
                page.update()

    async def set_font_family(
        self, font_family: str, page: ft.Page | None = None
    ) -> None:
        """Define a família tipográfica global, persiste e atualiza o tema."""
        if font_family in FONT_FAMILIES:
            self.font_family = font_family
            await self.save_preferences(font_family=font_family)
            if page:
                self.apply_theme(page)
                page.update()

    async def toggle_amoled(
        self, page: ft.Page, enabled: bool, edition: str | None = None
    ) -> None:
        """Alterna o modo AMOLED, persiste no banco e atualiza a interface."""
        self.is_amoled = enabled
        if edition:
            self.current_edition = edition
        await self.save_preferences(is_amoled=enabled, edition=edition)
        self.apply_theme(page, edition=edition)
        page.update()

    def get_accent_color(self, edition: str = EDITION_NOVO) -> str:
        """Retorna a cor de destaque principal de acordo com a edição e a seed M3 ativa."""
        if edition == EDITION_ANTIGO:
            return ANTIGO_DARK_PRIMARY
        return COLOR_SEEDS.get(self.current_seed, COLOR_SEEDS["purple"])["hex"]

    def apply_theme(self, page: ft.Page, edition: str | None = None) -> None:
        """
        Aplica o tema configurado à página do Flet.
        Configura fontes globais, seed M3, tema claro/escuro e suporte a AMOLED.
        """
        if not page:
            return

        active_edition = edition or self.current_edition
        seed_hex = COLOR_SEEDS.get(self.current_seed, COLOR_SEEDS["purple"])["hex"]

        page.fonts = {
            "AppSans": "fonts/AppSans-Regular.ttf",
            "AppSans-Bold": "fonts/AppSans-SemiBold.ttf",
            "HymnSerif": "fonts/HymnSerif-Regular.ttf",
            "HymnSerif-Bold": "fonts/HymnSerif-Bold.ttf",
            "OpenDyslexic": "fonts/OpenDyslexic-Regular.otf",
            "Times New Roman": "Times New Roman, serif",
            "Helvetica": "fonts/Helvetica-World-Regular.ttf",
            "Montserrat": "fonts/Montserrat-Regular.ttf",
            "Inter": "Inter, sans-serif",
            "Merriweather": "Merriweather, serif",
            "Roboto": "Roboto, sans-serif",
        }

        transitions = ft.PageTransitionsTheme(
            android=ft.PageTransitionTheme.CUPERTINO,
            ios=ft.PageTransitionTheme.CUPERTINO,
            linux=ft.PageTransitionTheme.CUPERTINO,
            macos=ft.PageTransitionTheme.CUPERTINO,
            windows=ft.PageTransitionTheme.CUPERTINO,
        )

        # Determina o ThemeMode e fundo da página
        if self.theme_mode == "light":
            page.theme_mode = ft.ThemeMode.LIGHT
            page.bgcolor = None
        elif self.theme_mode == "dark":
            page.theme_mode = ft.ThemeMode.DARK
            page.bgcolor = AMOLED_BG_COLOR if self.is_amoled else None
        else:  # "system"
            if self.is_amoled:
                page.theme_mode = ft.ThemeMode.DARK
                page.bgcolor = AMOLED_BG_COLOR
            else:
                page.theme_mode = ft.ThemeMode.SYSTEM
                page.bgcolor = None

        if active_edition == EDITION_ANTIGO:
            if self.is_amoled and page.theme_mode == ft.ThemeMode.DARK:
                page.bgcolor = ANTIGO_AMOLED_BG
                amoled_scheme = ft.ColorScheme(
                    surface=ANTIGO_AMOLED_BG,
                    surface_dim=ANTIGO_AMOLED_BG,
                    surface_bright=ANTIGO_AMOLED_CONTAINER_HIGHEST,
                    surface_container_lowest=ANTIGO_AMOLED_BG,
                    surface_container_low=ANTIGO_AMOLED_SURFACE,
                    surface_container=ANTIGO_AMOLED_CONTAINER,
                    surface_container_high=ANTIGO_AMOLED_CONTAINER_HIGH,
                    surface_container_highest=ANTIGO_AMOLED_CONTAINER_HIGHEST,
                    on_surface=ft.Colors.WHITE,
                    on_surface_variant=ANTIGO_DARK_ON_SURFACE_VARIANT,
                    primary=ANTIGO_AMOLED_PRIMARY,
                    on_primary=ft.Colors.BLACK,
                    outline=ANTIGO_AMOLED_OUTLINE,
                )
                page.dark_theme = ft.Theme(
                    color_scheme_seed=seed_hex,
                    use_material3=True,
                    font_family=self.font_family,
                    page_transitions=transitions,
                    color_scheme=amoled_scheme,
                    system_overlay_style=ft.SystemOverlayStyle(
                        status_bar_color=ANTIGO_AMOLED_BG,
                        system_navigation_bar_color=ANTIGO_AMOLED_BG,
                    ),
                )
                page.theme = ft.Theme(
                    color_scheme_seed=seed_hex,
                    use_material3=True,
                    font_family=self.font_family,
                    page_transitions=transitions,
                )
            else:
                antigo_light_scheme = ft.ColorScheme(
                    surface=ANTIGO_LIGHT_BG,
                    surface_dim=ANTIGO_LIGHT_SURFACE,
                    surface_bright=ANTIGO_LIGHT_CONTAINER,
                    surface_container_lowest=ANTIGO_LIGHT_BG,
                    surface_container_low=ANTIGO_LIGHT_SURFACE,
                    surface_container=ANTIGO_LIGHT_CONTAINER,
                    surface_container_high=ANTIGO_LIGHT_CONTAINER_HIGH,
                    surface_container_highest=ANTIGO_LIGHT_CONTAINER_HIGHEST,
                    on_surface=ANTIGO_LIGHT_ON_SURFACE,
                    on_surface_variant=ANTIGO_LIGHT_ON_SURFACE_VARIANT,
                    primary=ANTIGO_LIGHT_PRIMARY,
                    on_primary=ft.Colors.WHITE,
                    outline=ANTIGO_LIGHT_OUTLINE,
                )

                antigo_dark_scheme = ft.ColorScheme(
                    surface=ANTIGO_DARK_BG,
                    surface_dim=ANTIGO_DARK_SURFACE,
                    surface_bright=ANTIGO_DARK_CONTAINER_HIGHEST,
                    surface_container_lowest=ANTIGO_DARK_BG,
                    surface_container_low=ANTIGO_DARK_SURFACE,
                    surface_container=ANTIGO_DARK_CONTAINER,
                    surface_container_high=ANTIGO_DARK_CONTAINER_HIGH,
                    surface_container_highest=ANTIGO_DARK_CONTAINER_HIGHEST,
                    on_surface=ANTIGO_DARK_ON_SURFACE,
                    on_surface_variant=ANTIGO_DARK_ON_SURFACE_VARIANT,
                    primary=ANTIGO_DARK_PRIMARY,
                    on_primary=ft.Colors.BLACK,
                    outline=ANTIGO_DARK_OUTLINE,
                )

                page.theme = ft.Theme(
                    color_scheme_seed=seed_hex,
                    use_material3=True,
                    font_family=self.font_family,
                    page_transitions=transitions,
                    color_scheme=antigo_light_scheme,
                )
                page.dark_theme = ft.Theme(
                    color_scheme_seed=seed_hex,
                    use_material3=True,
                    font_family=self.font_family,
                    page_transitions=transitions,
                    color_scheme=antigo_dark_scheme,
                    system_overlay_style=ft.SystemOverlayStyle(
                        status_bar_color=ANTIGO_DARK_BG,
                        system_navigation_bar_color=ANTIGO_DARK_BG,
                    ),
                )
        else:
            # Edição Hinário Novo (Seed M3 Unificada)
            if self.is_amoled and page.theme_mode == ft.ThemeMode.DARK:
                page.bgcolor = AMOLED_BG_COLOR
                amoled_color_scheme = ft.ColorScheme(
                    surface=AMOLED_BG_COLOR,
                    surface_dim=AMOLED_BG_COLOR,
                    surface_bright=AMOLED_SURFACE_CONTAINER_HIGHEST,
                    surface_container_lowest=AMOLED_BG_COLOR,
                    surface_container_low=AMOLED_SURFACE_COLOR,
                    surface_container=AMOLED_SURFACE_CONTAINER,
                    surface_container_high=AMOLED_SURFACE_CONTAINER_HIGH,
                    surface_container_highest=AMOLED_SURFACE_CONTAINER_HIGHEST,
                    on_surface=ft.Colors.WHITE,
                    on_surface_variant=ft.Colors.GREY_400,
                    primary=seed_hex,
                    on_primary=ft.Colors.BLACK,
                    outline=AMOLED_DIVIDER_COLOR,
                )

                page.dark_theme = ft.Theme(
                    color_scheme_seed=seed_hex,
                    use_material3=True,
                    font_family=self.font_family,
                    page_transitions=transitions,
                    color_scheme=amoled_color_scheme,
                    system_overlay_style=ft.SystemOverlayStyle(
                        status_bar_color=AMOLED_BG_COLOR,
                        system_navigation_bar_color=AMOLED_BG_COLOR,
                    ),
                )
                page.theme = ft.Theme(
                    color_scheme_seed=seed_hex,
                    use_material3=True,
                    font_family=self.font_family,
                    page_transitions=transitions,
                )
            else:
                page.theme = ft.Theme(
                    color_scheme_seed=seed_hex,
                    use_material3=True,
                    font_family=self.font_family,
                    page_transitions=transitions,
                )
                page.dark_theme = ft.Theme(
                    color_scheme_seed=seed_hex,
                    use_material3=True,
                    font_family=self.font_family,
                    page_transitions=transitions,
                )

