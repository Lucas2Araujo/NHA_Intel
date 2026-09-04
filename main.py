import asyncio
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import flet as ft

# Registrar plugins do Flet 0.23+ globalmente na raiz
try:
    import flet_video
except ImportError:
    pass

from src.database.connection import DatabaseConnection
from src.repositories.biblia_repository import BibliaRepository
from src.repositories.comparativo_repository import ComparativoRepository
from src.repositories.culto_repository import CultoRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.hino_repository import HinoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.services.agente_service import AgenteService
from src.services.media_service import MediaService
from src.services.theme_service import EDITION_ANTIGO, EDITION_NOVO, ThemeService
from src.services.updater_service import UpdaterService
from src.views.agente_view import AgenteView
from src.views.biblia_view import BibliaView
from src.views.download_manager_view import DownloadManagerView
from src.views.hino_view import HinoView
from src.views.home_view import HomeView
from src.views.selecao_view import SelecaoView
from src.views.update_dialog import show_update_dialog

try:
    from src.version import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = "0.1.0"

ROUTE_SELECAO = "/"
ROUTE_NOVO = "/novo"
ROUTE_ANTIGO = "/antigo"
ROUTE_AGENTE = "/agente"
ROUTE_DOWNLOADS = "/downloads"
ROUTE_BIBLIA = "/biblia"

_background_tasks: set[asyncio.Task] = set()


@dataclass
class EditionContext:
    """Encapsula os repositórios e a lista em cache de IDs para uma edição do hinário."""

    hino_repo: HinoRepository
    fav_repo: FavoritoRepository
    hist_repo: HistoricoRepository
    hino_ids: list[int] = field(default_factory=list)


async def _get_hino_ids(
    hino_repository: HinoRepository, hino_ids_ordered: list[int]
) -> list[int]:
    """Carrega a lista ordenada de IDs de hinos (uma vez, lazy)."""
    if not hino_ids_ordered:
        all_hinos = await hino_repository.get_all()
        hino_ids_ordered.extend([h.id for h in all_hinos if h.id is not None])
    return hino_ids_ordered


def _set_window_icon_if_exists(page: ft.Page, asset_icon: Path) -> None:
    """Define o ícone da janela se o arquivo existir."""
    if asset_icon.exists():
        try:
            page.window.icon = str(asset_icon)
        except Exception:
            pass


def _setup_assets_and_theme(
    page: ft.Page, theme_service: ThemeService | None = None
) -> None:
    """Configura título, ícones, fontes e tema da aplicação."""
    is_web = getattr(page, "web", False)
    suffix = " (Web)" if is_web else ""
    page.title = f"Hinário Inteligente v{APP_VERSION}{suffix}"

    root_dir = Path(__file__).resolve().parent
    asset_icon = root_dir / "assets" / "icon.ico"
    _set_window_icon_if_exists(page, asset_icon)

    if theme_service:
        theme_service.apply_theme(page)
    else:
        page.fonts = {
            "OpenDyslexic": "fonts/OpenDyslexic-Regular.otf",
            "Times New Roman": "Times New Roman, serif",
            "Helvetica": "fonts/Helvetica-World-Regular.ttf",
            "Montserrat": "fonts/Montserrat-Regular.ttf",
        }
        page.theme_mode = ft.ThemeMode.SYSTEM
        page.theme = ft.Theme(
            page_transitions=ft.PageTransitionsTheme(
                android=ft.PageTransitionTheme.CUPERTINO,
                ios=ft.PageTransitionTheme.CUPERTINO,
                linux=ft.PageTransitionTheme.CUPERTINO,
                macos=ft.PageTransitionTheme.CUPERTINO,
                windows=ft.PageTransitionTheme.CUPERTINO,
            )
        )


def _build_loading_view(progress_val: float | None = None) -> ft.View:
    """
    Constrói a tela splash com fundo preto absoluto e o ícone centralizado do app.
    """
    return ft.View(
        route="/loading",
        bgcolor=ft.Colors.BLACK,
        padding=0,
        controls=[
            ft.SafeArea(
                maintain_bottom_view_padding=True,
                content=ft.Container(
                    content=ft.Image(
                        src="/icon.png",
                        width=128,
                        height=128,
                        fit=ft.BoxFit.CONTAIN,
                    ),
                    alignment=ft.Alignment.CENTER,
                    expand=True,
                ),
                expand=True,
            ),
        ],
    )


_build_splash_view = _build_loading_view



def _parse_route_query(route: str) -> tuple[str, str]:
    """Extrai a rota base e o parâmetro de busca (?q=) da URL."""
    if "?" not in route:
        return route, ""
    parts = route.split("?", 1)
    route_base = parts[0] or "/"
    query_str = parts[1]
    initial_search = ""
    for param in query_str.split("&"):
        if param.startswith("q="):
            initial_search = urllib.parse.unquote(param[2:])
    return route_base, initial_search


async def _render_home_route(
    page: ft.Page,
    route_base: str,
    initial_search: str,
    view_cache: dict[str, ft.View],
    home_novo_instance: HomeView,
    home_antigo_instance: HomeView,
    target_views: list[ft.View],
) -> None:
    """Renderiza a HomeView do Hinário Novo (/novo) ou Hinário Antigo (/antigo)."""
    if route_base == ROUTE_NOVO:
        view_cache[ROUTE_NOVO] = await home_novo_instance.build(
            page, initial_search=initial_search
        )
        target_views.append(view_cache[ROUTE_NOVO])
    elif route_base == ROUTE_ANTIGO:
        view_cache[ROUTE_ANTIGO] = await home_antigo_instance.build(
            page, initial_search=initial_search
        )
        target_views.append(view_cache[ROUTE_ANTIGO])


def _render_agente_route(
    page: ft.Page,
    view_cache: dict[str, ft.View],
    agente_view_instance: AgenteView,
    target_views: list[ft.View],
) -> None:
    """Renderiza a rota do Agente Organizador (/agente)."""
    if page.route == ROUTE_AGENTE:
        if ROUTE_AGENTE not in view_cache:
            view_cache[ROUTE_AGENTE] = agente_view_instance.build(page)
        target_views.append(view_cache[ROUTE_AGENTE])


def _render_downloads_route(
    page: ft.Page,
    view_cache: dict[str, ft.View],
    download_manager_instance: DownloadManagerView,
    target_views: list[ft.View],
) -> None:
    """Renderiza a rota do Gerenciador de Downloads (/downloads)."""
    if page.route == ROUTE_DOWNLOADS:
        if ROUTE_DOWNLOADS not in view_cache:
            view_cache[ROUTE_DOWNLOADS] = download_manager_instance.build(page)
        target_views.append(view_cache[ROUTE_DOWNLOADS])


async def _render_hino_route(
    page: ft.Page,
    route_base: str,
    ctx_novo: EditionContext,
    ctx_antigo: EditionContext,
    media_service: MediaService,
    biblia_repository: BibliaRepository,
    target_views: list[ft.View],
    comparativo_repository: ComparativoRepository | None = None,
    theme_service: ThemeService | None = None,
) -> None:
    """Renderiza a rota detalhada do hino (/novo/hino/{id}, /antigo/hino/{id} ou /hino/{id})."""
    if not route_base.startswith(("/antigo/hino/", "/novo/hino/", "/hino/")):
        return

    is_antigo = route_base.startswith("/antigo/hino/")
    active_ctx = ctx_antigo if is_antigo else ctx_novo
    edition = EDITION_ANTIGO if is_antigo else EDITION_NOVO

    try:
        hino_id = int(route_base.split("/")[-1])
        await _get_hino_ids(active_ctx.hino_repo, active_ctx.hino_ids)
        hino_view_instance = HinoView(
            hino_id,
            active_ctx.hino_repo,
            active_ctx.fav_repo,
            active_ctx.hist_repo,
            media_service,
            hino_ids_list=active_ctx.hino_ids,
            biblia_repository=biblia_repository,
            comparativo_repository=comparativo_repository,
            antigo_repository=ctx_antigo.hino_repo,
            novo_repository=ctx_novo.hino_repo,
            edition=edition,
            theme_service=theme_service,
        )
        built_view = await hino_view_instance.build(page)
        target_views.append(built_view)
    except ValueError:
        pass


async def _check_updates_background(page: ft.Page, updater_service: UpdaterService):
    """Verifica atualizações em segundo plano sem bloquear a inicialização do app."""
    try:
        if getattr(page, "web", False):
            return
        # Aguarda a renderização inicial da UI
        await asyncio.sleep(1.5)
        update_info = await updater_service.check_for_updates()
        if update_info.get("update_available") and (
            update_info.get("download_url") or update_info.get("html_url")
        ):
            show_update_dialog(page, update_info, updater_service)
    except Exception:
        pass


async def main(page: ft.Page):
    """
    Ponto de entrada assíncrono do aplicativo Hinário Inteligente em Flet.
    Inicializa conexões SQLite (Hinário Novo, Hinário Antigo, Bíblia e Comparativo),
    restaura preferências e gerencia rotas dinâmicas com suporte a ambos os hinários.
    """
    db_connection = DatabaseConnection(db_path="hinario.db")
    antigo_connection = DatabaseConnection(db_path="hinario_antigo.db")
    biblia_connection = DatabaseConnection(db_path="ARA.sqlite", read_only=True)
    comparativo_connection = DatabaseConnection(
        db_path="hinario_comparativo.db", read_only=True
    )

    theme_service = ThemeService(db_connection)
    _setup_assets_and_theme(page, theme_service)

    # 1. Renderiza IMEDIATAMENTE a tela de loading minimalista
    page.views.clear()
    page.views.append(_build_loading_view())
    page.update()

    # 2. Carrega preferências de tema (ex: Modo AMOLED) e aplica na página
    await theme_service.load_preferences()
    theme_service.apply_theme(page)

    # Repositórios Hinário Novo
    hino_repository = HinoRepository(db_connection)
    favorito_repository = FavoritoRepository(db_connection)
    historico_repository = HistoricoRepository(db_connection)
    culto_repository = CultoRepository(db_connection)

    # Repositórios Hinário Antigo
    antigo_hino_repo = HinoRepository(antigo_connection)
    antigo_fav_repo = FavoritoRepository(antigo_connection)
    antigo_hist_repo = HistoricoRepository(antigo_connection)

    # Contextos estruturados por Edição
    ctx_novo = EditionContext(
        hino_repo=hino_repository,
        fav_repo=favorito_repository,
        hist_repo=historico_repository,
    )
    ctx_antigo = EditionContext(
        hino_repo=antigo_hino_repo,
        fav_repo=antigo_fav_repo,
        hist_repo=antigo_hist_repo,
    )

    # Bíblia & Comparativo
    biblia_repository = BibliaRepository(biblia_connection)
    comparativo_repository = ComparativoRepository(comparativo_connection)

    media_service = MediaService(download_dir="downloads")
    agente_service = AgenteService(hino_repository)
    updater_service = UpdaterService()

    view_cache: dict[str, ft.View] = {}

    selecao_view_instance = SelecaoView(
        theme_service=theme_service, updater_service=updater_service
    )
    home_novo_instance = HomeView(
        hino_repository,
        favorito_repository,
        historico_repository,
        updater_service=updater_service,
        theme_service=theme_service,
        edition=EDITION_NOVO,
    )
    home_antigo_instance = HomeView(
        antigo_hino_repo,
        antigo_fav_repo,
        antigo_hist_repo,
        updater_service=updater_service,
        theme_service=theme_service,
        edition=EDITION_ANTIGO,
    )
    agente_view_instance = AgenteView(agente_service, culto_repository)
    download_manager_instance = DownloadManagerView(hino_repository, media_service)
    biblia_view_instance = BibliaView(
        biblia_repository, theme_service=theme_service
    )

    async def route_change(e=None):
        route = page.route or "/"
        route_base, initial_search = _parse_route_query(route)
        if "?" in route:
            page.route = route_base

        new_views: list[ft.View] = []

        # Sempre inclui a tela de seleção como base do stack
        new_views.append(selecao_view_instance.build(page))

        # Renderiza a sub-rota selecionada sobre o stack
        await _render_home_route(
            page,
            route_base,
            initial_search,
            view_cache,
            home_novo_instance,
            home_antigo_instance,
            new_views,
        )
        _render_agente_route(page, view_cache, agente_view_instance, new_views)
        _render_downloads_route(page, view_cache, download_manager_instance, new_views)

        # Rota da Bíblia Sagrada (/biblia ou /biblia/{book_id}/{chapter})
        if route_base == ROUTE_BIBLIA or route_base.startswith(f"{ROUTE_BIBLIA}/"):
            initial_book_id = 1
            initial_chapter = 1
            parts = route_base.strip("/").split("/")
            if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
                initial_book_id = int(parts[1])
                initial_chapter = int(parts[2])
            elif len(parts) >= 2 and parts[1].isdigit():
                initial_book_id = int(parts[1])
            view_cache[ROUTE_BIBLIA] = await biblia_view_instance.build(
                page, initial_book_id=initial_book_id, initial_chapter=initial_chapter
            )
            new_views.append(view_cache[ROUTE_BIBLIA])

        await _render_hino_route(
            page,
            route_base,
            ctx_novo,
            ctx_antigo,
            media_service,
            biblia_repository,
            new_views,
            comparativo_repository=comparativo_repository,
            theme_service=theme_service,
        )

        page.views.clear()
        page.views.extend(new_views)
        page.update()

    async def view_pop(e: ft.ViewPopEvent):
        if len(page.views) > 1:
            page.views.pop()
            top_view = page.views[-1]
            page.route = top_view.route
            await route_change(None)

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    if not page.route or page.route == "/loading":
        page.route = "/"

    # 3. Transiciona para a rota inicial (Seleção de Hinários)
    await route_change(None)

    # 4. Dispara a verificação assíncrona de atualizações em segundo plano
    update_task = asyncio.create_task(_check_updates_background(page, updater_service))
    _background_tasks.add(update_task)
    update_task.add_done_callback(_background_tasks.discard)


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
