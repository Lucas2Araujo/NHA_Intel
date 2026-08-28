import os
import shutil
import asyncio
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional
import flet as ft

# Registrar plugins do Flet 0.23+ globalmente na raiz
try:
    import flet_video
except ImportError:
    pass

from src.database.connection import DatabaseConnection
from src.repositories.hino_repository import HinoRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.repositories.culto_repository import CultoRepository
from src.repositories.biblia_repository import BibliaRepository
from src.repositories.comparativo_repository import ComparativoRepository
from src.services.media_service import MediaService
from src.services.agente_service import AgenteService
from src.services.updater_service import UpdaterService
from src.services.theme_service import ThemeService
from src.views.home_view import HomeView
from src.views.hino_view import HinoView
from src.views.agente_view import AgenteView
from src.views.download_manager_view import DownloadManagerView
from src.views.update_dialog import show_update_dialog

try:
    from src.version import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = "0.5.0"

ROUTE_AGENTE = "/agente"
ROUTE_DOWNLOADS = "/downloads"

_background_tasks: set[asyncio.Task] = set()


async def _get_hino_ids(hino_repository: HinoRepository, hino_ids_ordered: List[int]) -> List[int]:
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


def _setup_assets_and_theme(page: ft.Page, theme_service: Optional[ThemeService] = None) -> None:
    """Configura título, ícones, fontes e tema da aplicação."""
    page.title = f"Hinário Inteligente v{APP_VERSION}"

    root_dir = Path(__file__).resolve().parent
    asset_icon = root_dir / "assets" / "icon.ico"
    _set_window_icon_if_exists(page, asset_icon)

    if theme_service:
        theme_service.apply_theme(page)
    else:
        page.fonts = {
            "OpenDyslexic": "fonts/OpenDyslexic-Regular.otf",
            "Times New Roman": "Times New Roman, serif",
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


def _build_loading_view(progress_val: Optional[float] = None) -> ft.View:
    """
    Constrói a tela de loading/splash minimalista e adaptativa.
    Exibe o ícone, título e uma barra de progresso suave completando-se da esquerda para a direita.
    """
    return ft.View(
        route="/loading",
        bgcolor=ft.Colors.SURFACE,
        controls=[
            ft.SafeArea(
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                content=ft.Icon(
                                    ft.Icons.LIBRARY_MUSIC,
                                    size=48,
                                    color=ft.Colors.BLUE_400,
                                ),
                                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                                border_radius=16,
                                padding=ft.Padding.all(16),
                            ),
                            ft.Text(
                                "Hinário Inteligente",
                                size=20,
                                weight=ft.FontWeight.BOLD,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(
                                content=ft.ProgressBar(
                                    value=progress_val,
                                    width=200,
                                    height=4,
                                    border_radius=2,
                                    color=ft.Colors.BLUE_400,
                                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                                ),
                                padding=ft.Padding.only(top=16),
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=12,
                    ),
                    alignment=ft.Alignment.CENTER,
                    expand=True,
                ),
                expand=True,
            ),
        ],
    )


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
    view_cache: Dict[str, ft.View],
    home_view_instance: HomeView,
    target_views: List[ft.View],
) -> None:
    """Renderiza a rota principal (Home)."""
    coming_from_hino = route_base and not route_base.startswith("/hino/")
    if "/" not in view_cache or coming_from_hino or initial_search:
        view_cache["/"] = await home_view_instance.build(
            page, initial_search=initial_search
        )
    target_views.append(view_cache["/"])


def _render_agente_route(
    page: ft.Page,
    view_cache: Dict[str, ft.View],
    agente_view_instance: AgenteView,
    target_views: List[ft.View],
) -> None:
    """Renderiza a rota do Agente Organizador (/agente)."""
    if page.route == ROUTE_AGENTE:
        if ROUTE_AGENTE not in view_cache:
            view_cache[ROUTE_AGENTE] = agente_view_instance.build(page)
        target_views.append(view_cache[ROUTE_AGENTE])


def _render_downloads_route(
    page: ft.Page,
    view_cache: Dict[str, ft.View],
    download_manager_instance: DownloadManagerView,
    target_views: List[ft.View],
) -> None:
    """Renderiza a rota do Gerenciador de Downloads (/downloads)."""
    if page.route == ROUTE_DOWNLOADS:
        if ROUTE_DOWNLOADS not in view_cache:
            view_cache[ROUTE_DOWNLOADS] = download_manager_instance.build(page)
        target_views.append(view_cache[ROUTE_DOWNLOADS])


async def _render_hino_route(
    page: ft.Page,
    hino_repository: HinoRepository,
    favorito_repository: FavoritoRepository,
    historico_repository: HistoricoRepository,
    media_service: MediaService,
    biblia_repository: BibliaRepository,
    hino_ids_ordered: List[int],
    target_views: List[ft.View],
    comparativo_repository: Optional[ComparativoRepository] = None,
    antigo_repository: Optional[HinoRepository] = None,
) -> None:
    """Renderiza a rota detalhada do hino (/hino/{id})."""
    if not (page.route and page.route.startswith("/hino/")):
        return
    try:
        hino_id = int(page.route.split("/")[-1])

        await _get_hino_ids(hino_repository, hino_ids_ordered)

        hino_view_instance = HinoView(
            hino_id,
            hino_repository,
            favorito_repository,
            historico_repository,
            media_service,
            hino_ids_list=hino_ids_ordered,
            biblia_repository=biblia_repository,
            comparativo_repository=comparativo_repository,
            antigo_repository=antigo_repository,
        )
        built_view = await hino_view_instance.build(page)
        target_views.append(built_view)
    except ValueError:
        pass


async def _check_updates_background(page: ft.Page, updater_service: UpdaterService):
    """Verifica atualizações em segundo plano sem bloquear a inicialização do app."""
    try:
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
    Ponto de entrada assíncrono do aplicativo Hinário Inteligente em Flet (0.85+).
    Exibe imediatamente a tela de loading/splash adaptativa, inicializa as conexões
    aiosqlite, restaura preferências (incluindo AMOLED) e carrega as views com fluidez.
    """
    db_connection = DatabaseConnection(db_path="hinario.db")
    biblia_connection = DatabaseConnection(db_path="ARA.sqlite", read_only=True)
    comparativo_connection = DatabaseConnection(db_path="hinario_comparativo.db", read_only=True)
    antigo_connection = DatabaseConnection(db_path="hinario_antigo.db", read_only=True)

    theme_service = ThemeService(db_connection)
    _setup_assets_and_theme(page, theme_service)

    # 1. Renderiza IMEDIATAMENTE a tela de loading minimalista (elimina tela branca em ARMv7)
    page.views.clear()
    page.views.append(_build_loading_view())
    page.update()

    # 2. Carrega preferências de tema (ex: Modo AMOLED) e aplica na página
    await theme_service.load_preferences()
    theme_service.apply_theme(page)

    hino_repository = HinoRepository(db_connection)
    favorito_repository = FavoritoRepository(db_connection)
    historico_repository = HistoricoRepository(db_connection)
    culto_repository = CultoRepository(db_connection)
    biblia_repository = BibliaRepository(biblia_connection)
    comparativo_repository = ComparativoRepository(comparativo_connection)
    antigo_repository = HinoRepository(antigo_connection)

    media_service = MediaService(download_dir="downloads")
    agente_service = AgenteService(hino_repository)
    updater_service = UpdaterService()

    view_cache: Dict[str, ft.View] = {}

    home_view_instance = HomeView(
        hino_repository,
        favorito_repository,
        historico_repository,
        updater_service=updater_service,
        theme_service=theme_service,
    )
    agente_view_instance = AgenteView(agente_service, culto_repository)
    download_manager_instance = DownloadManagerView(hino_repository, media_service)
    hino_ids_ordered: List[int] = []

    async def route_change(e=None):
        route = page.route or "/"
        route_base, initial_search = _parse_route_query(route)
        if "?" in route:
            page.route = route_base

        new_views: List[ft.View] = []

        await _render_home_route(
            page, route_base, initial_search, view_cache, home_view_instance, new_views
        )
        _render_agente_route(page, view_cache, agente_view_instance, new_views)
        _render_downloads_route(page, view_cache, download_manager_instance, new_views)
        await _render_hino_route(
            page,
            hino_repository,
            favorito_repository,
            historico_repository,
            media_service,
            biblia_repository,
            hino_ids_ordered,
            new_views,
            comparativo_repository=comparativo_repository,
            antigo_repository=antigo_repository,
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

    async def run_background_task(handler, *args, **kwargs):
        return await asyncio.wrap_future(page.run_task(handler, *args, **kwargs))

    setattr(page, "run_background_task", run_background_task)
    page.on_route_change = route_change
    page.on_view_pop = view_pop

    if not page.route or page.route == "/loading":
        page.route = "/"

    # 3. Transiciona suavemente para a rota inicial (HomeView)
    await route_change(None)

    # 4. Dispara a verificação assíncrona de atualizações em segundo plano
    update_task = asyncio.create_task(_check_updates_background(page, updater_service))
    _background_tasks.add(update_task)
    update_task.add_done_callback(_background_tasks.discard)


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")

