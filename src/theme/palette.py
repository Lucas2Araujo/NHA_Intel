"""
Definições de paletas de cores, tokens visuais e matriz de contraste WCAG AAA
para o Dynamic Theming Engine do Hinário Inteligente.
"""

from dataclasses import dataclass
from enum import Enum
import re
from typing import Tuple

import flet as ft


class ThemeModeType(Enum):
    """Estilos globais de tema suportados."""
    MATERIAL_YOU = "material_you"
    LIQUID_GLASS = "liquid_glass"
    CLASSIC_BOOK = "classic_book"


@dataclass(frozen=True)
class ThemePalette:
    """Tokens de design e cores para um tema e modo específicos."""
    name: str
    is_dark: bool
    background: str
    surface: str
    surface_container: str
    surface_container_high: str
    primary: str
    on_primary: str
    text_primary: str
    text_secondary: str
    border_color: str
    blur_active: bool
    blur_sigma: float
    is_glass: bool


# --- PALETAS MATERIAL YOU ---
PALETTE_MATERIAL_YOU_LIGHT = ThemePalette(
    name="Material You Claro",
    is_dark=False,
    background="#FCF8FD",
    surface="#F8F2F8",
    surface_container="#EFE8EF",
    surface_container_high="#E8E1E8",
    primary="#6750A4",
    on_primary="#FFFFFF",
    text_primary=ft.Colors.ON_SURFACE,
    text_secondary=ft.Colors.ON_SURFACE_VARIANT,
    border_color="transparent",
    blur_active=False,
    blur_sigma=0.0,
    is_glass=False,
)

PALETTE_MATERIAL_YOU_DARK = ThemePalette(
    name="Material You Escuro",
    is_dark=True,
    background="#141218",
    surface="#1D1B20",
    surface_container="#211F26",
    surface_container_high="#2B2930",
    primary="#D0BCFF",
    on_primary="#381E72",
    text_primary=ft.Colors.ON_SURFACE,
    text_secondary=ft.Colors.ON_SURFACE_VARIANT,
    border_color="transparent",
    blur_active=False,
    blur_sigma=0.0,
    is_glass=False,
)

# --- PALETAS LIQUID GLASS ---
PALETTE_LIQUID_GLASS_LIGHT = ThemePalette(
    name="Liquid Glass Claro",
    is_dark=False,
    background="#F4F8FC",
    surface=ft.Colors.with_opacity(0.82, "#FFFFFF"),
    surface_container=ft.Colors.with_opacity(0.85, "#E2E8F0"),
    surface_container_high=ft.Colors.with_opacity(0.85, "#CBD5E1"),
    primary="#1D4ED8",
    on_primary="#FFFFFF",
    text_primary="#0F172A",
    text_secondary="#334155",
    border_color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE),
    blur_active=True,
    blur_sigma=20.0,
    is_glass=True,
)

PALETTE_LIQUID_GLASS_DARK = ThemePalette(
    name="Liquid Glass Escuro",
    is_dark=True,
    background="#060911",
    surface=ft.Colors.with_opacity(0.75, "#1E293B"),
    surface_container=ft.Colors.with_opacity(0.80, "#131C2E"),
    surface_container_high=ft.Colors.with_opacity(0.80, "#1E2C44"),
    primary="#60A5FA",
    on_primary="#090D16",
    text_primary="#F8FAFC",
    text_secondary="#CBD5E1",
    border_color=ft.Colors.with_opacity(0.24, "#94A3B8"),
    blur_active=True,
    blur_sigma=20.0,
    is_glass=True,
)

# --- PALETAS CLASSIC BOOK ---
PALETTE_CLASSIC_BOOK_LIGHT = ThemePalette(
    name="Classic Book Claro",
    is_dark=False,
    background="#F9F6F0",
    surface="#EFE9DE",
    surface_container="#E5DDD0",
    surface_container_high="#DDD3C3",
    primary="#795548",
    on_primary="#FFFFFF",
    text_primary="#241C14",
    text_secondary="#4E342E",
    border_color="#D7CCC8",
    blur_active=False,
    blur_sigma=0.0,
    is_glass=False,
)

PALETTE_CLASSIC_BOOK_DARK = ThemePalette(
    name="Classic Book Escuro",
    is_dark=True,
    background="#1A1613",
    surface="#241E18",
    surface_container="#2E2620",
    surface_container_high="#382F27",
    primary="#D7CCC8",
    on_primary="#1A1613",
    text_primary="#EFE6DC",
    text_secondary="#D7CCC8",
    border_color="#3E3228",
    blur_active=False,
    blur_sigma=0.0,
    is_glass=False,
)

PALETTES_CATALOG: dict[tuple[ThemeModeType, bool], ThemePalette] = {
    (ThemeModeType.MATERIAL_YOU, False): PALETTE_MATERIAL_YOU_LIGHT,
    (ThemeModeType.MATERIAL_YOU, True): PALETTE_MATERIAL_YOU_DARK,
    (ThemeModeType.LIQUID_GLASS, False): PALETTE_LIQUID_GLASS_LIGHT,
    (ThemeModeType.LIQUID_GLASS, True): PALETTE_LIQUID_GLASS_DARK,
    (ThemeModeType.CLASSIC_BOOK, False): PALETTE_CLASSIC_BOOK_LIGHT,
    (ThemeModeType.CLASSIC_BOOK, True): PALETTE_CLASSIC_BOOK_DARK,
}


def get_palette(style: ThemeModeType | str, is_dark: bool) -> ThemePalette:
    """Retorna a paleta correspondente ao estilo e modo informados."""
    if isinstance(style, str):
        try:
            normalized_style = ThemeModeType(style.lower())
        except ValueError:
            normalized_style = ThemeModeType.MATERIAL_YOU
    else:
        normalized_style = style

    return PALETTES_CATALOG.get(
        (normalized_style, is_dark), PALETTE_MATERIAL_YOU_LIGHT
    )


# --- UTILITÁRIOS MATEMÁTICOS DE CONTRASTE WCAG ---

def parse_color_rgb(color_str: str) -> Tuple[float, float, float, float]:
    """
    Decodifica uma string de cor (hexadecimal #RGB, #RRGGBB ou #AARRGGBB)
    em tupla (r, g, b, alpha) normalizada de 0.0 a 1.0.
    """
    clean = color_str.strip().lower()

    # Mapeamento para nomes comuns do Flet caso passem nome textual
    color_map = {
        "white": (1.0, 1.0, 1.0, 1.0),
        "black": (0.0, 0.0, 0.0, 1.0),
        "transparent": (0.0, 0.0, 0.0, 0.0),
        ft.Colors.ON_SURFACE: (0.1, 0.1, 0.1, 1.0),  # Fallback dinâmico aproximado
        ft.Colors.WHITE: (1.0, 1.0, 1.0, 1.0),
        ft.Colors.BLACK: (0.0, 0.0, 0.0, 1.0),
    }
    if clean in color_map:
        return color_map[clean]

    if "," in clean:
        parts = clean.split(",")
        hex_part = parts[0].strip()
        try:
            a = float(parts[1].strip())
        except ValueError:
            a = 1.0
        r, g, b, _ = parse_color_rgb(hex_part)
        return (r, g, b, a)

    if clean.startswith("#"):
        hex_val = clean[1:]
        if len(hex_val) == 3:
            r = int(hex_val[0] * 2, 16) / 255.0
            g = int(hex_val[1] * 2, 16) / 255.0
            b = int(hex_val[2] * 2, 16) / 255.0
            return (r, g, b, 1.0)
        elif len(hex_val) == 6:
            r = int(hex_val[0:2], 16) / 255.0
            g = int(hex_val[2:4], 16) / 255.0
            b = int(hex_val[4:6], 16) / 255.0
            return (r, g, b, 1.0)
        elif len(hex_val) == 8:
            # Flet utiliza formato #AARRGGBB para hex com alpha
            a = int(hex_val[0:2], 16) / 255.0
            r = int(hex_val[2:4], 16) / 255.0
            g = int(hex_val[4:6], 16) / 255.0
            b = int(hex_val[6:8], 16) / 255.0
            return (r, g, b, a)

    return (0.0, 0.0, 0.0, 1.0)


def composite_colors(
    fg_color: str, bg_color: str
) -> Tuple[float, float, float]:
    """Composição alfa de cor frontal sobre cor de fundo."""
    fg_r, fg_g, fg_b, fg_a = parse_color_rgb(fg_color)
    bg_r, bg_g, bg_b, _ = parse_color_rgb(bg_color)

    r = fg_r * fg_a + bg_r * (1.0 - fg_a)
    g = fg_g * fg_a + bg_g * (1.0 - fg_a)
    b = fg_b * fg_a + bg_b * (1.0 - fg_a)
    return (r, g, b)


def calculate_relative_luminance(color: str, bg_if_alpha: str = "#FFFFFF") -> float:
    """Calcula a luminância relativa normalizada segundo a especificação WCAG 2.1."""
    _, _, _, a = parse_color_rgb(color)
    if a < 1.0:
        r, g, b = composite_colors(color, bg_if_alpha)
    else:
        r, g, b, _ = parse_color_rgb(color)

    def channel_luminance(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel_luminance(r) + 0.7152 * channel_luminance(g) + 0.0722 * channel_luminance(b)


def calculate_contrast_ratio(
    foreground: str, background: str, context_bg: str = "#FFFFFF"
) -> float:
    """
    Calcula o índice de contraste (contrast ratio) entre duas cores segundo o padrão WCAG.
    Retorna valor de 1.0 a 21.0.
    """
    lum_bg = calculate_relative_luminance(background, context_bg)
    lum_fg = calculate_relative_luminance(foreground, background)

    l1 = max(lum_fg, lum_bg)
    l2 = min(lum_fg, lum_bg)
    return (l1 + 0.05) / (l2 + 0.05)


def is_wcag_aaa(
    foreground: str,
    background: str,
    is_large_text: bool = False,
    context_bg: str = "#FFFFFF",
) -> bool:
    """
    Verifica se o contraste atende ao critério de conformidade WCAG AAA:
    - 7.0:1 para texto normal
    - 4.5:1 para texto grande (>= 18pt ou 14pt bold)
    """
    ratio = calculate_contrast_ratio(foreground, background, context_bg)
    threshold = 4.5 if is_large_text else 7.0
    return ratio >= threshold
