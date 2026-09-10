"""
Gerenciador central de temas, estilos visuais e persistência para o Hinário Inteligente.
Suporta três estilos globais: Material You, Liquid Glass e Classic Book (com variantes Light/Dark),
gestão tipográfica com Montserrat como padrão e persistência via page.client_storage.
"""

import json
from typing import Any, Optional

import flet as ft

from src.database.connection import DatabaseConnection
from src.theme.palette import (
    ThemeModeType,
    ThemePalette,
    get_palette,
)
from src.utils.font_manager import DEFAULT_FONT_FAMILY, FontManager

# Chaves de persistência no Client Storage e Banco SQLite
STORAGE_KEY_THEME_STYLE = "pref_theme_style"
STORAGE_KEY_THEME_MODE = "pref_theme_mode"
STORAGE_KEY_AMOLED = "pref_is_amoled"
STORAGE_KEY_COLOR_SEED = "pref_color_seed"
STORAGE_KEY_FONT_FAMILY = "pref_font_family"
STORAGE_KEY_GLASS_BLUR = "pref_glass_blur"
PREF_DB_THEME_KEY = "theme_prefs"

# Catálogo oficial de seeds M3
COLOR_SEEDS: dict[str, dict[str, str]] = {
    "purple": {"name": "Violeta M3", "hex": "#6750A4"},
    "gold": {"name": "Dourado Sacro", "hex": "#C67D00"},
    "emerald": {"name": "Verde Bíblico", "hex": "#006D5B"},
    "sapphire": {"name": "Azul Safira", "hex": "#006399"},
}


class ThemeEngine:
    """Motor central de estilização, paletas e persistência de temas."""

    def __init__(self, db_connection: Optional[DatabaseConnection] = None):
        self.db_connection = db_connection
        self.theme_style: ThemeModeType = ThemeModeType.MATERIAL_YOU
        self.theme_mode: str = "system"  # "system", "light", "dark"
        self.is_dark: bool = False
        self.is_amoled: bool = False
        self.glass_blur_enabled: bool = True
        self.current_seed: str = "purple"
        self.font_family: str = DEFAULT_FONT_FAMILY
        self.current_edition: str = "novo"
        self._loaded: bool = False

    def get_current_palette(self) -> ThemePalette:
        """Retorna a paleta de design ativa baseada no estilo e modo de iluminação."""
        return get_palette(self.theme_style, self.is_dark)

    async def load_preferences(self, page: Optional[ft.Page] = None) -> bool:
        """
        Carrega as preferências salvas em page.client_storage (prioritário)
        com fallback para tabela de preferências SQLite.
        """
        if self._loaded and not page:
            return self.is_dark

        loaded_from_storage = False

        # 1. Tentar ler do client_storage se houver page disponível
        if page and hasattr(page, "client_storage"):
            try:
                storage = page.client_storage
                stored_style = await storage.get_async(STORAGE_KEY_THEME_STYLE)
                if stored_style:
                    try:
                        self.theme_style = ThemeModeType(stored_style)
                    except ValueError:
                        self.theme_style = ThemeModeType.MATERIAL_YOU

                stored_mode = await storage.get_async(STORAGE_KEY_THEME_MODE)
                if stored_mode in ("system", "light", "dark"):
                    self.theme_mode = stored_mode

                stored_amoled = await storage.get_async(STORAGE_KEY_AMOLED)
                if stored_amoled is not None:
                    self.is_amoled = bool(stored_amoled)

                stored_seed = await storage.get_async(STORAGE_KEY_COLOR_SEED)
                if stored_seed in COLOR_SEEDS:
                    self.current_seed = stored_seed

                stored_font = await storage.get_async(STORAGE_KEY_FONT_FAMILY)
                if stored_font:
                    self.font_family = stored_font

                stored_glass_blur = await storage.get_async(STORAGE_KEY_GLASS_BLUR)
                if stored_glass_blur is not None:
                    self.glass_blur_enabled = bool(stored_glass_blur)

                loaded_from_storage = True
            except Exception:
                loaded_from_storage = False

        # 2. Se não carregou do storage ou não havia dados, tentar ler do SQLite
        if not loaded_from_storage and self.db_connection:
            try:
                conn = await self.db_connection.get_connection()
                async with conn.execute(
                    "SELECT valor FROM preferencias WHERE chave = ?",
                    (PREF_DB_THEME_KEY,),
                ) as cursor:
                    row = await cursor.fetchone()
                if row and row[0]:
                    data = json.loads(row[0])
                    style_str = data.get("theme_style")
                    if style_str:
                        try:
                            self.theme_style = ThemeModeType(style_str)
                        except ValueError:
                            pass
                    self.is_amoled = bool(data.get("is_amoled", False))
                    self.current_edition = str(data.get("edition", "novo"))
                    seed = str(data.get("seed", "purple"))
                    self.current_seed = seed if seed in COLOR_SEEDS else "purple"
                    mode = str(data.get("theme_mode", "system")).lower()
                    self.theme_mode = mode if mode in ("system", "light", "dark") else "system"
                    font = str(data.get("font_family", DEFAULT_FONT_FAMILY))
                    self.font_family = font
                    self.glass_blur_enabled = bool(data.get("glass_blur_enabled", True))
            except Exception:
                pass

        self._resolve_is_dark(page)
        self._loaded = True
        return self.is_dark

    async def save_preferences(
        self,
        page: Optional[ft.Page] = None,
        theme_style: Optional[ThemeModeType | str] = None,
        theme_mode: Optional[str] = None,
        is_amoled: Optional[bool] = None,
        seed: Optional[str] = None,
        font_family: Optional[str] = None,
        edition: Optional[str] = None,
        glass_blur_enabled: Optional[bool] = None,
    ) -> None:
        """Persiste as preferências atualizadas em page.client_storage e SQLite."""
        if theme_style is not None:
            if isinstance(theme_style, str):
                try:
                    self.theme_style = ThemeModeType(theme_style.lower())
                except ValueError:
                    pass
            else:
                self.theme_style = theme_style

        if theme_mode is not None and theme_mode.lower() in ("system", "light", "dark"):
            self.theme_mode = theme_mode.lower()

        if is_amoled is not None:
            self.is_amoled = is_amoled

        if seed is not None and seed in COLOR_SEEDS:
            self.current_seed = seed

        if font_family is not None:
            self.font_family = font_family

        if edition is not None:
            self.current_edition = edition

        if glass_blur_enabled is not None:
            self.glass_blur_enabled = glass_blur_enabled

        self._resolve_is_dark(page)

        # 1. Salvar no client_storage
        if page and hasattr(page, "client_storage"):
            try:
                storage = page.client_storage
                await storage.set_async(STORAGE_KEY_THEME_STYLE, self.theme_style.value)
                await storage.set_async(STORAGE_KEY_THEME_MODE, self.theme_mode)
                await storage.set_async(STORAGE_KEY_AMOLED, self.is_amoled)
                await storage.set_async(STORAGE_KEY_COLOR_SEED, self.current_seed)
                await storage.set_async(STORAGE_KEY_FONT_FAMILY, self.font_family)
                await storage.set_async(STORAGE_KEY_GLASS_BLUR, self.glass_blur_enabled)
            except Exception:
                pass

        # 2. Salvar no banco SQLite
        if self.db_connection:
            try:
                conn = await self.db_connection.get_connection()
                prefs_json = json.dumps(
                    {
                        "theme_style": self.theme_style.value,
                        "is_amoled": self.is_amoled,
                        "edition": self.current_edition,
                        "seed": self.current_seed,
                        "theme_mode": self.theme_mode,
                        "font_family": self.font_family,
                        "glass_blur_enabled": self.glass_blur_enabled,
                    }
                )
                await conn.execute(
                    "INSERT OR REPLACE INTO preferencias (chave, valor) VALUES (?, ?)",
                    (PREF_DB_THEME_KEY, prefs_json),
                )
                await conn.commit()
            except Exception:
                try:
                    conn = await self.db_connection.get_connection()
                    await conn.rollback()
                except Exception:
                    pass

    async def set_glass_blur_enabled(
        self, enabled: bool, page: Optional[ft.Page] = None
    ) -> None:
        """Ativa ou desativa o desfoque de fundo (Backdrop Blur) do Liquid Glass para otimização de performance."""
        self.glass_blur_enabled = enabled
        await self.save_preferences(page=page, glass_blur_enabled=enabled)
        if page:
            self.apply_theme(page)
            page.update()

    async def set_theme_style(
        self, style: ThemeModeType | str, page: Optional[ft.Page] = None
    ) -> None:
        """Define o estilo de tema ativo e atualiza a interface."""
        if isinstance(style, str):
            try:
                self.theme_style = ThemeModeType(style.lower())
            except ValueError:
                return
        else:
            self.theme_style = style

        await self.save_preferences(page=page, theme_style=self.theme_style)
        if page:
            self.apply_theme(page)
            page.update()

    async def set_theme_mode(
        self, mode: str, page: Optional[ft.Page] = None
    ) -> None:
        """Define o modo ('system', 'light', 'dark') e atualiza a interface."""
        mode_normalized = mode.lower()
        if mode_normalized in ("system", "light", "dark"):
            self.theme_mode = mode_normalized
            await self.save_preferences(page=page, theme_mode=mode_normalized)
            if page:
                self.apply_theme(page)
                page.update()

    async def set_dark_mode(
        self, is_dark: bool, page: Optional[ft.Page] = None
    ) -> None:
        """Define modo escuro diretamente."""
        await self.set_theme_mode("dark" if is_dark else "light", page=page)

    async def set_color_seed(
        self, seed_key: str, page: Optional[ft.Page] = None
    ) -> None:
        """Define a cor seed M3 ativa."""
        if seed_key in COLOR_SEEDS:
            self.current_seed = seed_key
            await self.save_preferences(page=page, seed=seed_key)
            if page:
                self.apply_theme(page)
                page.update()

    async def set_font_family(
        self, font_family: str, page: Optional[ft.Page] = None
    ) -> None:
        """Define a família de fonte padrão global."""
        self.font_family = font_family
        await self.save_preferences(page=page, font_family=font_family)
        if page:
            self.apply_theme(page)
            page.update()

    async def toggle_amoled(
        self, page: Optional[ft.Page], enabled: bool, edition: Optional[str] = None
    ) -> None:
        """Alterna o modo AMOLED (preto absoluto)."""
        self.is_amoled = enabled
        if edition:
            self.current_edition = edition
        await self.save_preferences(page=page, is_amoled=enabled, edition=edition)
        if page:
            self.apply_theme(page, edition=edition)
            page.update()

    def get_accent_color(self, edition: str = "novo") -> str:
        """Retorna a cor de destaque principal de acordo com o tema e a seed M3 ativa."""
        palette = self.get_current_palette()
        if self.theme_style == ThemeModeType.CLASSIC_BOOK:
            return palette.primary
        return COLOR_SEEDS.get(self.current_seed, COLOR_SEEDS["purple"])["hex"]

    def _resolve_is_dark(self, page: Optional[ft.Page]) -> None:
        """Determina se o tema deve ser escuro ou claro."""
        if self.theme_mode == "light":
            self.is_dark = False
        elif self.theme_mode == "dark":
            self.is_dark = True
        else:  # "system"
            if self.is_amoled:
                self.is_dark = True
            elif page and hasattr(page, "platform_brightness") and page.platform_brightness:
                self.is_dark = str(page.platform_brightness).lower() == "dark"
            else:
                self.is_dark = False

    def apply_theme(self, page: ft.Page, edition: Optional[str] = None) -> None:
        """
        Aplica a configuração completa do tema selecionado na página Flet:
        - Registro de fontes nativas e padrão Montserrat via FontManager
        - Ajuste do ThemeMode, ColorScheme e DarkTheme correspondentes
        - Configurações de transparência, blur e plano de fundo
        """
        if not page:
            return

        active_edition = edition or self.current_edition
        FontManager.register_fonts(page)
        self._resolve_is_dark(page)

        palette = self.get_current_palette()
        seed_hex = self.get_accent_color(active_edition)

        transitions = ft.PageTransitionsTheme(
            android=ft.PageTransitionTheme.CUPERTINO,
            ios=ft.PageTransitionTheme.CUPERTINO,
            linux=ft.PageTransitionTheme.CUPERTINO,
            macos=ft.PageTransitionTheme.CUPERTINO,
            windows=ft.PageTransitionTheme.CUPERTINO,
        )

        # 1. Configuração do ThemeMode na página
        if self.theme_mode == "light":
            page.theme_mode = ft.ThemeMode.LIGHT
        elif self.theme_mode == "dark":
            page.theme_mode = ft.ThemeMode.DARK
        else:
            page.theme_mode = ft.ThemeMode.DARK if self.is_amoled else ft.ThemeMode.SYSTEM

        # 2. Definição do Background
        if self.is_amoled and self.is_dark:
            page.bgcolor = "#000000"
        else:
            page.bgcolor = palette.background

        # 3. Construção dos ColorSchemes adaptados a cada tema
        if self.theme_style == ThemeModeType.CLASSIC_BOOK:
            light_scheme = ft.ColorScheme(
                surface=palette.surface,
                surface_dim=palette.surface,
                surface_bright=palette.surface_container_high,
                surface_container_lowest=palette.background,
                surface_container_low=palette.surface,
                surface_container=palette.surface_container,
                surface_container_high=palette.surface_container_high,
                surface_container_highest=palette.surface_container_high,
                on_surface=palette.text_primary,
                on_surface_variant=palette.text_secondary,
                primary=palette.primary,
                on_primary=palette.on_primary,
                outline=palette.border_color,
            )
            dark_scheme = ft.ColorScheme(
                surface=palette.surface,
                surface_dim=palette.surface,
                surface_bright=palette.surface_container_high,
                surface_container_lowest=palette.background,
                surface_container_low=palette.surface,
                surface_container=palette.surface_container,
                surface_container_high=palette.surface_container_high,
                surface_container_highest=palette.surface_container_high,
                on_surface=palette.text_primary,
                on_surface_variant=palette.text_secondary,
                primary=palette.primary,
                on_primary=palette.on_primary,
                outline=palette.border_color,
            )
            page.theme = ft.Theme(
                color_scheme=light_scheme,
                color_scheme_seed=palette.primary,
                use_material3=True,
                font_family=self.font_family,
                page_transitions=transitions,
            )
            page.dark_theme = ft.Theme(
                color_scheme=dark_scheme,
                color_scheme_seed=palette.primary,
                use_material3=True,
                font_family=self.font_family,
                page_transitions=transitions,
                system_overlay_style=ft.SystemOverlayStyle(
                    status_bar_color=palette.background,
                    system_navigation_bar_color=palette.background,
                ),
            )

        elif self.theme_style == ThemeModeType.LIQUID_GLASS:
            # Liquid Glass: Esquema vítreo moderno (estilo Apple / visionOS)
            glass_light_scheme = ft.ColorScheme(
                surface=palette.surface,
                surface_dim=palette.surface,
                surface_bright=palette.surface_container_high,
                surface_container_lowest=palette.background,
                surface_container_low=palette.surface,
                surface_container=palette.surface_container,
                surface_container_high=palette.surface_container_high,
                surface_container_highest=palette.surface_container_high,
                on_surface=palette.text_primary,
                on_surface_variant=palette.text_secondary,
                primary=palette.primary,
                on_primary=palette.on_primary,
                outline=palette.border_color,
                outline_variant=ft.Colors.with_opacity(0.12, ft.Colors.BLACK),
            )
            glass_dark_scheme = ft.ColorScheme(
                surface=palette.surface,
                surface_dim=palette.surface,
                surface_bright=palette.surface_container_high,
                surface_container_lowest=palette.background,
                surface_container_low=palette.surface,
                surface_container=palette.surface_container,
                surface_container_high=palette.surface_container_high,
                surface_container_highest=palette.surface_container_high,
                on_surface=palette.text_primary,
                on_surface_variant=palette.text_secondary,
                primary=palette.primary,
                on_primary=palette.on_primary,
                outline=palette.border_color,
                outline_variant=ft.Colors.with_opacity(0.15, ft.Colors.WHITE),
            )
            page.theme = ft.Theme(
                color_scheme=glass_light_scheme,
                use_material3=True,
                font_family=self.font_family,
                page_transitions=transitions,
            )
            page.dark_theme = ft.Theme(
                color_scheme=glass_dark_scheme,
                use_material3=True,
                font_family=self.font_family,
                page_transitions=transitions,
                system_overlay_style=ft.SystemOverlayStyle(
                    status_bar_color=palette.background,
                    system_navigation_bar_color=palette.background,
                ),
            )

        else:
            # Material You
            if self.is_amoled and self.is_dark:
                amoled_scheme = ft.ColorScheme(
                    surface="#000000",
                    surface_dim="#000000",
                    surface_bright="#222222",
                    surface_container_lowest="#000000",
                    surface_container_low="#0D0D0D",
                    surface_container="#141414",
                    surface_container_high="#1A1A1A",
                    surface_container_highest="#222222",
                    on_surface=ft.Colors.WHITE,
                    on_surface_variant=ft.Colors.GREY_400,
                    primary=seed_hex,
                    on_primary=ft.Colors.BLACK,
                    outline="#2D2D2D",
                )
                page.dark_theme = ft.Theme(
                    color_scheme_seed=seed_hex,
                    use_material3=True,
                    font_family=self.font_family,
                    page_transitions=transitions,
                    color_scheme=amoled_scheme,
                    system_overlay_style=ft.SystemOverlayStyle(
                        status_bar_color="#000000",
                        system_navigation_bar_color="#000000",
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

