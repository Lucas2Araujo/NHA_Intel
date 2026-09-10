"""
Testes unitários e de integração para o Dynamic Theming Engine (v0.3.0),
Gestão Tipográfica, Adaptação Lúdica de Hinos Infantis (508 a 557) e Conformidade WCAG AAA.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import flet as ft
import pytest

from src.models.hino import Hino
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.hino_repository import HinoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.theme.glass_styles import (
    get_card_decoration,
    get_glass_card_props,
    get_liquid_glass_background_gradient,
)
from src.theme.kids_styles import (
    KIDS_HYMNS_END,
    KIDS_HYMNS_START,
    build_kids_badge,
    build_verse_card,
    is_kids_hymn,
)
from src.theme.palette import (
    PALETTE_CLASSIC_BOOK_DARK,
    PALETTE_CLASSIC_BOOK_LIGHT,
    PALETTE_LIQUID_GLASS_DARK,
    PALETTE_LIQUID_GLASS_LIGHT,
    PALETTE_MATERIAL_YOU_DARK,
    PALETTE_MATERIAL_YOU_LIGHT,
    PALETTES_CATALOG,
    ThemeModeType,
    calculate_contrast_ratio,
    calculate_relative_luminance,
    composite_colors,
    get_palette,
    is_wcag_aaa,
    parse_color_rgb,
)
from src.theme.theme_engine import (
    COLOR_SEEDS,
    STORAGE_KEY_AMOLED,
    STORAGE_KEY_COLOR_SEED,
    STORAGE_KEY_FONT_FAMILY,
    STORAGE_KEY_GLASS_BLUR,
    STORAGE_KEY_THEME_MODE,
    STORAGE_KEY_THEME_STYLE,
    ThemeEngine,
)
from src.utils.font_manager import (
    DEFAULT_FONT_FAMILY,
    INITIAL_FONTS,
    FontManager,
)
from src.views.hino_view import HinoView


# ==============================================================================
# 1. TESTES DE CONTRASTE WCAG AAA E PALETAS
# ==============================================================================

def test_palette_contrast_wcag_aaa():
    """
    Garante matematicamente conformidade estrita com WCAG AAA (contrast ratio >= 7.0:1)
    para todas as paletas de design e cartões infantis.
    """
    # 1.1 Paletas Liquid Glass e Classic Book (Claro e Escuro)
    # Liquid Glass Claro (Primário e Secundário)
    cr_lg_light_surface = calculate_contrast_ratio(
        PALETTE_LIQUID_GLASS_LIGHT.text_primary, PALETTE_LIQUID_GLASS_LIGHT.surface
    )
    cr_lg_light_bg = calculate_contrast_ratio(
        PALETTE_LIQUID_GLASS_LIGHT.text_primary, PALETTE_LIQUID_GLASS_LIGHT.background
    )
    cr_lg_light_sec = calculate_contrast_ratio(
        PALETTE_LIQUID_GLASS_LIGHT.text_secondary, PALETTE_LIQUID_GLASS_LIGHT.surface
    )
    assert cr_lg_light_surface >= 7.0, f"Liquid Glass Light Surface falhou WCAG AAA: {cr_lg_light_surface:.2f}"
    assert cr_lg_light_bg >= 7.0, f"Liquid Glass Light BG falhou WCAG AAA: {cr_lg_light_bg:.2f}"
    assert cr_lg_light_sec >= 7.0, f"Liquid Glass Light Secundário falhou WCAG AAA: {cr_lg_light_sec:.2f}"

    # Liquid Glass Escuro (fundo da página #060911)
    cr_lg_dark_surface = calculate_contrast_ratio(
        PALETTE_LIQUID_GLASS_DARK.text_primary,
        PALETTE_LIQUID_GLASS_DARK.surface,
        context_bg=PALETTE_LIQUID_GLASS_DARK.background,
    )
    cr_lg_dark_bg = calculate_contrast_ratio(
        PALETTE_LIQUID_GLASS_DARK.text_primary, PALETTE_LIQUID_GLASS_DARK.background
    )
    cr_lg_dark_sec = calculate_contrast_ratio(
        PALETTE_LIQUID_GLASS_DARK.text_secondary,
        PALETTE_LIQUID_GLASS_DARK.surface,
        context_bg=PALETTE_LIQUID_GLASS_DARK.background,
    )
    assert cr_lg_dark_surface >= 7.0, f"Liquid Glass Dark Surface falhou WCAG AAA: {cr_lg_dark_surface:.2f}"
    assert cr_lg_dark_bg >= 7.0, f"Liquid Glass Dark BG falhou WCAG AAA: {cr_lg_dark_bg:.2f}"
    assert cr_lg_dark_sec >= 7.0, f"Liquid Glass Dark Secundário falhou WCAG AAA: {cr_lg_dark_sec:.2f}"

    # Classic Book Claro
    cr_cb_light_surface = calculate_contrast_ratio(
        PALETTE_CLASSIC_BOOK_LIGHT.text_primary, PALETTE_CLASSIC_BOOK_LIGHT.surface
    )
    cr_cb_light_bg = calculate_contrast_ratio(
        PALETTE_CLASSIC_BOOK_LIGHT.text_primary, PALETTE_CLASSIC_BOOK_LIGHT.background
    )
    cr_cb_light_sec = calculate_contrast_ratio(
        PALETTE_CLASSIC_BOOK_LIGHT.text_secondary, PALETTE_CLASSIC_BOOK_LIGHT.surface
    )
    assert cr_cb_light_surface >= 7.0, f"Classic Book Light Surface falhou WCAG AAA: {cr_cb_light_surface:.2f}"
    assert cr_cb_light_bg >= 7.0, f"Classic Book Light BG falhou WCAG AAA: {cr_cb_light_bg:.2f}"
    assert cr_cb_light_sec >= 7.0, f"Classic Book Light Secundário falhou WCAG AAA: {cr_cb_light_sec:.2f}"

    # Classic Book Escuro
    cr_cb_dark_surface = calculate_contrast_ratio(
        PALETTE_CLASSIC_BOOK_DARK.text_primary, PALETTE_CLASSIC_BOOK_DARK.surface
    )
    cr_cb_dark_bg = calculate_contrast_ratio(
        PALETTE_CLASSIC_BOOK_DARK.text_primary, PALETTE_CLASSIC_BOOK_DARK.background
    )
    cr_cb_dark_sec = calculate_contrast_ratio(
        PALETTE_CLASSIC_BOOK_DARK.text_secondary, PALETTE_CLASSIC_BOOK_DARK.surface
    )
    assert cr_cb_dark_surface >= 7.0, f"Classic Book Dark Surface falhou WCAG AAA: {cr_cb_dark_surface:.2f}"
    assert cr_cb_dark_bg >= 7.0, f"Classic Book Dark BG falhou WCAG AAA: {cr_cb_dark_bg:.2f}"
    assert cr_cb_dark_sec >= 7.0, f"Classic Book Dark Secundário falhou WCAG AAA: {cr_cb_dark_sec:.2f}"

    # 1.2 Material You com tokens concretos M3
    m3_light_cr = calculate_contrast_ratio("#1D1B20", PALETTE_MATERIAL_YOU_LIGHT.surface)
    m3_dark_cr = calculate_contrast_ratio("#E6E1E5", PALETTE_MATERIAL_YOU_DARK.surface)
    assert m3_light_cr >= 7.0, f"Material You Light falhou WCAG AAA: {m3_light_cr:.2f}"
    assert m3_dark_cr >= 7.0, f"Material You Dark falhou WCAG AAA: {m3_dark_cr:.2f}"

    # 1.3 Badge de Hinos Infantis (#FFE58F)
    cr_badge = calculate_contrast_ratio("#6E3300", "#FFE58F")
    assert cr_badge >= 7.0, f"Badge Infantil falhou WCAG AAA: {cr_badge:.2f}"
    assert is_wcag_aaa("#6E3300", "#FFE58F") is True

    # 1.4 Cartões de Estrofes Infantis (Ímpar e Par em todos os temas)
    kids_checks = [
        # Classic Book Claro
        ("CB Light Odd Title", "#823400", "#FFF8EB", "#FFFFFF"),
        ("CB Light Even Title", "#064E52", "#EAF7EE", "#FFFFFF"),
        ("CB Light Odd Text", "#1C1B1F", "#FFF8EB", "#FFFFFF"),
        ("CB Light Even Text", "#1C1B1F", "#EAF7EE", "#FFFFFF"),
        # Classic Book Escuro
        ("CB Dark Odd Title", "#FFB74D", "#2A1F18", "#000000"),
        ("CB Dark Even Title", "#80CBC4", "#162822", "#000000"),
        ("CB Dark Odd Text", "#FFF3E0", "#2A1F18", "#000000"),
        ("CB Dark Even Text", "#E0F2F1", "#162822", "#000000"),
        # Liquid Glass Claro
        ("LG Light Odd Title", "#8B2500", "#FFF3E0,0.7", "#F1F5F9"),
        ("LG Light Even Title", "#06544E", "#E0F2F1,0.7", "#F1F5F9"),
        ("LG Light Odd Text", "#0F172A", "#FFF3E0,0.7", "#F1F5F9"),
        ("LG Light Even Text", "#0F172A", "#E0F2F1,0.7", "#F1F5F9"),
        # Liquid Glass Escuro
        ("LG Dark Odd Title", "#FDBA74", "#3E2723,0.6", "#090D16"),
        ("LG Dark Even Title", "#5EEAD4", "#004D40,0.6", "#090D16"),
        ("LG Dark Odd Text", "#F8FAFC", "#3E2723,0.6", "#090D16"),
        ("LG Dark Even Text", "#F8FAFC", "#004D40,0.6", "#090D16"),
    ]
    for desc, fg, bg, ctx in kids_checks:
        cr = calculate_contrast_ratio(fg, bg, context_bg=ctx)
        assert cr >= 7.0, f"Cartão Infantil '{desc}' falhou WCAG AAA: {cr:.2f}:1"


def test_color_parsing_and_luminance():
    """Valida o parser de cores hex e alfa e a luminância relativa WCAG."""
    # 6-digit hex
    r, g, b, a = parse_color_rgb("#FFFFFF")
    assert (r, g, b, a) == (1.0, 1.0, 1.0, 1.0)
    assert calculate_relative_luminance("#FFFFFF") == pytest.approx(1.0, rel=1e-3)

    r, g, b, a = parse_color_rgb("#000000")
    assert (r, g, b, a) == (0.0, 0.0, 0.0, 1.0)
    assert calculate_relative_luminance("#000000") == pytest.approx(0.0, abs=1e-4)

    # 3-digit hex
    r, g, b, a = parse_color_rgb("#FFF")
    assert (r, g, b, a) == (1.0, 1.0, 1.0, 1.0)

    # Comma-separated opacity (Flet with_opacity format: "#HEX,opacity")
    r, g, b, a = parse_color_rgb("#000000,0.5")
    assert a == pytest.approx(0.5)

    # 8-digit hex (#AARRGGBB)
    r, g, b, a = parse_color_rgb("#80FFFFFF")
    assert a == pytest.approx(128 / 255.0, rel=1e-2)

    # Composite colors
    comp = composite_colors("#000000,0.5", "#FFFFFF")
    assert comp[0] == pytest.approx(0.5, rel=1e-2)

    # Contrast ratio bounds (between 1.0 and 21.0)
    cr_max = calculate_contrast_ratio("#000000", "#FFFFFF")
    assert cr_max == pytest.approx(21.0, rel=1e-1)
    cr_same = calculate_contrast_ratio("#FFFFFF", "#FFFFFF")
    assert cr_same == pytest.approx(1.0, abs=1e-3)


def test_get_palette_lookup():
    """Valida a resolução de paletas a partir de enums e strings."""
    pal = get_palette(ThemeModeType.MATERIAL_YOU, is_dark=False)
    assert pal == PALETTE_MATERIAL_YOU_LIGHT

    pal_dark = get_palette("liquid_glass", is_dark=True)
    assert pal_dark == PALETTE_LIQUID_GLASS_DARK

    pal_classic = get_palette("classic_book", is_dark=False)
    assert pal_classic == PALETTE_CLASSIC_BOOK_LIGHT

    # Fallback para string inválida
    pal_invalid = get_palette("unknown_theme", is_dark=False)
    assert pal_invalid == PALETTE_MATERIAL_YOU_LIGHT


# ==============================================================================
# 2. TESTES DE GESTÃO TIPOGRÁFICA (FontManager)
# ==============================================================================

def test_font_manager_initial_fonts_and_default():
    """Valida o catálogo inicial de fontes e a fonte padrão Montserrat."""
    assert DEFAULT_FONT_FAMILY == "Montserrat"

    initial = FontManager.get_initial_fonts()
    assert "Montserrat" in initial
    assert "AppSans" in initial
    assert "HymnSerif" in initial
    assert "OpenDyslexic" in initial
    assert "Roboto" in initial
    assert "Inter" in initial
    assert "Times New Roman" in initial


def test_font_manager_register_fonts():
    """Valida o registro seguro de fontes em ft.Page."""
    mock_page = MagicMock(spec=ft.Page)
    mock_page.fonts = {"Custom": "fonts/custom.ttf"}

    FontManager.register_fonts(mock_page)

    assert "Montserrat" in mock_page.fonts
    assert "Custom" in mock_page.fonts
    assert "OpenDyslexic" in mock_page.fonts


def test_font_manager_register_downloaded_fonts(tmp_path: Path):
    """Valida o carregamento dinâmico de fontes baixadas na Central de Downloads."""
    mock_page = MagicMock(spec=ft.Page)
    mock_page.fonts = {}

    # Cria arquivos simulados de fontes no diretório temporário
    font_a = tmp_path / "LexendDeca.ttf"
    font_a.write_text("dummy ttf content")

    font_b = tmp_path / "Lora-Regular.otf"
    font_b.write_text("dummy otf content")

    non_font = tmp_path / "metadata.json"
    non_font.write_text("{}")

    registered = FontManager.register_downloaded_fonts(mock_page, tmp_path)

    assert "LexendDeca" in registered
    assert "Lora-Regular" in registered
    assert "metadata" not in registered
    assert len(registered) == 2

    assert "LexendDeca" in mock_page.fonts
    assert str(font_a.resolve()) == mock_page.fonts["LexendDeca"]
    assert "Lora-Regular" in mock_page.fonts

    # Teste com diretório inexistente
    inexistent = tmp_path / "non_existent_folder"
    assert FontManager.register_downloaded_fonts(mock_page, inexistent) == []

    # Teste com page None
    assert FontManager.register_downloaded_fonts(None, tmp_path) == []


# ==============================================================================
# 3. TESTES DE DETECÇÃO DE HINOS INFANTIS (508 A 557)
# ==============================================================================

def test_kids_hymns_detection():
    """Valida a identificação exata do intervalo de Hinos Infantis (508 a 557)."""
    # Limites exatos
    assert is_kids_hymn(KIDS_HYMNS_START) is True
    assert is_kids_hymn(KIDS_HYMNS_END) is True
    assert is_kids_hymn(508) is True
    assert is_kids_hymn(557) is True

    # Interior do intervalo
    assert is_kids_hymn(509) is True
    assert is_kids_hymn(530) is True
    assert is_kids_hymn(556) is True

    # Fora do intervalo
    assert is_kids_hymn(507) is False
    assert is_kids_hymn(558) is False
    assert is_kids_hymn(1) is False
    assert is_kids_hymn(100) is False
    assert is_kids_hymn(600) is False

    # Entradas em string e variantes (ex: 508A, 508_A, 510.1)
    assert is_kids_hymn("508") is True
    assert is_kids_hymn("557") is True
    assert is_kids_hymn("508A") is True
    assert is_kids_hymn("508_A") is True
    assert is_kids_hymn("510.1") is True
    assert is_kids_hymn(" 525 ") is True

    # Entradas inválidas
    assert is_kids_hymn(None) is False
    assert is_kids_hymn("") is False
    assert is_kids_hymn("hino_abc") is False
    assert is_kids_hymn("ABC") is False


def test_kids_badge_component():
    """Valida a construção e estilização do badge solar de Hinos Infantis."""
    badge = build_kids_badge()
    assert isinstance(badge, ft.Container)
    assert badge.bgcolor == "#FFE58F"
    assert badge.border_radius == 20
    assert isinstance(badge.content, ft.Row)

    row = badge.content
    assert len(row.controls) == 3
    # Ícone solar
    assert isinstance(row.controls[0], ft.Icon)
    assert row.controls[0].icon == ft.Icons.WB_SUNNY_ROUNDED
    # Texto
    assert isinstance(row.controls[1], ft.Text)
    assert row.controls[1].value == "Hino Infantil"
    assert row.controls[1].color == "#6E3300"
    # Ícone estrela
    assert isinstance(row.controls[2], ft.Icon)
    assert row.controls[2].icon == ft.Icons.STAR_ROUNDED


# ==============================================================================
# 4. TESTES DE RENDERIZAÇÃO DE ESTROFES POR TEMA
# ==============================================================================

def test_kids_verse_card_rendering_material_you():
    """Valida a renderização de cards pílula para hinos infantis em Material You."""
    engine = ThemeEngine()
    engine.theme_style = ThemeModeType.MATERIAL_YOU
    engine.is_dark = False

    # Estrofe 1 (ímpar)
    card_odd = build_verse_card("Primeira estrofe infantil", 1, 508, engine)
    assert isinstance(card_odd, ft.Container)
    assert card_odd.border_radius == 32
    assert card_odd.bgcolor == ft.Colors.TERTIARY_CONTAINER
    assert isinstance(card_odd.content, ft.Column)
    assert card_odd.content.controls[0].value == "Estrofe 1"

    # Estrofe 2 (par)
    card_even = build_verse_card("Segunda estrofe infantil", 2, 508, engine)
    assert card_even.border_radius == 32
    assert card_even.bgcolor == ft.Colors.SECONDARY_CONTAINER

    # Coro
    card_coro = build_verse_card("Coro:\nGlória a Jesus!", 3, 508, engine)
    assert card_coro.content.controls[0].value == "Coro ☀️"


def test_kids_verse_card_rendering_liquid_glass():
    """Valida a renderização translúcida de cards para hinos infantis em Liquid Glass."""
    engine = ThemeEngine()
    engine.theme_style = ThemeModeType.LIQUID_GLASS
    engine.is_dark = False

    card = build_verse_card("Estrofe glass", 1, 508, engine)
    assert isinstance(card, ft.Container)
    assert card.border_radius == 32
    assert card.border is not None
    assert card.border.top.width == 1.0


def test_kids_verse_card_rendering_classic_book():
    """Valida a renderização clássica editorial de cards para hinos infantis em Classic Book."""
    engine = ThemeEngine()
    engine.theme_style = ThemeModeType.CLASSIC_BOOK
    engine.is_dark = False

    card = build_verse_card("Estrofe clássica", 1, 508, engine)
    assert isinstance(card, ft.Container)
    assert card.border_radius == 32
    assert card.border is not None
    assert card.border.top.width == 1.5
    assert card.bgcolor == "#FFF8EB"


def test_regular_hymn_editorial_rendering():
    """Garante que hinos não-infantis mantêm layout editorial limpo sem molduras pílula."""
    engine = ThemeEngine()
    engine.theme_style = ThemeModeType.MATERIAL_YOU

    # Hino 1 (não-infantil)
    card_normal = build_verse_card("Santo, Santo, Santo!\nDeus Onipotente!", 1, 1, engine)
    assert isinstance(card_normal, ft.Container)
    assert card_normal.border_radius is None
    assert isinstance(card_normal.content, ft.Text)
    assert card_normal.content.value.startswith("Santo, Santo, Santo!")


# ==============================================================================
# 5. TESTES DE INTEGRAÇÃO COM HinoView (KIDS VS REGULAR)
# ==============================================================================

@pytest.mark.asyncio
async def test_hino_view_kids_vs_normal_integration(in_memory_db):
    """
    Testa HinoView garantindo que:
    - Hinos Infantis (508) exibem o badge solar e cartões estilizados.
    - Hinos Regulares (1) exibem layout editorial sem badge infantil.
    """
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    # Insere hino infantil 508 no banco de teste
    conn = await in_memory_db.get_connection()
    await conn.execute(
        """
        INSERT INTO hino (id, numero, titulo, letra, categoria, subcategoria)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            508,
            "508",
            "Jesus e as Crianças",
            "Deixai vir a mim as criancinhas\nPorque delas é o reino dos céus.\n\nCoro:\nVinde já, vinde já!",
            "Infantil",
            "Louvor",
        ),
    )
    await conn.commit()

    engine = ThemeEngine()
    mock_page = MagicMock(spec=ft.Page)
    mock_page.width = 400

    # 1. Visualização de Hino Infantil (508)
    view_kids_obj = HinoView(508, hino_repo, fav_repo, hist_repo, theme_engine=engine)
    view_kids = await view_kids_obj.build(mock_page)
    assert isinstance(view_kids, ft.View)
    assert view_kids_obj.letra_text is not None

    # O container da letra deve conter o badge e os cards
    letra_controls = view_kids_obj.letra_text.content.controls
    # Primeiro elemento deve ser o badge solar
    assert isinstance(letra_controls[0], ft.Container)
    assert letra_controls[0].bgcolor == "#FFE58F"
    # Estrofes devem ser cartões com border_radius = 32
    assert isinstance(letra_controls[1], ft.Container)
    assert letra_controls[1].border_radius == 32

    # 2. Visualização de Hino Regular (1)
    view_norm_obj = HinoView(1, hino_repo, fav_repo, hist_repo, theme_engine=engine)
    view_norm = await view_norm_obj.build(mock_page)
    assert isinstance(view_norm, ft.View)
    assert view_norm_obj.letra_text is not None

    letra_norm_controls = view_norm_obj.letra_text.content.controls
    # Hino regular não deve possuir o badge amarelo pastel no topo
    assert not any(
        isinstance(ctrl, ft.Container) and getattr(ctrl, "bgcolor", None) == "#FFE58F"
        for ctrl in letra_norm_controls
    )


# ==============================================================================
# 6. TESTES DE PERSISTÊNCIA (Client Storage & SQLite Fallback)
# ==============================================================================

@pytest.mark.asyncio
async def test_theme_persistence_client_storage():
    """Valida o salvamento e carregamento de preferências usando page.client_storage."""
    engine = ThemeEngine()
    storage_mock = AsyncMock()
    storage_dict = {}

    async def mock_get(key):
        return storage_dict.get(key)

    async def mock_set(key, val):
        storage_dict[key] = val

    storage_mock.get_async.side_effect = mock_get
    storage_mock.set_async.side_effect = mock_set

    mock_page = MagicMock(spec=ft.Page)
    mock_page.client_storage = storage_mock

    # Salva preferências
    await engine.save_preferences(
        page=mock_page,
        theme_style=ThemeModeType.LIQUID_GLASS,
        theme_mode="dark",
        is_amoled=True,
        seed="emerald",
        font_family="OpenDyslexic",
    )

    assert storage_dict[STORAGE_KEY_THEME_STYLE] == "liquid_glass"
    assert storage_dict[STORAGE_KEY_THEME_MODE] == "dark"
    assert storage_dict[STORAGE_KEY_AMOLED] is True
    assert storage_dict[STORAGE_KEY_COLOR_SEED] == "emerald"
    assert storage_dict[STORAGE_KEY_FONT_FAMILY] == "OpenDyslexic"

    # Cria nova engine e carrega do storage
    new_engine = ThemeEngine()
    await new_engine.load_preferences(mock_page)

    assert new_engine.theme_style == ThemeModeType.LIQUID_GLASS
    assert new_engine.theme_mode == "dark"
    assert new_engine.is_dark is True
    assert new_engine.is_amoled is True
    assert new_engine.current_seed == "emerald"
    assert new_engine.font_family == "OpenDyslexic"


@pytest.mark.asyncio
async def test_theme_persistence_sqlite_fallback(in_memory_db):
    """Valida o fallback para tabela SQLite preferencias quando client_storage não está disponível."""
    engine = ThemeEngine(in_memory_db)

    await engine.save_preferences(
        page=None,
        theme_style=ThemeModeType.CLASSIC_BOOK,
        theme_mode="light",
        is_amoled=False,
        seed="gold",
        font_family="Roboto",
    )

    assert engine.theme_style == ThemeModeType.CLASSIC_BOOK
    assert engine.theme_mode == "light"
    assert engine.is_amoled is False
    assert engine.current_seed == "gold"
    assert engine.font_family == "Roboto"

    # Nova instância com o mesmo banco
    reloaded_engine = ThemeEngine(in_memory_db)
    await reloaded_engine.load_preferences(page=None)

    assert reloaded_engine.theme_style == ThemeModeType.CLASSIC_BOOK
    assert reloaded_engine.theme_mode == "light"
    assert reloaded_engine.is_dark is False
    assert reloaded_engine.is_amoled is False
    assert reloaded_engine.current_seed == "gold"
    assert reloaded_engine.font_family == "Roboto"


# ==============================================================================
# 7. TESTES DE APLICAÇÃO DE TEMAS NO ft.Page
# ==============================================================================

def test_theme_engine_apply_theme_material_you():
    """Valida a aplicação do tema Material You."""
    engine = ThemeEngine()
    engine.theme_style = ThemeModeType.MATERIAL_YOU
    engine.theme_mode = "system"
    engine.is_amoled = False

    mock_page = MagicMock(spec=ft.Page)
    engine.apply_theme(mock_page)

    assert mock_page.theme_mode == ft.ThemeMode.SYSTEM
    assert mock_page.theme is not None
    assert mock_page.theme.use_material3 is True
    assert mock_page.theme.color_scheme_seed == "#6750A4"
    assert "Montserrat" in mock_page.fonts


def test_theme_engine_apply_theme_liquid_glass():
    """Valida a aplicação do tema Liquid Glass no ft.Page."""
    engine = ThemeEngine()
    engine.theme_style = ThemeModeType.LIQUID_GLASS
    engine.theme_mode = "dark"
    engine.is_amoled = False

    mock_page = MagicMock(spec=ft.Page)
    engine.apply_theme(mock_page)

    assert mock_page.theme_mode == ft.ThemeMode.DARK
    assert mock_page.bgcolor == PALETTE_LIQUID_GLASS_DARK.background
    assert mock_page.dark_theme is not None
    assert mock_page.dark_theme.use_material3 is True


def test_theme_engine_apply_theme_classic_book():
    """Valida a aplicação do tema Classic Book no ft.Page."""
    engine = ThemeEngine()
    engine.theme_style = ThemeModeType.CLASSIC_BOOK
    engine.theme_mode = "light"
    engine.is_amoled = False

    mock_page = MagicMock(spec=ft.Page)
    engine.apply_theme(mock_page)

    assert mock_page.theme_mode == ft.ThemeMode.LIGHT
    assert mock_page.bgcolor == "#F9F6F0"
    assert mock_page.theme is not None
    assert mock_page.theme.use_material3 is True


def test_theme_engine_apply_theme_amoled():
    """Valida a aplicação de preto absoluto (#000000) em modo AMOLED."""
    engine = ThemeEngine()
    engine.is_amoled = True

    mock_page = MagicMock(spec=ft.Page)
    engine.apply_theme(mock_page)

    assert mock_page.theme_mode == ft.ThemeMode.DARK
    assert mock_page.bgcolor == "#000000"
    assert mock_page.dark_theme.color_scheme.surface == "#000000"


@pytest.mark.asyncio
async def test_theme_engine_toggle_and_setters():
    """Valida métodos utilitários de alternância e atualização de tema."""
    engine = ThemeEngine()
    mock_page = MagicMock(spec=ft.Page)

    await engine.toggle_amoled(mock_page, True)
    assert engine.is_amoled is True
    mock_page.update.assert_called_once()

    mock_page.reset_mock()
    await engine.set_theme_style(ThemeModeType.LIQUID_GLASS, page=mock_page)
    assert engine.theme_style == ThemeModeType.LIQUID_GLASS
    mock_page.update.assert_called_once()

    mock_page.reset_mock()
    await engine.set_theme_mode("dark", page=mock_page)
    assert engine.theme_mode == "dark"
    assert engine.is_dark is True
    mock_page.update.assert_called_once()

    mock_page.reset_mock()
    await engine.set_color_seed("emerald", page=mock_page)
    assert engine.current_seed == "emerald"
    mock_page.update.assert_called_once()

    mock_page.reset_mock()
    await engine.set_font_family("OpenDyslexic", page=mock_page)
    assert engine.font_family == "OpenDyslexic"
    mock_page.update.assert_called_once()

    # Toggle de performance / blur do Liquid Glass
    mock_page.reset_mock()
    await engine.set_glass_blur_enabled(False, page=mock_page)
    assert engine.glass_blur_enabled is False
    mock_page.update.assert_called_once()


def test_glass_styles_utilities():
    """Valida os utilitários de geração de gradientes e propriedades de cartão vítreo."""
    # Gradientes de fundo ambiente
    grad_light = get_liquid_glass_background_gradient(is_dark=False)
    assert isinstance(grad_light, ft.LinearGradient)
    assert len(grad_light.colors) >= 3

    grad_dark = get_liquid_glass_background_gradient(is_dark=True)
    assert isinstance(grad_dark, ft.LinearGradient)
    assert len(grad_dark.colors) >= 3

    # Propriedades de cartão com blur e sombra ativados
    props_full = get_glass_card_props(is_dark=False, blur_enabled=True, shadow_enabled=True)
    assert props_full["blur"] is not None
    assert props_full["shadow"] is not None
    assert props_full["gradient"] is not None
    assert props_full["border"] is not None
    assert props_full["border_radius"] == 20

    # Modo desempenho (blur desativado)
    props_perf = get_glass_card_props(is_dark=False, blur_enabled=False, shadow_enabled=True)
    assert props_perf["blur"] is None
    assert props_perf["shadow"] is not None

    # Decorações de cartão conforme o tema ativo
    engine = ThemeEngine()
    engine.theme_style = ThemeModeType.LIQUID_GLASS
    dec_glass = get_card_decoration(engine)
    assert dec_glass["gradient"] is not None
    assert dec_glass["border"] is not None

    engine.theme_style = ThemeModeType.CLASSIC_BOOK
    dec_classic = get_card_decoration(engine)
    assert dec_classic["gradient"] is None
    assert dec_classic["bgcolor"] is not None
    assert dec_classic["border"] is not None

    engine.theme_style = ThemeModeType.MATERIAL_YOU
    dec_m3 = get_card_decoration(engine)
    assert dec_m3["gradient"] is None
    assert dec_m3["bgcolor"] == ft.Colors.SURFACE_CONTAINER_HIGH


@pytest.mark.asyncio
async def test_glass_blur_persistence_client_storage_and_sqlite(in_memory_db):
    """Valida a persistência do switch de desfoque (performance) em client_storage e SQLite."""
    engine = ThemeEngine(in_memory_db)
    storage_mock = AsyncMock()
    storage_dict = {}

    async def mock_get(key):
        return storage_dict.get(key)

    async def mock_set(key, val):
        storage_dict[key] = val

    storage_mock.get_async.side_effect = mock_get
    storage_mock.set_async.side_effect = mock_set

    mock_page = MagicMock(spec=ft.Page)
    mock_page.client_storage = storage_mock

    # Salva com blur desativado
    await engine.set_glass_blur_enabled(False, page=mock_page)
    assert engine.glass_blur_enabled is False
    assert storage_dict[STORAGE_KEY_GLASS_BLUR] is False

    # Carrega em nova engine a partir do client_storage
    new_engine = ThemeEngine(in_memory_db)
    await new_engine.load_preferences(mock_page)
    assert new_engine.glass_blur_enabled is False

    # Fallback SQLite sem client_storage
    new_engine_sql = ThemeEngine(in_memory_db)
    await new_engine_sql.load_preferences(page=None)
    assert new_engine_sql.glass_blur_enabled is False
