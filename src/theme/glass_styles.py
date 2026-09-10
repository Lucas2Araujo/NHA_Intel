"""
Módulo de componentes e utilitários visuais para o tema Liquid Glass (estilo Apple / visionOS).
Fornece fundos com gradientes fluidos ambientes, cartões translúcidos com reflexos especulares,
bordas de refração cristalina (rim light) e controle de desempenho (toggle de desfoque/sombras).
"""

from typing import Any, Optional
import flet as ft

from src.theme.palette import ThemeModeType, get_palette


def get_liquid_glass_background_gradient(is_dark: bool) -> ft.LinearGradient:
    """
    Retorna o gradiente ambiente fluido e límpido para o plano de fundo do Liquid Glass.
    Permite que o efeito de refração e desfoque dos cartões seja perceptível.
    """
    if not is_dark:
        # Fundo líquido claro: brilho suave azul-gelo / lavanda translúcido
        return ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=["#F8FAFC", "#EEF2F6", "#E0F2FE"],
            stops=[0.0, 0.55, 1.0],
        )
    else:
        # Fundo líquido escuro: profundidade abissal oceânica / safira espacial
        return ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=["#060911", "#0B1220", "#0F1E36"],
            stops=[0.0, 0.50, 1.0],
        )


def get_glass_card_props(
    is_dark: bool,
    blur_enabled: bool = True,
    shadow_enabled: bool = True,
) -> dict:
    """
    Retorna as propriedades visuais de um cartão Liquid Glass estilo Apple:
    - Gradiente especular (luz incidindo no canto superior)
    - Borda de refração vítrea fina (specular rim)
    - Desfoque de fundo (Backdrop Blur) condicional para performance
    - Sombra com dispersão líquida suave condicional
    """
    if not is_dark:
        gradient = ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[
                ft.Colors.with_opacity(0.88, "#FFFFFF"),
                ft.Colors.with_opacity(0.58, "#F1F5F9"),
            ],
            stops=[0.0, 1.0],
        )
        border = ft.Border.all(1.2, ft.Colors.with_opacity(0.75, "#FFFFFF"))
        shadow = (
            ft.BoxShadow(
                spread_radius=0,
                blur_radius=20,
                color=ft.Colors.with_opacity(0.08, "#0F172A"),
                offset=ft.Offset(0, 8),
            )
            if shadow_enabled
            else None
        )
    else:
        gradient = ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[
                ft.Colors.with_opacity(0.75, "#1E293B"),
                ft.Colors.with_opacity(0.45, "#0F172A"),
            ],
            stops=[0.0, 1.0],
        )
        border = ft.Border.all(1.0, ft.Colors.with_opacity(0.24, "#94A3B8"))
        shadow = (
            ft.BoxShadow(
                spread_radius=0,
                blur_radius=24,
                color=ft.Colors.with_opacity(0.40, "#000000"),
                offset=ft.Offset(0, 10),
            )
            if shadow_enabled
            else None
        )

    blur = (
        ft.Blur(sigma_x=20, sigma_y=20, tile_mode=ft.BlurTileMode.CLAMP)
        if blur_enabled
        else None
    )

    return {
        "gradient": gradient,
        "border": border,
        "shadow": shadow,
        "blur": blur,
        "border_radius": 20,
    }


def get_card_decoration(
    theme_engine: Any,
    is_dark: Optional[bool] = None,
) -> dict:
    """
    Abstração universal que retorna a decoração ideal do cartão de acordo com o tema ativo:
    - Liquid Glass: Vidro líquido Apple com suporte a desativação de blur para performance
    - Classic Book: Pergaminho suave com bordas clássicas acolhedoras
    - Material You: Superfície M3 com cantos arredondados padrão
    """
    theme_style = getattr(theme_engine, "theme_style", ThemeModeType.MATERIAL_YOU)
    if isinstance(theme_style, str):
        try:
            theme_style = ThemeModeType(theme_style.lower())
        except ValueError:
            theme_style = ThemeModeType.MATERIAL_YOU

    resolved_dark = (
        is_dark if is_dark is not None else bool(getattr(theme_engine, "is_dark", False))
    )
    palette = get_palette(theme_style, resolved_dark)

    if theme_style == ThemeModeType.LIQUID_GLASS:
        blur_enabled = bool(getattr(theme_engine, "glass_blur_enabled", True))
        glass_props = get_glass_card_props(
            is_dark=resolved_dark,
            blur_enabled=blur_enabled,
            shadow_enabled=True,
        )
        return {
            "bgcolor": None,
            "gradient": glass_props["gradient"],
            "border": glass_props["border"],
            "border_radius": glass_props["border_radius"],
            "blur": glass_props["blur"],
            "shadow": glass_props["shadow"],
            "clip_behavior": ft.ClipBehavior.HARD_EDGE if glass_props["blur"] else ft.ClipBehavior.NONE,
        }

    elif theme_style == ThemeModeType.CLASSIC_BOOK:
        return {
            "bgcolor": palette.surface_container_high,
            "gradient": None,
            "border": ft.Border.all(1.0, palette.border_color),
            "border_radius": 16,
            "blur": None,
            "shadow": None,
            "clip_behavior": ft.ClipBehavior.NONE,
        }

    else:
        # Material You
        return {
            "bgcolor": ft.Colors.SURFACE_CONTAINER_HIGH,
            "gradient": None,
            "border": None,
            "border_radius": 16,
            "blur": None,
            "shadow": None,
            "clip_behavior": ft.ClipBehavior.NONE,
        }

