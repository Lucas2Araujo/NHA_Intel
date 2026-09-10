"""
Módulo de renderização adaptativa para Hinos Infantis (Hinos 508 a 557)
e cartões de estrofes do Hinário Inteligente.
"""

import re
from typing import Any, Optional

import flet as ft

from src.theme.palette import ThemeModeType, get_palette

KIDS_HYMNS_START = 508
KIDS_HYMNS_END = 557


def is_kids_hymn(numero: int | str | None) -> bool:
    """
    Verifica se o número do hino pertence ao intervalo infantil oficial (508 a 557).
    Trata inteiros, strings e variantes como '508A', '508_A', '508.1'.
    """
    if numero is None:
        return False
    try:
        clean = str(numero).strip()
        match = re.match(r"^(\d+)", clean)
        if match:
            num_int = int(match.group(1))
            return KIDS_HYMNS_START <= num_int <= KIDS_HYMNS_END
        return False
    except (ValueError, TypeError):
        return False


def build_kids_badge() -> ft.Container:
    """
    Constrói a badge lúdica de topo para os Hinos Infantis:
    Ícone solar/estrela com fundo amarelo pastel (#FFE58F) e cantos arredondados.
    """
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(
                    ft.Icons.WB_SUNNY_ROUNDED,
                    size=18,
                    color="#B85D19",
                ),
                ft.Text(
                    "Hino Infantil",
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color="#6E3300",
                ),
                ft.Icon(
                    ft.Icons.STAR_ROUNDED,
                    size=16,
                    color="#D97706",
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
        ),
        bgcolor="#FFE58F",
        border_radius=20,
        padding=ft.Padding.symmetric(horizontal=14, vertical=6),
        alignment=ft.Alignment.CENTER,
        margin=ft.Margin.only(bottom=16),
    )


def _resolve_verse_title(estrofe: str, index: int) -> str:
    """Determina o título da estrofe (ex: 'Estrofe 1', 'Coro', etc.)."""
    first_line = estrofe.strip().split("\n")[0].strip().lower()
    if first_line.startswith("coro") or first_line.startswith("refrão"):
        return "Coro ☀️"
    return f"Estrofe {index}"


def _build_kids_verse_card(
    estrofe: str,
    index: int,
    theme_style: ThemeModeType,
    is_dark: bool,
    font_size: int = 18,
    font_family: Optional[str] = None,
    blur_enabled: bool = True,
) -> ft.Container:
    """Renderiza a estrofe infantil no formato de card pílula (r=32) adaptado ao tema."""
    is_odd = (index % 2 != 0)
    title = _resolve_verse_title(estrofe, index)
    kids_font = font_family or "AppSans-Bold"

    if theme_style == ThemeModeType.CLASSIC_BOOK:
        if not is_dark:
            # Kids Stich Clássico Claro
            bg_color = "#FFF8EB" if is_odd else "#EAF7EE"
            border_color = "#F5E5C9" if is_odd else "#CDECD6"
            title_color = "#823400" if is_odd else "#064E52"
            text_color = "#1C1B1F"
        else:
            # Kids Stich Clássico Escuro
            bg_color = "#2A1F18" if is_odd else "#162822"
            border_color = "#4A3525" if is_odd else "#234A3C"
            title_color = "#FFB74D" if is_odd else "#80CBC4"
            text_color = "#FFF3E0" if is_odd else "#E0F2F1"

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        title,
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=title_color,
                        font_family=kids_font,
                    ),
                    ft.Text(
                        estrofe,
                        size=font_size,
                        weight=ft.FontWeight.W_500,
                        color=text_color,
                        font_family=font_family or "Montserrat",
                        text_align=ft.TextAlign.CENTER,
                        style=ft.TextStyle(height=1.5),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            bgcolor=bg_color,
            border=ft.Border.all(1.5, border_color),
            border_radius=32,
            padding=ft.Padding.symmetric(horizontal=24, vertical=20),
            margin=ft.Margin.only(bottom=16),
            alignment=ft.Alignment.CENTER,
        )

    elif theme_style == ThemeModeType.MATERIAL_YOU:
        # Material You: M3 Container tokens sólidos com cantos r=32
        if is_odd:
            surface_color = ft.Colors.TERTIARY_CONTAINER
            title_color = ft.Colors.ON_TERTIARY_CONTAINER
            text_color = ft.Colors.ON_SURFACE
        else:
            surface_color = ft.Colors.SECONDARY_CONTAINER
            title_color = ft.Colors.ON_SECONDARY_CONTAINER
            text_color = ft.Colors.ON_SURFACE

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        title,
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=title_color,
                        font_family=kids_font,
                    ),
                    ft.Text(
                        estrofe,
                        size=font_size,
                        weight=ft.FontWeight.W_500,
                        color=text_color,
                        font_family=font_family or "Montserrat",
                        text_align=ft.TextAlign.CENTER,
                        style=ft.TextStyle(height=1.5),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            bgcolor=surface_color,
            border_radius=32,
            padding=ft.Padding.symmetric(horizontal=24, vertical=20),
            margin=ft.Margin.only(bottom=16),
            alignment=ft.Alignment.CENTER,
        )

    else:
        # Liquid Glass: Superfícies translúcidas âmbar / ciano com gradiente especular e bordas de refração
        if not is_dark:
            gradient = ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    ft.Colors.with_opacity(0.82, "#FFF3E0") if is_odd else ft.Colors.with_opacity(0.82, "#E0F2F1"),
                    ft.Colors.with_opacity(0.55, "#FFF8E1") if is_odd else ft.Colors.with_opacity(0.55, "#E8F5E9"),
                ],
            )
            border_color = ft.Colors.with_opacity(0.70, ft.Colors.WHITE)
            title_color = "#8B2500" if is_odd else "#06544E"
            text_color = "#0F172A"
            shadow = ft.BoxShadow(
                spread_radius=0,
                blur_radius=16,
                color=ft.Colors.with_opacity(0.06, "#0F172A"),
                offset=ft.Offset(0, 6),
            )
        else:
            gradient = ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    ft.Colors.with_opacity(0.70, "#3E2723") if is_odd else ft.Colors.with_opacity(0.70, "#004D40"),
                    ft.Colors.with_opacity(0.40, "#271612") if is_odd else ft.Colors.with_opacity(0.40, "#002D26"),
                ],
            )
            border_color = ft.Colors.with_opacity(0.24, ft.Colors.WHITE)
            title_color = "#FDBA74" if is_odd else "#5EEAD4"
            text_color = "#F8FAFC"
            shadow = ft.BoxShadow(
                spread_radius=0,
                blur_radius=18,
                color=ft.Colors.with_opacity(0.35, "#000000"),
                offset=ft.Offset(0, 8),
            )

        blur = ft.Blur(18, 18, tile_mode=ft.BlurTileMode.CLAMP) if blur_enabled else None

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        title,
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=title_color,
                        font_family=kids_font,
                    ),
                    ft.Text(
                        estrofe,
                        size=font_size,
                        weight=ft.FontWeight.W_500,
                        color=text_color,
                        font_family=font_family or "Montserrat",
                        text_align=ft.TextAlign.CENTER,
                        style=ft.TextStyle(height=1.5),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            gradient=gradient,
            border=ft.Border.all(1.0, border_color),
            border_radius=32,
            blur=blur,
            shadow=shadow,
            padding=ft.Padding.symmetric(horizontal=24, vertical=20),
            margin=ft.Margin.only(bottom=16),
            alignment=ft.Alignment.CENTER,
        )


def _build_editorial_verse_card(
    estrofe: str,
    index: int,
    theme_engine: Any,
    font_size: int = 18,
    font_family: Optional[str] = None,
) -> ft.Container:
    """Renderiza uma estrofe para hinos regulares (não-infantis) com layout limpo e editorial."""
    palette = getattr(theme_engine, "get_current_palette", None)
    current_pal = palette() if callable(palette) else None

    text_color = current_pal.text_primary if current_pal else ft.Colors.ON_SURFACE

    return ft.Container(
        content=ft.Text(
            estrofe,
            size=font_size,
            weight=ft.FontWeight.W_400,
            color=text_color,
            font_family=font_family or "Montserrat",
            text_align=ft.TextAlign.CENTER,
            style=ft.TextStyle(height=1.5),
        ),
        margin=ft.Margin.only(bottom=24),
        alignment=ft.Alignment.CENTER,
    )


def build_verse_card(
    estrofe: str,
    index: int,
    hino_numero: int | str,
    theme_engine: Any,
    font_size: int = 18,
    font_family: Optional[str] = None,
) -> ft.Control:
    """
    Ponto de entrada principal para renderização de estrofes de hinos.
    Se for hino infantil (508 a 557), aplica o layout lúdico tipo pílula adaptado ao tema;
    caso contrário, gera uma leitura limpa, elegante e editorial.
    """
    if is_kids_hymn(hino_numero):
        theme_style = getattr(theme_engine, "theme_style", ThemeModeType.MATERIAL_YOU)
        if isinstance(theme_style, str):
            try:
                theme_style = ThemeModeType(theme_style.lower())
            except ValueError:
                theme_style = ThemeModeType.MATERIAL_YOU

        is_dark = bool(getattr(theme_engine, "is_dark", False))
        blur_enabled = bool(getattr(theme_engine, "glass_blur_enabled", True))
        return _build_kids_verse_card(
            estrofe=estrofe,
            index=index,
            theme_style=theme_style,
            is_dark=is_dark,
            font_size=font_size,
            font_family=font_family,
            blur_enabled=blur_enabled,
        )

    return _build_editorial_verse_card(
        estrofe=estrofe,
        index=index,
        theme_engine=theme_engine,
        font_size=font_size,
        font_family=font_family,
    )
