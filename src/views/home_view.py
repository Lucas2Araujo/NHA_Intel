import asyncio
import re
import unicodedata

import flet as ft

from src.models.hino import Hino
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.hino_repository import HinoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.services.theme_service import ThemeService
from src.services.updater_service import UpdaterService
from src.views.settings_dialog import show_settings_dialog
from src.views.update_dialog import show_update_dialog

try:
    from src.version import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = "0.5.0"


def parse_hino_number(numero: str) -> float:
    """
    Converte o número do hino (ex: '587', '587_A', '587A', '587_B', '587.1', '587.2')
    para um número float comparável para ordenação numérica precisa.
    """
    if not numero:
        return 0.0

    clean = numero.strip()
    match = re.match(r"^(\d+)(?:[._-]?([A-Za-z0-9]+))?", clean)
    if match:
        main_num = float(match.group(1))
        sub = match.group(2)
        if sub:
            if sub.isdigit():
                return main_num + (float(sub) / 10.0)
            else:
                sub_val = (ord(sub[0].upper()) - ord("A") + 1) / 10.0
                return main_num + sub_val
        return main_num
    try:
        return float(clean)
    except ValueError:
        return 0.0


def format_hino_number(numero: str) -> str:
    """Formata '587_A' -> '587A' e '587_B' -> '587B' para exibição na UI."""
    if not numero:
        return ""
    return numero.replace("_", "").strip()


def strip_accents(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("utf-8")


class HomeView:
    """
    Interface da Home do Hinário Inteligente v0.2.
    Funcionalidades:
    - Lista rolável virtualizada (ft.ListView) com 601 hinos
    - Busca full-text via FTS5 (letra, temas, categorias, textos bíblicos)
    - Abas: Todos | Favoritos | Recentes | Explorar (categorias/temas)
    - Loading state com ProgressRing no primeiro carregamento
    - Empty states ilustrados para Favoritos/Recentes vazios
    - Modal "Sobre o App" com informações da versão e Toggle AMOLED
    - Suporte a temas dinâmicos (Sistema / AMOLED)
    Segue as diretrizes do Flet 0.85+.
    """

    def __init__(
        self,
        hino_repository: HinoRepository,
        favorito_repository: FavoritoRepository,
        historico_repository: HistoricoRepository,
        updater_service: UpdaterService | None = None,
        theme_service: ThemeService | None = None,
        edition: str = "novo",
        novo_hino_repo: HinoRepository | None = None,
        novo_fav_repo: FavoritoRepository | None = None,
        novo_hist_repo: HistoricoRepository | None = None,
        antigo_hino_repo: HinoRepository | None = None,
        antigo_fav_repo: FavoritoRepository | None = None,
        antigo_hist_repo: HistoricoRepository | None = None,
    ):
        self.hino_repository = hino_repository
        self.favorito_repository = favorito_repository
        self.historico_repository = historico_repository
        self.updater_service = updater_service or UpdaterService()
        self.theme_service = theme_service or ThemeService(
            hino_repository.db_connection
        )
        self.edition: str = edition

        self._novo_repos = (
            (novo_hino_repo, novo_fav_repo, novo_hist_repo)
            if (novo_hino_repo and novo_fav_repo and novo_hist_repo)
            else (
                (hino_repository, favorito_repository, historico_repository)
                if edition == "novo"
                else None
            )
        )
        self._antigo_repos = (
            (antigo_hino_repo, antigo_fav_repo, antigo_hist_repo)
            if (antigo_hino_repo and antigo_fav_repo and antigo_hist_repo)
            else (
                (hino_repository, favorito_repository, historico_repository)
                if edition == "antigo"
                else None
            )
        )

        self._search_task: asyncio.Task | None = None
        self._sort_task: asyncio.Task | None = None
        self._chunk_render_task: asyncio.Task | None = None
        self.current_filter: str = "todos"
        self.current_search: str = ""
        self.current_sort: str = "num_asc"
        self.active_category: str | None = None
        self.active_tema: str | None = None
        self.origin_hino_id: int | None = None
        self.page: ft.Page | None = None
        self.list_container: ft.ListView | None = None
        self.explore_container: ft.Column | None = None
        self.search_field: ft.TextField | None = None
        self.sort_button: ft.PopupMenuButton | None = None
        self.edition_selector: ft.SegmentedButton | None = None
        self.filter_bar: ft.SegmentedButton | None = None
        self.active_filter_banner: ft.Container | None = None
        self._explore_sections_cached: list[ft.Control] | None = None
        self._cached_view: ft.View | None = None

    async def build(
        self,
        page: ft.Page,
        initial_search: str = "",
        initial_categoria: str | None = None,
        initial_tema: str | None = None,
        origin_hino_id: int | None = None,
    ) -> ft.View:
        self.page = page
        edition_title = (
            "Hinário Novo" if self.edition == "novo" else "Hinário Tradicional"
        )
        self.page.title = f"{edition_title} - v{APP_VERSION}"

        if self.theme_service:
            self.theme_service.apply_theme(page, edition=self.edition)

        # Se já tivermos a view construída, aplicamos o filtro recebido ou retornamos o cache
        if self._cached_view is not None:
            if initial_categoria:
                await self._filter_by_categoria(
                    initial_categoria, origin_hino_id=origin_hino_id
                )
                return self._cached_view
            elif initial_tema:
                await self._filter_by_tema(initial_tema, origin_hino_id=origin_hino_id)
                return self._cached_view
            elif initial_search:
                self.origin_hino_id = None
                self.current_search = initial_search
                if self.search_field:
                    self.search_field.value = initial_search
                    self.search_field.suffix = ft.IconButton(
                        ft.Icons.CLEAR,
                        on_click=self._clear_search,
                        tooltip="Limpar busca",
                        icon_size=18,
                    )
                self.current_filter = "todos"
                if self.filter_bar:
                    self.filter_bar.selected = ["todos"]
                self._show_content_view("list")
                await self._load_current_filter_data(initial_search)
                return self._cached_view
            return self._cached_view

        if initial_categoria:
            self.current_filter = "categoria"
            self.active_category = initial_categoria
            self.active_tema = None
            self.origin_hino_id = origin_hino_id
        elif initial_tema:
            self.current_filter = "tema"
            self.active_tema = initial_tema
            self.active_category = None
            self.origin_hino_id = origin_hino_id
        elif initial_search:
            self.current_search = initial_search
            self.current_filter = "todos"
            self.origin_hino_id = None

        self.list_container = ft.ListView(
            controls=[],
            expand=True,
            spacing=2,
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            visible=True,
        )

        self.explore_container = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=10,
            visible=False,
        )

        # Loading state inicial
        self.list_container.controls = [
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.ProgressRing(),
                        ft.Text("Carregando hinos...", size=14, italic=True),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10,
                ),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.all(40),
            )
        ]

        self.active_filter_banner = ft.Container(
            visible=False,
            padding=ft.Padding.symmetric(horizontal=16, vertical=2),
        )

        self.search_field = ft.TextField(
            hint_text="Pesquisar hinos, letra, temas...",
            prefix_icon=ft.Icons.SEARCH,
            suffix=(
                ft.IconButton(
                    ft.Icons.CLEAR,
                    on_click=self._clear_search,
                    tooltip="Limpar busca",
                    icon_size=18,
                )
                if self.current_search
                else None
            ),
            on_change=self._on_search_change,
            border_radius=12,
            expand=True,
            content_padding=ft.Padding.symmetric(vertical=12, horizontal=16),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            value=self.current_search,
        )

        self.sort_button = ft.PopupMenuButton(
            icon=ft.Icons.SORT,
            tooltip="Modo de Ordenação",
            items=self._build_sort_menu_items(),
        )

        self.edition_selector = ft.SegmentedButton(
            selected=[self.edition],
            allow_empty_selection=False,
            show_selected_icon=False,
            segments=[
                ft.Segment(
                    value="novo",
                    label=ft.Text("Novo (2022)", size=12),
                    icon=ft.Icon(ft.Icons.AUTO_AWESOME_OUTLINED, size=15),
                ),
                ft.Segment(
                    value="antigo",
                    label=ft.Text("Tradicional (1996)", size=12),
                    icon=ft.Icon(ft.Icons.HISTORY_EDU_OUTLINED, size=15),
                ),
            ],
            on_change=self._on_edition_select,
            expand=True,
        )

        self.filter_bar = ft.SegmentedButton(
            selected=[
                "explorar"
                if self.current_filter in ("categoria", "tema")
                else self.current_filter
            ],
            allow_empty_selection=True,
            show_selected_icon=False,
            segments=[
                ft.Segment(value="todos", label=ft.Text("Todos", size=13)),
                ft.Segment(value="favoritos", label=ft.Text("Favoritos", size=13)),
                ft.Segment(value="recentes", label=ft.Text("Recentes", size=13)),
                ft.Segment(value="explorar", label=ft.Text("Explorar", size=13)),
            ],
            on_change=self._on_filter_select,
            expand=True,
        )

        await self._load_current_filter_data(self.current_search)


        self.main_content_container = ft.Container(
            content=ft.Column(
                controls=[
                    self.list_container,
                    self.explore_container,
                ],
                expand=True,
            ),
            expand=True,
            padding=ft.Padding.symmetric(horizontal=4, vertical=4),
        )

        badge_year = "2022" if self.edition == "novo" else "1996"
        badge_color = (
            (
                self.theme_service.get_accent_color()
                if self.theme_service
                else ft.Colors.PRIMARY
            )
            if self.edition == "novo"
            else ft.Colors.AMBER_300
        )

        self._cached_view = ft.View(
            route=f"/{self.edition}",
            bgcolor=ft.Colors.SURFACE,
            appbar=ft.AppBar(
                leading=ft.IconButton(
                    ft.Icons.ARROW_BACK,
                    tooltip="Voltar ao Menu Principal",
                    on_click=lambda e: asyncio.create_task(self._navigate("/")),
                ),
                title=ft.Row(
                    controls=[
                        ft.Text(edition_title, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            content=ft.Text(
                                badge_year,
                                size=11,
                                color=badge_color,
                                weight=ft.FontWeight.BOLD,
                            ),
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                            border_radius=4,
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                ),
                center_title=True,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                actions=[
                    ft.IconButton(
                        ft.Icons.INFO_OUTLINE,
                        tooltip="Sobre o App e Configurações",
                        on_click=self._show_about_dialog,
                    ),
                ],
            ),
            controls=[
                ft.SafeArea(
                    maintain_bottom_view_padding=True,
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                content=ft.Row(
                                    controls=[
                                        self.search_field,
                                        self.sort_button,
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                padding=ft.Padding.only(
                                    left=16, top=16, right=16, bottom=6
                                ),
                            ),
                            ft.Container(
                                content=ft.Row(
                                    controls=[self.edition_selector],
                                ),
                                alignment=ft.Alignment.CENTER,
                                padding=ft.Padding.symmetric(horizontal=16, vertical=2),
                            ),
                            ft.Container(
                                content=ft.Row(
                                    controls=[self.filter_bar],
                                ),
                                alignment=ft.Alignment.CENTER,
                                padding=ft.Padding.symmetric(horizontal=16, vertical=4),
                            ),
                            self.active_filter_banner,
                            self.main_content_container,
                        ],
                        expand=True,
                    ),
                    expand=True,
                ),
            ],
        )
        return self._cached_view

    async def _on_edition_select(self, e: ft.ControlEvent):
        selected = e.control.selected
        if not selected:
            return
        new_edition = next(iter(selected))
        if new_edition == self.edition:
            return
        if self.page:
            await self.page.push_route(f"/{new_edition}")
        else:
            await self.switch_edition(new_edition)

    async def switch_edition(self, new_edition: str):
        """Alterna a edição de hinos assincronamente e recarrega os dados."""
        if new_edition not in ("novo", "antigo"):
            return
        self.edition = new_edition
        if new_edition == "novo" and self._novo_repos:
            self.hino_repository, self.favorito_repository, self.historico_repository = self._novo_repos
        elif new_edition == "antigo" and self._antigo_repos:
            self.hino_repository, self.favorito_repository, self.historico_repository = self._antigo_repos

        if self.edition_selector:
            self.edition_selector.selected = [new_edition]

        edition_title = (
            "Hinário Novo" if self.edition == "novo" else "Hinário Tradicional"
        )
        if self.page:
            self.page.title = f"{edition_title} - v{APP_VERSION}"
            if self.theme_service:
                self.theme_service.apply_theme(self.page, edition=self.edition)

        self._cached_view = None
        await self._load_current_filter_data(self.current_search)
        if self.page:
            try:
                self.page.update()
            except Exception:
                pass

    async def _navigate(self, route_path: str):
        if self.page:
            await self.page.push_route(route_path)

    async def _open_url(self, url: str):
        """Abre uma URL externa no navegador padrão ou app nativo."""
        try:
            await ft.UrlLauncher().launch_url(url)
        except Exception:
            pass

    def _show_about_dialog(self, e=None):
        if not self.page:
            return

        show_settings_dialog(
            page=self.page,
            theme_service=self.theme_service,
            updater_service=self.updater_service,
            edition=self.edition,
            on_check_updates=self._check_updates_manual,
        )

    async def _on_amoled_toggle(self, enabled: bool) -> None:
        """Manipula a alternância do Modo AMOLED."""
        if self.theme_service and self.page:
            await self.theme_service.toggle_amoled(
                self.page, enabled, edition=self.edition
            )

    def _show_snack(self, message: str, duration: int = 3000) -> None:
        """Exibe um SnackBar de forma segura compatível com o Flet."""
        if not self.page:
            return
        snack = ft.SnackBar(ft.Text(message), duration=duration)
        try:
            if hasattr(self.page, "open"):
                self.page.open(snack)
            elif hasattr(self.page, "show_snack_bar"):
                self.page.show_snack_bar(snack)
        except Exception:
            pass

    async def _check_updates_manual(self):
        """Verifica manualmente por atualizações a partir do modal Sobre."""
        if not self.page or not self.updater_service:
            return

        self._show_snack("Buscando atualizações no GitHub...", duration=2000)

        update_info = await self.updater_service.check_for_updates()
        if update_info.get("update_available"):
            try:
                self.page.pop_dialog()
            except Exception:
                pass
            show_update_dialog(self.page, update_info, self.updater_service)
        else:
            err = update_info.get("error")
            msg = (
                f"Você já está na versão mais recente (v{APP_VERSION})!"
                if not err
                else f"Não foi possível verificar atualizações: {err}"
            )
            self._show_snack(msg, duration=3000)

    def _create_empty_state_control(self) -> ft.Container:
        if self.current_filter == "favoritos":
            icon = ft.Icons.FAVORITE_BORDER
            msg = "Nenhum hino favorito ainda."
            hint = "Toque no ❤️ na tela do hino para salvar seus favoritos!"
        elif self.current_filter == "recentes":
            icon = ft.Icons.HISTORY
            msg = "Nenhum hino acessado recentemente."
            hint = "Seus hinos acessados aparecerão aqui automaticamente."
        else:
            icon = ft.Icons.SEARCH_OFF
            msg = "Nenhum hino encontrado."
            hint = "Tente buscar por outro termo, número ou trecho da letra."

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(icon, size=48, color=ft.Colors.GREY_600),
                    ft.Text(
                        msg,
                        weight=ft.FontWeight.BOLD,
                        size=16,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        hint,
                        size=13,
                        color=ft.Colors.GREY_400,
                        italic=True,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.all(40),
        )

    def _render_hino_tiles(self, hinos: list[Hino]):
        if not self.list_container:
            return

        seen_ids = set()
        unique_hinos = []
        for h in hinos:
            if h.id is None:
                continue
            h_id = h.id
            if h_id not in seen_ids:
                seen_ids.add(h_id)
                unique_hinos.append(h)

        accent = (
            self.theme_service.get_accent_color()
            if self.theme_service
            else ft.Colors.PRIMARY
        )
        num_color = (
            accent
            if self.edition == "novo"
            else (
                ft.Colors.PURPLE_200
                if (self.theme_service and self.theme_service.is_amoled)
                else ft.Colors.AMBER_300
            )
        )

        tiles: list[ft.Control] = [
            ft.ListTile(
                leading=ft.Container(
                    content=ft.Text(
                        format_hino_number(hino.numero),
                        weight=ft.FontWeight.BOLD,
                        size=13,
                        color=num_color,
                    ),
                    width=52,
                    height=36,
                    border_radius=8,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    alignment=ft.Alignment.CENTER,
                ),
                title=ft.Text(
                    hino.titulo,
                    weight=ft.FontWeight.W_500,
                    size=15,
                    color=ft.Colors.ON_SURFACE,
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                shape=ft.RoundedRectangleBorder(radius=12),
                hover_color=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                content_padding=ft.Padding.symmetric(horizontal=12, vertical=4),
                on_click=lambda e=None, h_id=hino.id: asyncio.create_task(
                    self._navigate(f"/{self.edition}/hino/{h_id}")
                ),
            )
            for hino in unique_hinos
        ]

        if not tiles:
            self.list_container.controls = [self._create_empty_state_control()]
        else:
            chunk_size = 40
            if len(tiles) <= chunk_size:
                self.list_container.controls = tiles
            else:
                self.list_container.controls = tiles[:chunk_size]
                if self._chunk_render_task and not self._chunk_render_task.done():
                    self._chunk_render_task.cancel()
                self._chunk_render_task = asyncio.create_task(
                    self._append_remaining_tiles(tiles[chunk_size:])
                )

    async def _append_remaining_tiles(self, remaining: list[ft.Control]):
        """Anexa o restante dos hinos de forma não-bloqueante para não travar a UI em ARMv7."""
        await asyncio.sleep(0.01)
        if self.list_container and remaining:
            self.list_container.controls.extend(remaining)
            if self.page:
                try:
                    self.list_container.update()
                except Exception:
                    self.page.update()

    def _build_explore_section(
        self,
        title: str,
        items: list[str],
        icon: ft.IconData,
        icon_color: str,
        on_item_click,
    ) -> ft.Container:
        chips: list[ft.Control] = [
            ft.Chip(
                label=ft.Text(item, size=12),
                leading=ft.Icon(icon, size=16, color=icon_color),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                on_click=lambda e=None, val=item: asyncio.create_task(
                    on_item_click(val)
                ),
            )
            for item in items
        ]
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(title, weight=ft.FontWeight.BOLD, size=16),
                    ft.Row(controls=chips, wrap=True, spacing=6, run_spacing=6),
                ],
                spacing=8,
            ),
            padding=ft.Padding.symmetric(horizontal=16, vertical=8),
        )

    def _create_explore_empty_state(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.EXPLORE_OFF, size=48, color=ft.Colors.GREY_600),
                    ft.Text(
                        "Nenhuma categoria ou tema disponível.", size=14, italic=True
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.all(30),
        )

    async def _load_explore_data(self):
        """Carrega categorias e temas para a aba Explorar."""
        if not self.explore_container:
            return

        if self._explore_sections_cached:
            self.explore_container.controls = list(self._explore_sections_cached)
            if self.page:
                self.page.update()
            return

        self.explore_container.controls = [
            ft.Container(
                content=ft.ProgressRing(),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.all(30),
            )
        ]
        if self.page:
            self.page.update()

        categorias = await self.hino_repository.get_categorias()
        temas = await self.hino_repository.get_temas()

        sections = []
        if categorias:
            sections.append(
                self._build_explore_section(
                    "📂 Categorias",
                    categorias,
                    ft.Icons.FOLDER_OUTLINED,
                    (
                        self.theme_service.get_accent_color()
                        if self.theme_service
                        else ft.Colors.PRIMARY
                    ),
                    self._filter_by_categoria,
                )
            )

        if temas:
            sections.append(
                self._build_explore_section(
                    "🏷️ Temas",
                    temas,
                    ft.Icons.LABEL_OUTLINED,
                    ft.Colors.AMBER_400,
                    self._filter_by_tema,
                )
            )

        if not sections:
            sections.append(self._create_explore_empty_state())

        self._explore_sections_cached = sections
        self.explore_container.controls = list(sections)
        if self.page:
            self.page.update()

    def _sort_hinos(self, hinos: list[Hino]) -> list[Hino]:
        """Ordena os hinos de acordo com o modo ativo em self.current_sort."""
        if not hinos:
            return []

        if self.current_sort == "num_desc":
            return sorted(
                hinos, key=lambda h: parse_hino_number(h.numero), reverse=True
            )
        elif self.current_sort == "title_asc":
            return sorted(hinos, key=lambda h: strip_accents(h.titulo.lower()))
        elif self.current_sort == "title_desc":
            return sorted(
                hinos, key=lambda h: strip_accents(h.titulo.lower()), reverse=True
            )
        else:  # "num_asc" (padrão)

            return sorted(hinos, key=lambda h: parse_hino_number(h.numero))

    def _build_sort_menu_items(self) -> list[ft.PopupMenuItem]:
        return [
            ft.PopupMenuItem(
                content=ft.Text("Número (Crescente 1 → N)"),
                icon=ft.Icons.ARROW_UPWARD,
                checked=self.current_sort == "num_asc",
                on_click=lambda e: self._on_sort_change("num_asc"),
            ),
            ft.PopupMenuItem(
                content=ft.Text("Número (Decrescente N → 1)"),
                icon=ft.Icons.ARROW_DOWNWARD,
                checked=self.current_sort == "num_desc",
                on_click=lambda e: self._on_sort_change("num_desc"),
            ),
            ft.PopupMenuItem(
                content=ft.Text("Título (A → Z)"),
                icon=ft.Icons.SORT_BY_ALPHA,
                checked=self.current_sort == "title_asc",
                on_click=lambda e: self._on_sort_change("title_asc"),
            ),
            ft.PopupMenuItem(
                content=ft.Text("Título (Z → A)"),
                icon=ft.Icons.SORT_BY_ALPHA,
                checked=self.current_sort == "title_desc",
                on_click=lambda e: self._on_sort_change("title_desc"),
            ),
        ]

    def _on_sort_change(self, new_sort: str):
        self.current_sort = new_sort
        if self.sort_button:
            self.sort_button.items = self._build_sort_menu_items()
        if self._sort_task and not self._sort_task.done():
            self._sort_task.cancel()
        self._sort_task = asyncio.create_task(self._execute_sort_update())

    async def _execute_sort_update(self):
        await self._load_current_filter_data(self.current_search)
        if self.page:
            self.page.update()

    def _update_filter_banner(self, count: int = 0):
        """Atualiza a exibição do banner de filtro ativo (Categoria ou Tema)."""
        if not self.active_filter_banner:
            return

        if self.current_filter == "categoria" and self.active_category:
            self.active_filter_banner.visible = True
            btn_label = "Voltar para o hino" if self.origin_hino_id else "Explorar Categorias"
            btn_action = (
                (lambda e: asyncio.create_task(self._navigate_back_to_hino()))
                if self.origin_hino_id
                else (lambda e: asyncio.create_task(self._return_to_explore()))
            )
            self.active_filter_banner.content = ft.Container(
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.FOLDER,
                            size=18,
                            color=(
                                self.theme_service.get_accent_color()
                                if self.theme_service
                                else ft.Colors.PRIMARY
                            ),
                        ),
                        ft.Text(
                            f"Categoria: {self.active_category} ({count} hinos)",
                            weight=ft.FontWeight.W_500,
                            size=13,
                            expand=True,
                        ),
                        ft.TextButton(
                            content=ft.Text(btn_label),
                            icon=ft.Icons.ARROW_BACK,
                            on_click=btn_action,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE,
                            tooltip="Limpar filtro de categoria",
                            icon_size=18,
                            on_click=lambda e: asyncio.create_task(
                                self._clear_category_or_theme_filter()
                            ),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            )
        elif self.current_filter == "tema" and self.active_tema:
            self.active_filter_banner.visible = True
            btn_label = "Voltar para o hino" if self.origin_hino_id else "Explorar Temas"
            btn_action = (
                (lambda e: asyncio.create_task(self._navigate_back_to_hino()))
                if self.origin_hino_id
                else (lambda e: asyncio.create_task(self._return_to_explore()))
            )
            self.active_filter_banner.content = ft.Container(
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.LABEL, size=18, color=ft.Colors.AMBER_400),
                        ft.Text(
                            f"Tema: {self.active_tema} ({count} hinos)",
                            weight=ft.FontWeight.W_500,
                            size=13,
                            expand=True,
                        ),
                        ft.TextButton(
                            content=ft.Text(btn_label),
                            icon=ft.Icons.ARROW_BACK,
                            on_click=btn_action,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE,
                            tooltip="Limpar filtro de tema",
                            icon_size=18,
                            on_click=lambda e: asyncio.create_task(
                                self._clear_category_or_theme_filter()
                            ),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            )
        else:
            self.active_filter_banner.visible = False
            self.active_filter_banner.content = None

    async def _navigate_back_to_hino(self) -> None:
        """Navega de volta para o hino de onde o filtro se originou."""
        if self.page and self.origin_hino_id:
            hino_id = self.origin_hino_id
            await self.page.push_route(f"/{self.edition}/hino/{hino_id}")

    def _show_content_view(self, mode: str):
        """Alterna a visibilidade entre a listagem de hinos e o painel de exploração."""
        if not self.list_container or not self.explore_container:
            return
        if mode == "explorar":
            self.list_container.visible = False
            self.explore_container.visible = True
        else:
            self.list_container.visible = True
            self.explore_container.visible = False

    def _reset_search_state(self) -> None:
        """Limpa o campo de busca e o estado de pesquisa."""
        self.current_search = ""
        if self.search_field:
            self.search_field.value = ""
            self.search_field.suffix = None

    def _reset_filter_banner(self) -> None:
        """Oculta e limpa os filtros de categoria/tema."""
        self.active_category = None
        self.active_tema = None
        self.origin_hino_id = None
        if self.active_filter_banner:
            self.active_filter_banner.visible = False

    async def _handle_empty_filter_selection(self) -> None:
        """Restaura o filtro quando ocorre desseleção acidental de aba."""
        if self.current_filter in ("categoria", "tema"):
            return
        valid_filters = ("todos", "favoritos", "recentes", "explorar")
        fallback = (
            self.current_filter if self.current_filter in valid_filters else "todos"
        )
        if self.filter_bar:
            self.filter_bar.selected = [fallback]
        if self.page:
            self.page.update()

    async def _return_to_explore(self):
        """Retorna para a visão geral de exploração de categorias e temas."""
        self._reset_filter_banner()
        self._reset_search_state()
        self.current_filter = "explorar"
        if self.filter_bar:
            self.filter_bar.selected = ["explorar"]
        if self.sort_button:
            self.sort_button.visible = False
        self._show_content_view("explorar")
        await self._load_explore_data()
        if self.page:
            self.page.update()

    async def _clear_category_or_theme_filter(self):
        """Limpa o filtro ativo de categoria/tema e volta para todos os hinos."""
        self._reset_filter_banner()
        self._reset_search_state()
        self.current_filter = "todos"
        if self.filter_bar:
            self.filter_bar.selected = ["todos"]
        if self.sort_button:
            self.sort_button.visible = True
        self._show_content_view("list")
        await self._load_current_filter_data("")
        if self.page:
            self.page.update()

    async def _filter_by_categoria(self, cat: str, origin_hino_id: int | None = None):
        """Filtra hinos por categoria e volta para lista."""
        self._reset_search_state()
        self.current_filter = "categoria"
        self.active_category = cat
        self.active_tema = None
        self.origin_hino_id = origin_hino_id
        if self.filter_bar:
            self.filter_bar.selected = ["explorar"]
        if self.sort_button:
            self.sort_button.visible = True
        self._show_content_view("list")

        await self._load_current_filter_data("")
        if self.page:
            self.page.update()

    async def _filter_by_tema(self, tema: str, origin_hino_id: int | None = None):
        """Filtra hinos por tema e volta para lista."""
        self._reset_search_state()
        self.current_filter = "tema"
        self.active_tema = tema
        self.active_category = None
        self.origin_hino_id = origin_hino_id
        if self.filter_bar:
            self.filter_bar.selected = ["explorar"]
        if self.sort_button:
            self.sort_button.visible = True
        self._show_content_view("list")

        await self._load_current_filter_data("")
        if self.page:
            self.page.update()

    @staticmethod
    def _filter_by_text(hinos: list[Hino], search_term: str) -> list[Hino]:
        """Filtra lista em memória por termo de busca no número ou título."""
        if not search_term or not search_term.strip():
            return hinos
        term = search_term.lower().strip()
        return [
            h for h in hinos if term in h.numero.lower() or term in h.titulo.lower()
        ]

    async def _fetch_hinos_by_filter(
        self, search_term: str
    ) -> tuple[list[Hino], bool, int]:
        """Obtém hinos conforme o filtro ativo retornando (hinos, deve_ordenar, banner_count)."""
        if self.current_filter == "categoria" and self.active_category:
            hinos = await self.hino_repository.search_by_categoria(self.active_category)
            filtered = self._filter_by_text(hinos, search_term)
            return filtered, True, len(filtered)

        if self.current_filter == "tema" and self.active_tema:
            hinos = await self.hino_repository.search_by_tema(self.active_tema)
            filtered = self._filter_by_text(hinos, search_term)
            return filtered, True, len(filtered)

        if self.current_filter == "favoritos":
            hinos = await self._fetch_filtered_favoritos(search_term)
            return hinos, True, 0

        if self.current_filter == "recentes":
            hinos = await self._fetch_filtered_recentes(search_term)
            # Na aba Recentes, preserva estritamente a ordem cronológica
            return hinos, False, 0

        hinos = await self.hino_repository.search(search_term)
        return hinos, True, 0

    async def _load_current_filter_data(self, search_term: str = ""):
        hinos, should_sort, banner_count = await self._fetch_hinos_by_filter(
            search_term
        )
        self._update_filter_banner(banner_count)

        sorted_hinos = self._sort_hinos(hinos) if should_sort else hinos

        if self.sort_button:
            self.sort_button.visible = self.current_filter not in (
                "recentes",
                "explorar",
            )

        self._render_hino_tiles(sorted_hinos)

    async def _fetch_filtered_favoritos(self, search_term: str) -> list[Hino]:
        hinos = await self.favorito_repository.get_favoritos()
        return self._filter_by_text(hinos, search_term)

    async def _fetch_filtered_recentes(self, search_term: str) -> list[Hino]:
        hinos = await self.historico_repository.get_recentes()
        return self._filter_by_text(hinos, search_term)

    async def _execute_search(self, term: str, debounce: float = 0.25):
        if debounce > 0:
            await asyncio.sleep(debounce)
        await self._load_current_filter_data(term)
        if self.page:
            try:
                if self.list_container:
                    self.list_container.update()
                if self.active_filter_banner:
                    self.active_filter_banner.update()
            except Exception:
                self.page.update()

    def _clear_search(self, e=None):
        self.current_search = ""
        if self.search_field:
            self.search_field.value = ""
            self.search_field.suffix = None
        if self._search_task and not self._search_task.done():
            self._search_task.cancel()
        self._search_task = asyncio.create_task(self._execute_search("", debounce=0.0))

    def _on_search_change(self, e):
        term = e.control.value or ""
        self.current_search = term
        if term and self.current_filter in ("favoritos", "recentes", "explorar"):
            self.current_filter = "todos"
            self.active_category = None
            self.active_tema = None
            if self.active_filter_banner:
                self.active_filter_banner.visible = False
            if self.filter_bar:
                self.filter_bar.selected = ["todos"]
            if self.sort_button:
                self.sort_button.visible = True
            self._show_content_view("list")

        if self.search_field:
            self.search_field.value = term
            self.search_field.suffix = (
                ft.IconButton(
                    ft.Icons.CLEAR,
                    on_click=self._clear_search,
                    tooltip="Limpar busca",
                    icon_size=18,
                )
                if term
                else None
            )

        if self._search_task and not self._search_task.done():
            self._search_task.cancel()

        clean = term.strip()
        is_numeric = bool(clean and re.match(r"^\d+[A-Za-z]?$", clean))
        debounce_time = 0.0 if is_numeric or not clean else 0.25

        self._search_task = asyncio.create_task(
            self._execute_search(term, debounce=debounce_time)
        )

    async def _on_filter_select(self, e):
        selected = e.control.selected
        if not selected:
            await self._handle_empty_filter_selection()
            return

        self._reset_search_state()

        if "explorar" in selected:
            await self._return_to_explore()
            return

        self._reset_filter_banner()
        self._show_content_view("list")

        filter_map = {"favoritos": "favoritos", "recentes": "recentes"}
        self.current_filter = next(
            (filter_map[k] for k in filter_map if k in selected), "todos"
        )

        await self._load_current_filter_data("")
        if self.page:
            self.page.update()


# Alias oficial da Sprint 3 para a visualização da lista de hinos
HinosView = HomeView
