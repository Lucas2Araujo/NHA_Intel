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
from src.services.content_manager import ContentManager
from src.services.media_service import MediaService
from src.services.theme_service import EDITION_ANTIGO, EDITION_NOVO, ThemeService
from src.services.updater_service import UpdaterService
from src.views.agente_view import AgenteView
from src.views.biblia_view import BibliaView
from src.views.download_manager_view import DownloadManagerView
from src.views.downloads_view import DownloadsView
from src.views.hino_view import HinoView
from src.views.home_view import HinosView, HomeView
from src.views.selecao_view import SelecaoView
from src.views.settings_dialog import ensure_page_dialogs
from src.views.update_dialog import show_update_dialog

try:
    from src.version import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = "0.2.2"

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
            "AppSans": "fonts/AppSans-Regular.ttf",
            "AppSans-Bold": "fonts/AppSans-SemiBold.ttf",
            "HymnSerif": "fonts/HymnSerif-Regular.ttf",
            "HymnSerif-Bold": "fonts/HymnSerif-Bold.ttf",
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



def _parse_route_query(
    route: str,
) -> tuple[str, str, str | None, str | None, int | None]:
    """Extrai a rota base e os parâmetros de query da URL."""
    if "?" not in route:
        return route, "", None, None, None
    parts = route.split("?", 1)
    route_base = parts[0] or "/"
    query_str = parts[1]
    initial_search = ""
    initial_categoria = None
    initial_tema = None
    from_hino = None
    for param in query_str.split("&"):
        if param.startswith("q="):
            initial_search = urllib.parse.unquote(param[2:])
        elif param.startswith("categoria="):
            initial_categoria = urllib.parse.unquote(param[10:])
        elif param.startswith("tema="):
            initial_tema = urllib.parse.unquote(param[5:])
        elif param.startswith("from_hino="):
            val = param[10:]
            if val.isdigit():
                from_hino = int(val)
    return route_base, initial_search, initial_categoria, initial_tema, from_hino


def _parse_bible_route_query(
    route: str,
) -> tuple[str | None, int | None, int | None, int | None]:
    """Extrai parâmetros específicos da rota bíblica (?livro=...&cap=...&ver=...&hino_id=...)."""
    if "?" not in route:
        return None, None, None, None
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(route).query)
    livro = query.get("livro", [None])[0]
    if livro:
        livro = urllib.parse.unquote(livro)
    cap = int(query.get("cap")[0]) if "cap" in query and query["cap"][0].isdigit() else None
    ver = int(query.get("ver")[0]) if "ver" in query and query["ver"][0].isdigit() else None
    hino_id = (
        int(query.get("hino_id")[0])
        if "hino_id" in query and query["hino_id"][0].isdigit()
        else None
    )
    return livro, cap, ver, hino_id



async def _render_home_route(
    page: ft.Page,
    route_base: str,
    initial_search: str,
    initial_categoria: str | None,
    initial_tema: str | None,
    origin_hino_id: int | None,
    view_cache: dict[str, ft.View],
    home_novo_instance: HomeView,
    home_antigo_instance: HomeView,
    target_views: list[ft.View],
) -> None:
    """Renderiza a HomeView do Hinário Novo (/novo) ou Hinário Antigo (/antigo)."""
    if (
        route_base == ROUTE_NOVO
        or route_base.startswith(f"{ROUTE_NOVO}/")
        or route_base.startswith("/hino/")
    ):
        view_cache[ROUTE_NOVO] = await home_novo_instance.build(
            page,
            initial_search=initial_search,
            initial_categoria=initial_categoria,
            initial_tema=initial_tema,
            origin_hino_id=origin_hino_id,
        )
        target_views.append(view_cache[ROUTE_NOVO])
    elif route_base == ROUTE_ANTIGO or route_base.startswith(f"{ROUTE_ANTIGO}/"):
        view_cache[ROUTE_ANTIGO] = await home_antigo_instance.build(
            page,
            initial_search=initial_search,
            initial_categoria=initial_categoria,
            initial_tema=initial_tema,
            origin_hino_id=origin_hino_id,
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


def _show_route_warning(page: ft.Page, message: str) -> None:
    """Exibe um aviso via SnackBar caso o usuário tente acessar um módulo não instalado."""
    sb = ft.SnackBar(
        content=ft.Text(message, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
        bgcolor=ft.Colors.AMBER_800,
        duration=3500,
        behavior=ft.SnackBarBehavior.FLOATING,
    )
    if hasattr(page, "overlay"):
        page.overlay.append(sb)
        sb.open = True
        try:
            page.update()
        except Exception:
            pass


def _render_downloads_route(
    page: ft.Page,
    view_cache: dict[str, ft.View],
    downloads_view_instance: DownloadsView,
    target_views: list[ft.View],
) -> None:
    """Renderiza a rota do Gerenciador de Downloads (/downloads)."""
    if page.route == ROUTE_DOWNLOADS:
        view_cache[ROUTE_DOWNLOADS] = downloads_view_instance.build(page)
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


class AppRouter:
    """Controlador de rotas, histórico de navegação e ciclo de vida de conexões da aplicação."""

    def __init__(
        self,
        page: ft.Page,
        connections: tuple[DatabaseConnection, ...],
        selecao_view: SelecaoView,
        home_novo: HinosView,
        home_antigo: HinosView,
        agente_view: AgenteView,
        downloads_view: DownloadsView,
        biblia_view: BibliaView,
        content_manager: ContentManager,
        media_service: MediaService,
        theme_service: ThemeService,
        ctx_novo: EditionContext,
        ctx_antigo: EditionContext,
        biblia_repository: BibliaRepository,
        comparativo_repository: ComparativoRepository,
    ):
        self.page = page
        self.connections = connections
        self.selecao_view = selecao_view
        self.home_novo = home_novo
        self.home_antigo = home_antigo
        self.agente_view = agente_view
        self.downloads_view = downloads_view
        self.biblia_view = biblia_view
        self.content_manager = content_manager
        self.media_service = media_service
        self.theme_service = theme_service
        self.ctx_novo = ctx_novo
        self.ctx_antigo = ctx_antigo
        self.biblia_repository = biblia_repository
        self.comparativo_repository = comparativo_repository

        self.view_cache: dict[str, ft.View] = {}
        self.navigation_history: list[str] = []
        self.current_tracked_route: list[str] = [page.route or "/"]
        self.is_popping: bool = False

    def _check_missing_module_redirects(self, route_base: str) -> str:
        """Verifica se módulos opcionais dependentes estão instalados, redirecionando para downloads se necessário."""
        if route_base == ROUTE_ANTIGO or route_base.startswith(f"{ROUTE_ANTIGO}/"):
            if not self.content_manager.is_module_installed("hinario_antigo"):
                _show_route_warning(
                    self.page,
                    "O Hinário Tradicional (1996) precisa ser baixado na tela de módulos.",
                )
                self.page.route = ROUTE_DOWNLOADS
                return ROUTE_DOWNLOADS

        if route_base == ROUTE_BIBLIA or route_base.startswith(f"{ROUTE_BIBLIA}/"):
            if not self.content_manager.has_any_bible_installed():
                _show_route_warning(
                    self.page,
                    "Nenhuma tradução completa instalada. Baixe uma versão da Bíblia.",
                )
                self.page.route = ROUTE_DOWNLOADS
                return ROUTE_DOWNLOADS

        return route_base

    async def _render_biblia_route(
        self, route_base: str, route: str, new_views: list[ft.View]
    ) -> None:
        """Renderiza a rota da Bíblia Sagrada (/biblia ou /biblia/{book_id}/{chapter})."""
        if not (route_base == ROUTE_BIBLIA or route_base.startswith(f"{ROUTE_BIBLIA}/")):
            return

        initial_book_id = None
        initial_chapter = None
        parts = route_base.strip("/").split("/")
        if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
            initial_book_id = int(parts[1])
            initial_chapter = int(parts[2])
        elif len(parts) >= 2 and parts[1].isdigit():
            initial_book_id = int(parts[1])

        livro_p, cap_p, ver_p, hino_id_p = _parse_bible_route_query(route)

        self.view_cache[ROUTE_BIBLIA] = await self.biblia_view.build(
            self.page,
            initial_book_id=initial_book_id,
            initial_chapter=initial_chapter,
            livro=livro_p,
            capitulo=cap_p,
            versiculo_foco=ver_p,
            hino_origem_id=hino_id_p,
        )
        new_views.append(self.view_cache[ROUTE_BIBLIA])

    def _track_navigation(self, route: str) -> None:
        """Registra navegação na pilha de histórico preservando a rota anterior."""
        if not self.is_popping and self.current_tracked_route[0] != route:
            if (
                not self.navigation_history
                or self.navigation_history[-1] != self.current_tracked_route[0]
            ):
                self.navigation_history.append(self.current_tracked_route[0])
            self.current_tracked_route[0] = route

    async def route_change(self, e=None) -> None:
        """Manipula transições de rota construindo as visualizações empilhadas."""
        route = (e.route if (e and hasattr(e, "route") and e.route) else self.page.route) or "/"
        (
            route_base,
            initial_search,
            initial_categoria,
            initial_tema,
            from_hino,
        ) = _parse_route_query(route)

        route_base = self._check_missing_module_redirects(route_base)
        self._track_navigation(route)

        if "?" in route:
            self.page.route = route_base

        new_views: list[ft.View] = [self.selecao_view.build(self.page)]

        await _render_home_route(
            self.page,
            route_base,
            initial_search,
            initial_categoria,
            initial_tema,
            from_hino,
            self.view_cache,
            self.home_novo,
            self.home_antigo,
            new_views,
        )
        _render_agente_route(self.page, self.view_cache, self.agente_view, new_views)
        _render_downloads_route(self.page, self.view_cache, self.downloads_view, new_views)
        await self._render_biblia_route(route_base, route, new_views)

        active_comp_repo = (
            self.comparativo_repository
            if self.content_manager.is_module_installed("hinario_comparativo")
            else None
        )
        await _render_hino_route(
            self.page,
            route_base,
            self.ctx_novo,
            self.ctx_antigo,
            self.media_service,
            self.biblia_repository,
            new_views,
            comparativo_repository=active_comp_repo,
            theme_service=self.theme_service,
        )

        self.page.views.clear()
        self.page.views.extend(new_views)
        self.page.update()

    async def view_pop(self, e: ft.ViewPopEvent | None = None) -> None:
        """Gerencia o desempilhamento de rotas e retorno de modais/telas."""
        try:
            if hasattr(self.page, "pop_dialog") and self.page.pop_dialog():
                return
        except Exception:
            pass

        if self.navigation_history:
            prev_route = self.navigation_history.pop()
            self.is_popping = True
            self.current_tracked_route[0] = prev_route
            try:
                await self.page.push_route(prev_route)
            finally:
                self.is_popping = False
        elif len(self.page.views) > 1:
            self.page.views.pop()
            top_view = self.page.views[-1]
            self.page.route = top_view.route
            await self.route_change(None)
        else:
            await self.page.push_route("/")

    async def on_disconnect(self, e=None) -> None:
        """Encerra graciosamente todas as conexões SQLite ativas."""
        for conn in self.connections:
            try:
                await conn.close()
            except Exception:
                pass


async def main(page: ft.Page):
    """
    Ponto de entrada assíncrono do aplicativo Hinário Inteligente em Flet.
    Inicializa conexões SQLite (Hinário Novo, Hinário Antigo, Bíblia e Comparativo),
    restaura preferências e gerencia rotas dinâmicas com suporte a ambos os hinários.
    """
    ensure_page_dialogs(page)
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
    content_manager = ContentManager()
    updater_service = UpdaterService()

    selecao_view_instance = SelecaoView(
        theme_service=theme_service,
        updater_service=updater_service,
        content_manager=content_manager,
    )
    home_novo_instance = HinosView(
        hino_repository,
        favorito_repository,
        historico_repository,
        updater_service=updater_service,
        theme_service=theme_service,
        edition=EDITION_NOVO,
        antigo_hino_repo=antigo_hino_repo,
        antigo_fav_repo=antigo_fav_repo,
        antigo_hist_repo=antigo_hist_repo,
    )
    home_antigo_instance = HinosView(
        antigo_hino_repo,
        antigo_fav_repo,
        antigo_hist_repo,
        updater_service=updater_service,
        theme_service=theme_service,
        edition=EDITION_ANTIGO,
        novo_hino_repo=hino_repository,
        novo_fav_repo=favorito_repository,
        novo_hist_repo=historico_repository,
    )
    agente_view_instance = AgenteView(agente_service, culto_repository)
    downloads_view_instance = DownloadsView(
        content_manager=content_manager,
        media_service=media_service,
        theme_service=theme_service,
    )
    biblia_view_instance = BibliaView(
        biblia_repository,
        theme_service=theme_service,
        hino_repository=hino_repository,
        antigo_hino_repo=antigo_hino_repo,
    )

    router = AppRouter(
        page=page,
        connections=(
            db_connection,
            antigo_connection,
            biblia_connection,
            comparativo_connection,
        ),
        selecao_view=selecao_view_instance,
        home_novo=home_novo_instance,
        home_antigo=home_antigo_instance,
        agente_view=agente_view_instance,
        downloads_view=downloads_view_instance,
        biblia_view=biblia_view_instance,
        content_manager=content_manager,
        media_service=media_service,
        theme_service=theme_service,
        ctx_novo=ctx_novo,
        ctx_antigo=ctx_antigo,
        biblia_repository=biblia_repository,
        comparativo_repository=comparativo_repository,
    )

    page.on_route_change = router.route_change
    page.on_view_pop = router.view_pop
    page.on_disconnect = router.on_disconnect

    if not page.route or page.route == "/loading":
        page.route = "/"

    # 3. Transiciona para a rota inicial (Seleção de Hinários)
    await router.route_change(None)

    # 4. Dispara a verificação assíncrona de atualizações em segundo plano
    update_task = asyncio.create_task(_check_updates_background(page, updater_service))
    _background_tasks.add(update_task)
    update_task.add_done_callback(_background_tasks.discard)


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
