"""
Serviço centralizado de gerenciamento de temas para o aplicativo Hinário Inteligente.
Suporta o Modo Automático do Sistema (Claro/Escuro) e o Modo AMOLED (True Black #000000)
com persistência assíncrona na tabela 'preferencias' do SQLite.
"""

import json

import flet as ft

from src.database.connection import DatabaseConnection

PREF_THEME_KEY = "theme_prefs"

# Paleta True Black para Telas AMOLED
AMOLED_BG_COLOR = "#000000"
AMOLED_SURFACE_COLOR = "#0D0D0D"
AMOLED_SURFACE_CONTAINER = "#141414"
AMOLED_SURFACE_CONTAINER_HIGH = "#1A1A1A"
AMOLED_SURFACE_CONTAINER_HIGHEST = "#222222"
AMOLED_DIVIDER_COLOR = "#2D2D2D"


class ThemeService:
    """
    Controlador de tema do aplicativo.
    Gerencia a ativação do modo AMOLED e a aplicação das cores nas páginas e views.
    """

    def __init__(self, db_connection: DatabaseConnection):
        self.db_connection = db_connection
        self.is_amoled: bool = False
        self._loaded: bool = False

    async def load_preferences(self) -> bool:
        """Carrega a preferência de tema do banco de dados SQLite."""
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
        except Exception:
            self.is_amoled = False
        self._loaded = True
        return self.is_amoled

    async def save_preferences(self, is_amoled: bool) -> None:
        """Salva a preferência de tema no banco de dados SQLite."""
        self.is_amoled = is_amoled
        try:
            conn = await self.db_connection.get_connection()
            prefs_json = json.dumps({"is_amoled": self.is_amoled})
            await conn.execute(
                "INSERT OR REPLACE INTO preferencias (chave, valor) VALUES (?, ?)",
                (PREF_THEME_KEY, prefs_json),
            )
            await conn.commit()
        except Exception:
            pass

    def apply_theme(self, page: ft.Page) -> None:
        """
        Aplica o tema configurado à página do Flet.
        Se AMOLED: ativa Dark Mode com fundo #000000 e esquema de cores otimizado para OLED.
        Se Sistema: ativa ThemeMode.SYSTEM padrão com transições de tela fluidas.

        IMPORTANTE: page.theme é usado para o modo CLARO e page.dark_theme para o modo ESCURO.
        Nunca copiar dark_theme → theme, pois isso causa inconsistências quando o Flet
        resolve tokens semânticos de cor.
        """
        if not page:
            return

        page.fonts = {
            "OpenDyslexic": "fonts/OpenDyslexic-Regular.otf",
            "Times New Roman": "Times New Roman, serif",
        }

        transitions = ft.PageTransitionsTheme(
            android=ft.PageTransitionTheme.CUPERTINO,
            ios=ft.PageTransitionTheme.CUPERTINO,
            linux=ft.PageTransitionTheme.CUPERTINO,
            macos=ft.PageTransitionTheme.CUPERTINO,
            windows=ft.PageTransitionTheme.CUPERTINO,
        )

        if self.is_amoled:
            page.theme_mode = ft.ThemeMode.DARK
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
                primary=ft.Colors.BLUE_400,
                on_primary=ft.Colors.BLACK,
                outline=AMOLED_DIVIDER_COLOR,
            )

            # dark_theme recebe o esquema AMOLED — usado pelo Flet quando theme_mode=DARK
            page.dark_theme = ft.Theme(
                page_transitions=transitions,
                color_scheme=amoled_color_scheme,
                system_overlay_style=ft.SystemOverlayStyle(
                    status_bar_color=AMOLED_BG_COLOR,
                    system_navigation_bar_color=AMOLED_BG_COLOR,
                ),
            )

            # theme (modo claro) fica com o padrão — nunca copiar dark_theme para cá
            page.theme = ft.Theme(page_transitions=transitions)

        else:
            page.theme_mode = ft.ThemeMode.SYSTEM
            page.bgcolor = None
            page.dark_theme = None
            page.theme = ft.Theme(page_transitions=transitions)

    async def toggle_amoled(self, page: ft.Page, enabled: bool) -> None:
        """Alterna o modo AMOLED, persiste no banco e atualiza a interface."""
        await self.save_preferences(enabled)
        self.apply_theme(page)
        page.update()
