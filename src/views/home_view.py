import asyncio
import re
import unicodedata
import flet as ft
from typing import List, Optional
from src.repositories.hino_repository import HinoRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.models.hino import Hino


APP_VERSION = "0.2"


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
    return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8')


class HomeView:
    """
    Interface da Home do Hinário Inteligente v0.2.
    Funcionalidades:
    - Lista rolável virtualizada (ft.ListView) com 601 hinos
    - Busca full-text via FTS5 (letra, temas, categorias, textos bíblicos)
    - Abas: Todos | Favoritos | Recentes | Explorar (categorias/temas)
    - Loading state com ProgressRing no primeiro carregamento
    - Empty states ilustrados para Favoritos/Recentes vazios
    - Modal "Sobre o App" com informações da versão
    Segue as diretrizes do Flet 0.85+.
    """

    def __init__(
        self,
        hino_repository: HinoRepository,
        favorito_repository: FavoritoRepository,
        historico_repository: HistoricoRepository,
    ):
        self.hino_repository = hino_repository
        self.favorito_repository = favorito_repository
        self.historico_repository = historico_repository
        self._search_task: Optional[asyncio.Task] = None
        self.current_filter: str = "todos"
        self.current_search: str = ""
        self.current_sort: str = "num_asc"
        self.active_category: Optional[str] = None
        self.active_tema: Optional[str] = None
        self.page: Optional[ft.Page] = None
        self.list_container: Optional[ft.ListView] = None
        self.explore_container: Optional[ft.Column] = None
        self.search_field: Optional[ft.TextField] = None
        self.sort_button: Optional[ft.PopupMenuButton] = None
        self.filter_bar: Optional[ft.SegmentedButton] = None

    async def build(self, page: ft.Page, initial_search: str = "") -> ft.View:
        self.page = page
        self.page.title = f"Hinário Inteligente - v{APP_VERSION}"

        if initial_search:
            self.current_search = initial_search
            self.current_filter = "todos"

        self.list_container = ft.ListView(
            controls=[],
            expand=True,
            spacing=2,
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        )

        self.explore_container = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=10,
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

        await self._load_current_filter_data(self.current_search)

        self.search_field = ft.TextField(
            hint_text="Pesquisar hinos, letra, temas...",
            prefix_icon=ft.Icons.SEARCH,
            suffix=ft.IconButton(
                ft.Icons.CLEAR,
                on_click=self._clear_search,
                tooltip="Limpar busca",
                icon_size=18,
            ) if self.current_search else None,
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

        self.filter_bar = ft.SegmentedButton(
            selected=[self.current_filter],
            segments=[
                ft.Segment(value="todos", label=ft.Text("Todos")),
                ft.Segment(
                    value="favoritos",
                    label=ft.Text("Favoritos"),
                    icon=ft.Icons.FAVORITE,
                ),
                ft.Segment(
                    value="recentes", label=ft.Text("Recentes"), icon=ft.Icons.HISTORY
                ),
                ft.Segment(
                    value="explorar", label=ft.Text("Explorar"), icon=ft.Icons.EXPLORE
                ),
            ],
            on_change=self._on_filter_select,
            expand=True,
        )

        self.main_content_container = ft.Container(
            content=self.list_container,
            expand=True,
            padding=ft.Padding.symmetric(horizontal=4, vertical=4),
        )

        return ft.View(
            route="/",
            appbar=ft.AppBar(
                title=ft.Row(
                    controls=[
                        ft.Text("Hinário", weight=ft.FontWeight.BOLD),
                        ft.Container(
                            content=ft.Text(f"v{APP_VERSION}", size=11, color=ft.Colors.BLUE_200, weight=ft.FontWeight.BOLD),
                            padding=ft.Padding.only(left=4),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                ),
                center_title=True,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                actions=[
                    ft.IconButton(
                        ft.Icons.INFO_OUTLINED,
                        tooltip=f"Sobre o App (v{APP_VERSION})",
                        on_click=self._show_about_dialog,
                    ),
                    ft.IconButton(
                        ft.Icons.AUTO_AWESOME,
                        tooltip="Agente Organizador de Cultos",
                        icon_color=ft.Colors.AMBER_300,
                        on_click=lambda e: asyncio.create_task(self._navigate("/agente")),
                    ),
                ],
            ),
            controls=[
                ft.Container(
                    content=ft.Row(
                        controls=[
                            self.search_field,
                            self.sort_button,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    padding=ft.Padding.only(left=16, top=16, right=16, bottom=8),
                ),
                ft.Container(
                    content=self.filter_bar,
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.symmetric(horizontal=16, vertical=4),
                ),
                self.main_content_container,
            ],
        )

    async def _navigate(self, route_path: str):
        if self.page:
            await self.page.push_route(route_path)

    def _show_about_dialog(self, e=None):
        if not self.page:
            return
        bs = ft.BottomSheet(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text("Sobre o Aplicativo", weight=ft.FontWeight.BOLD, size=18),
                                ft.IconButton(ft.Icons.CLOSE, on_click=lambda ev: self.page.pop_dialog() if self.page else None),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Divider(),
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.BOOK_ROUNDED, size=36, color=ft.Colors.BLUE_200),
                                ft.Column(
                                    controls=[
                                        ft.Text("Hinário Inteligente", weight=ft.FontWeight.BOLD, size=16),
                                        ft.Text(f"Versão {APP_VERSION}", size=13, color=ft.Colors.AMBER_300, weight=ft.FontWeight.BOLD),
                                    ],
                                    spacing=2,
                                ),
                            ],
                            spacing=15,
                        ),
                        ft.Text(
                            "Aplicação completa para o Hinário Adventista (601 hinos).\n"
                            "Oferece busca full-text (FTS5) na letra e temas, favoritos, histórico, "
                            "reprodução e downloads de áudio offline, acessibilidade de leitura "
                            "(OpenDyslexic), exploração por categorias/temas e Agente Organizador "
                            "de Cultos por blocos litúrgicos.",
                            size=13,
                            color=ft.Colors.GREY_300,
                        ),
                    ],
                    tight=True,
                    spacing=12,
                ),
                padding=ft.Padding.all(20),
            )
        )
        self.page.show_dialog(bs)

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
                    ft.Text(msg, weight=ft.FontWeight.BOLD, size=16, text_align=ft.TextAlign.CENTER),
                    ft.Text(hint, size=13, color=ft.Colors.GREY_400, italic=True, text_align=ft.TextAlign.CENTER),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding.all(40),
        )

    def _render_hino_tiles(self, hinos: List[Hino]):
        if not self.list_container:
            return

        seen_ids = set()
        unique_hinos = []
        for h in hinos:
            if h.id is None:
                continue
            h_id = int(h.id)
            if h_id not in seen_ids:
                seen_ids.add(h_id)
                unique_hinos.append(h)

        tiles: List[ft.Control] = [
            ft.ListTile(
                leading=ft.Container(
                    content=ft.Text(
                        format_hino_number(hino.numero),
                        weight=ft.FontWeight.BOLD,
                        size=14,
                        color=ft.Colors.BLUE_200,
                    ),
                    width=50,
                    alignment=ft.Alignment.CENTER,
                ),
                title=ft.Text(
                    hino.titulo,
                    weight=ft.FontWeight.W_500,
                    size=16,
                ),
                on_click=lambda e=None, h_id=hino.id: asyncio.create_task(self._navigate(f"/hino/{h_id}")),
            )
            for hino in unique_hinos
        ]

        if not tiles:
            self.list_container.controls = [self._create_empty_state_control()]
        else:
            self.list_container.controls = tiles

    def _build_explore_section(self, title: str, items: List[str], icon: ft.IconData, icon_color: str, on_item_click) -> ft.Container:
        chips: List[ft.Control] = [
            ft.Chip(
                label=ft.Text(item, size=12),
                leading=ft.Icon(icon, size=16, color=icon_color),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                on_click=lambda e=None, val=item: asyncio.create_task(on_item_click(val)),
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
                    ft.Text("Nenhuma categoria ou tema disponível.", size=14, italic=True),
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
                self._build_explore_section("📂 Categorias", categorias, ft.Icons.FOLDER_OUTLINED, ft.Colors.BLUE_400, self._filter_by_categoria)
            )

        if temas:
            sections.append(
                self._build_explore_section("🏷️ Temas", temas, ft.Icons.LABEL_OUTLINED, ft.Colors.AMBER_400, self._filter_by_tema)
            )

        if not sections:
            sections.append(self._create_explore_empty_state())

        self.explore_container.controls = sections
        if self.page:
            self.page.update()

    def _sort_hinos(self, hinos: List[Hino]) -> List[Hino]:
        """Ordena os hinos de acordo com o modo ativo em self.current_sort."""
        if not hinos:
            return []

        if self.current_sort == "num_desc":
            return sorted(hinos, key=lambda h: parse_hino_number(h.numero), reverse=True)
        elif self.current_sort == "title_asc":
            return sorted(hinos, key=lambda h: strip_accents(h.titulo.lower()))
        elif self.current_sort == "title_desc":
            return sorted(hinos, key=lambda h: strip_accents(h.titulo.lower()), reverse=True)
        else:  # "num_asc" (padrão)

            return sorted(hinos, key=lambda h: parse_hino_number(h.numero))

    def _build_sort_menu_items(self) -> List[ft.PopupMenuItem]:
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
        asyncio.create_task(self._execute_sort_update())

    async def _execute_sort_update(self):
        await self._load_current_filter_data(self.current_search)
        if self.page:
            self.page.update()

    async def _filter_by_categoria(self, cat: str):
        """Filtra hinos por categoria e volta para lista."""
        self.current_filter = "categoria"
        self.active_category = cat
        self.active_tema = None
        self.current_search = ""
        if self.filter_bar:
            self.filter_bar.selected = []
        if self.search_field:
            self.search_field.value = ""
            self.search_field.suffix = None
        if self.main_content_container and self.list_container:
            self.main_content_container.content = self.list_container

        await self._load_current_filter_data("")
        if self.page:
            self.page.update()

    async def _filter_by_tema(self, tema: str):
        """Filtra hinos por tema e volta para lista."""
        self.current_filter = "tema"
        self.active_tema = tema
        self.active_category = None
        self.current_search = ""
        if self.filter_bar:
            self.filter_bar.selected = []
        if self.search_field:
            self.search_field.value = ""
            self.search_field.suffix = None
        if self.main_content_container and self.list_container:
            self.main_content_container.content = self.list_container

        await self._load_current_filter_data("")
        if self.page:
            self.page.update()

    async def _load_current_filter_data(self, search_term: str = ""):
        if self.current_filter == "categoria" and self.active_category:
            hinos = await self.hino_repository.search_by_categoria(self.active_category)
            if search_term and search_term.strip():
                term = search_term.lower().strip()
                hinos = [h for h in hinos if term in h.numero.lower() or term in h.titulo.lower()]
        elif self.current_filter == "tema" and self.active_tema:
            hinos = await self.hino_repository.search_by_tema(self.active_tema)
            if search_term and search_term.strip():
                term = search_term.lower().strip()
                hinos = [h for h in hinos if term in h.numero.lower() or term in h.titulo.lower()]
        elif self.current_filter == "favoritos":
            hinos = await self._fetch_filtered_favoritos(search_term)
        elif self.current_filter == "recentes":
            hinos = await self._fetch_filtered_recentes(search_term)
        else:
            hinos = await self.hino_repository.search(search_term)

        sorted_hinos = self._sort_hinos(hinos)
        self._render_hino_tiles(sorted_hinos)

    async def _fetch_filtered_favoritos(self, search_term: str) -> List[Hino]:
        hinos = await self.favorito_repository.get_favoritos()
        if not search_term.strip():
            return hinos
        term = search_term.lower().strip()
        return [h for h in hinos if term in h.numero.lower() or term in h.titulo.lower()]

    async def _fetch_filtered_recentes(self, search_term: str) -> List[Hino]:
        hinos = await self.historico_repository.get_recentes()
        if not search_term.strip():
            return hinos
        term = search_term.lower().strip()
        return [h for h in hinos if term in h.numero.lower() or term in h.titulo.lower()]

    async def _execute_search(self, term: str):
        await asyncio.sleep(0.3)
        await self._load_current_filter_data(term)
        if self.page:
            self.page.update()

    def _clear_search(self, e=None):
        self.current_search = ""
        self.active_category = None
        self.active_tema = None
        if self.current_filter in ("categoria", "tema"):
            self.current_filter = "todos"
            if self.filter_bar:
                self.filter_bar.selected = ["todos"]
        if self.search_field:
            self.search_field.value = ""
            self.search_field.suffix = None
        if self._search_task and not self._search_task.done():
            self._search_task.cancel()
        self._search_task = asyncio.create_task(self._execute_search(""))

    def _on_search_change(self, e):
        term = e.control.value or ""
        self.current_search = term
        if term and self.current_filter in ("categoria", "tema"):
            self.current_filter = "todos"
            self.active_category = None
            self.active_tema = None
            if self.filter_bar:
                self.filter_bar.selected = ["todos"]

        if self.search_field:
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

        self._search_task = asyncio.create_task(self._execute_search(term))

    async def _on_filter_select(self, e):
        selected = e.control.selected
        self.active_category = None
        self.active_tema = None

        if "explorar" in selected:
            self.current_filter = "explorar"
            if self.main_content_container and self.explore_container:
                self.main_content_container.content = self.explore_container
            await self._load_explore_data()
            if self.page:
                self.page.update()
            return

        if self.main_content_container and self.list_container:
            self.main_content_container.content = self.list_container

        if "favoritos" in selected:
            self.current_filter = "favoritos"
        elif "recentes" in selected:
            self.current_filter = "recentes"
        else:
            self.current_filter = "todos"

        search_val = self.current_search
        await self._load_current_filter_data(search_val or "")
        if self.page:
            self.page.update()

