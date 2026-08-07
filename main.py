import asyncio
from collections import OrderedDict
import flet as ft
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

# Tamanho máximo do cache LRU para views de hinos
_HINO_VIEW_CACHE_MAX = 10


async def main(page: ft.Page):
    """
    Ponto de entrada assíncrono do aplicativo Hinário Inteligente em Flet (0.85+).
    Inicializa a conexão aiosqlite, repositórios, serviços de mídia, Agente Organizador e roteamento.
    """
    # Registrar fontes personalizadas (OpenDyslexic e Times New Roman)
    page.fonts = {
        "OpenDyslexic": "https://cdn.jsdelivr.net/gh/antijingoist/open-dyslexic@master/otf/OpenDyslexic-Regular.otf",
        "Times New Roman": "Times New Roman, serif",
    }

    # Modo claro/escuro automático — segue o tema do sistema operacional
    page.theme_mode = ft.ThemeMode.SYSTEM

    # Gerenciador de conexão assíncrona com SQLite (aiosqlite)
    db_connection = DatabaseConnection(db_path="hinario_normalizado.db")
    hino_repository = HinoRepository(db_connection)
    favorito_repository = FavoritoRepository(db_connection)
    historico_repository = HistoricoRepository(db_connection)
    culto_repository = CultoRepository(db_connection)

    # Serviços de Mídia, Downloads e Agente Organizador
    media_service = MediaService(download_dir="downloads")
    agente_service = AgenteService(hino_repository)

    # Dicionário de Cache de Views (View Caching)
    view_cache: Dict[str, ft.View] = {}
    # Cache LRU para views de hinos individuais (evita crescimento ilimitado)
    hino_view_cache: OrderedDict[str, ft.View] = OrderedDict()

    home_view_instance = HomeView(
        hino_repository, favorito_repository, historico_repository
    )
    agente_view_instance = AgenteView(agente_service, culto_repository)

    # Lista de IDs dos hinos em ordem para navegação anterior/próximo
    hino_ids_ordered: List[int] = []

    async def _ensure_hino_ids():
        """Carrega a lista ordenada de IDs de hinos (uma vez, lazy)."""
        nonlocal hino_ids_ordered
        if not hino_ids_ordered:
            all_hinos = await hino_repository.get_all()
            hino_ids_ordered = [h.id for h in all_hinos if h.id is not None]

    async def route_change(e=None):
        page.views.clear()

        # Rota Principal (Home) — invalida cache se vindo de /hino/* para refletir favoritos/recentes
        coming_from_hino = page.route and not page.route.startswith("/hino/")
        if "/" not in view_cache or coming_from_hino:
            view_cache["/"] = await home_view_instance.build(page)

        page.views.append(view_cache["/"])

        # Rota do Agente Organizador de Cultos (/agente)
        if page.route == "/agente":
            if "/agente" not in view_cache:
                view_cache["/agente"] = await agente_view_instance.build(page)
            page.views.append(view_cache["/agente"])

        # Rota da Tela do Hino (/hino/{id})
        if page.route and page.route.startswith("/hino/"):
            try:
                hino_id = int(page.route.split("/")[-1])
                route_key = f"/hino/{hino_id}"

                # Garantir lista de IDs para navegação prev/next
                await _ensure_hino_ids()

                # Instancia sempre uma nova HinoView para atualizar histórico, favoritos e downloads
                hino_view_instance = HinoView(
                    hino_id,
                    hino_repository,
                    favorito_repository,
                    historico_repository,
                    media_service,
                    hino_ids_list=hino_ids_ordered,
                )
                built_view = await hino_view_instance.build(page)

                # LRU: manter no máximo _HINO_VIEW_CACHE_MAX views de hinos
                hino_view_cache[route_key] = built_view
                hino_view_cache.move_to_end(route_key)
                while len(hino_view_cache) > _HINO_VIEW_CACHE_MAX:
                    hino_view_cache.popitem(last=False)

                page.views.append(built_view)
            except ValueError:
                pass

        page.update()

    async def view_pop(e: ft.ViewPopEvent):
        if len(page.views) > 1:
            page.views.pop()
            top_view = page.views[-1]
            page.route = top_view.route
            await route_change(None)

    # Utilitário para delegação de tarefas pesadas em background (ex: downloads, inteligência semântica)
    async def run_background_task(handler, *args, **kwargs):
        """Envelopa a execução de tarefas pesadas de I/O ou CPU sem bloquear a UI."""
        return await asyncio.wrap_future(page.run_task(handler, *args, **kwargs))

    setattr(page, "run_background_task", run_background_task)
    page.on_route_change = route_change
    page.on_view_pop = view_pop

    # Garante a rota inicial e dispara o roteamento assíncrono
    if not page.route:
        page.route = "/"

    await route_change(None)


if __name__ == "__main__":
    ft.run(main)
