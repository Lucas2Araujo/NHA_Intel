import os
import shutil
import asyncio
from pathlib import Path
from collections import OrderedDict
import flet as ft

# Registrar plugins do Flet 0.23+ globalmente na raiz
try:
    import flet_video
except ImportError:
    pass
from typing import Dict, List
from src.database.connection import DatabaseConnection
from src.repositories.hino_repository import HinoRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.repositories.culto_repository import CultoRepository
from src.services.media_service import MediaService
from src.services.agente_service import AgenteService
from src.views.home_view import HomeView
from src.views.hino_view import HinoView
from src.views.agente_view import AgenteView
from src.views.download_manager_view import DownloadManagerView
try:
    from src.version import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = "0.5.0"

# Tamanho máximo do cache LRU para views de hinos
_HINO_VIEW_CACHE_MAX = 10
ROUTE_AGENTE = "/agente"
ROUTE_DOWNLOADS = "/downloads"


async def _get_hino_ids(hino_repository: HinoRepository, hino_ids_ordered: List[int]) -> List[int]:
    """Carrega a lista ordenada de IDs de hinos (uma vez, lazy)."""
    if not hino_ids_ordered:
        all_hinos = await hino_repository.get_all()
        hino_ids_ordered.extend([h.id for h in all_hinos if h.id is not None])
    return hino_ids_ordered


def _setup_assets_and_theme(page: ft.Page) -> None:
    """Configura título, ícones, fontes e tema da aplicação."""
    page.title = f"Hinário Inteligente v{APP_VERSION}"

    root_dir = Path(__file__).resolve().parent
    assets_dir = root_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    root_icon = root_dir / "icon.ico"
    asset_icon = assets_dir / "icon.ico"
    _copy_icon_if_needed(root_icon, asset_icon)
    _set_window_icon_if_exists(page, asset_icon)

    page.fonts = {
        "OpenDyslexic": "fonts/OpenDyslexic-Regular.otf",
        "Times New Roman": "Times New Roman, serif",
    }
    page.theme_mode = ft.ThemeMode.SYSTEM


def _copy_icon_if_needed(root_icon: Path, asset_icon: Path) -> None:
    """Copia o ícone raiz para assets se não existir."""
    if root_icon.exists() and not asset_icon.exists():
        try:
            shutil.copy2(root_icon, asset_icon)
        except Exception:
            pass


def _set_window_icon_if_exists(page: ft.Page, asset_icon: Path) -> None:
    """Define o ícone da janela se o arquivo existir."""
    if asset_icon.exists():
        try:
            page.window.icon = str(asset_icon)
        except Exception:
            pass


import urllib.parse


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


def _update_hino_view_cache(
    hino_view_cache: OrderedDict[str, ft.View], route_key: str, built_view: ft.View
) -> None:
    """Mantém o cache LRU de views de hinos dentro do limite máximo."""
    hino_view_cache[route_key] = built_view
    hino_view_cache.move_to_end(route_key)
    while len(hino_view_cache) > _HINO_VIEW_CACHE_MAX:
        hino_view_cache.popitem(last=False)


async def _render_home_route(
    page: ft.Page,
    route_base: str,
    initial_search: str,
    view_cache: Dict[str, ft.View],
    home_view_instance: HomeView,
) -> None:
    """Renderiza a rota principal (Home)."""
    coming_from_hino = route_base and not route_base.startswith("/hino/")
    if "/" not in view_cache or coming_from_hino or initial_search:
        view_cache["/"] = await home_view_instance.build(
            page, initial_search=initial_search
        )
    page.views.append(view_cache["/"])


def _render_agente_route(
    page: ft.Page,
    view_cache: Dict[str, ft.View],
    agente_view_instance: AgenteView,
) -> None:
    """Renderiza a rota do Agente Organizador (/agente)."""
    if page.route == ROUTE_AGENTE:
        if ROUTE_AGENTE not in view_cache:
            view_cache[ROUTE_AGENTE] = agente_view_instance.build(page)
        page.views.append(view_cache[ROUTE_AGENTE])


def _render_downloads_route(
    page: ft.Page,
    view_cache: Dict[str, ft.View],
    download_manager_instance: DownloadManagerView,
) -> None:
    """Renderiza a rota do Gerenciador de Downloads (/downloads)."""
    if page.route == ROUTE_DOWNLOADS:
        if ROUTE_DOWNLOADS not in view_cache:
            view_cache[ROUTE_DOWNLOADS] = download_manager_instance.build(page)
        page.views.append(view_cache[ROUTE_DOWNLOADS])


async def _render_hino_route(
    page: ft.Page,
    hino_repository: HinoRepository,
    favorito_repository: FavoritoRepository,
    historico_repository: HistoricoRepository,
    media_service: MediaService,
    hino_view_cache: OrderedDict[str, ft.View],
    hino_ids_ordered: List[int],
) -> None:
    """Renderiza a rota detalhada do hino (/hino/{id})."""
    if not (page.route and page.route.startswith("/hino/")):
        return
    try:
        hino_id = int(page.route.split("/")[-1])
        route_key = f"/hino/{hino_id}"

        await _get_hino_ids(hino_repository, hino_ids_ordered)

        hino_view_instance = HinoView(
            hino_id,
            hino_repository,
            favorito_repository,
            historico_repository,
            media_service,
            hino_ids_list=hino_ids_ordered,
        )
        built_view = await hino_view_instance.build(page)
        _update_hino_view_cache(hino_view_cache, route_key, built_view)
        page.views.append(built_view)
    except ValueError:
        pass


async def main(page: ft.Page):
    """
    Ponto de entrada assíncrono do aplicativo Hinário Inteligente em Flet (0.85+).
    Inicializa a conexão aiosqlite, repositórios, serviços de mídia, Agente Organizador e roteamento.
    """
    _setup_assets_and_theme(page)

    db_connection = DatabaseConnection(db_path="hinario.db")
    hino_repository = HinoRepository(db_connection)
    favorito_repository = FavoritoRepository(db_connection)
    historico_repository = HistoricoRepository(db_connection)
    culto_repository = CultoRepository(db_connection)

    media_service = MediaService(download_dir="downloads")
    agente_service = AgenteService(hino_repository)

    view_cache: Dict[str, ft.View] = {}
    hino_view_cache: OrderedDict[str, ft.View] = OrderedDict()

    home_view_instance = HomeView(
        hino_repository, favorito_repository, historico_repository
    )
    agente_view_instance = AgenteView(agente_service, culto_repository)
    download_manager_instance = DownloadManagerView(hino_repository, media_service)
    hino_ids_ordered: List[int] = []

    async def route_change(e=None):
        page.views.clear()

        route = page.route or "/"
        route_base, initial_search = _parse_route_query(route)
        if "?" in route:
            page.route = route_base

        await _render_home_route(
            page, route_base, initial_search, view_cache, home_view_instance
        )
        _render_agente_route(page, view_cache, agente_view_instance)
        _render_downloads_route(page, view_cache, download_manager_instance)
        await _render_hino_route(
            page,
            hino_repository,
            favorito_repository,
            historico_repository,
            media_service,
            hino_view_cache,
            hino_ids_ordered,
        )

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

    if not page.route:
        page.route = "/"

    await route_change(None)


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")

