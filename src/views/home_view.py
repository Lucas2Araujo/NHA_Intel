import asyncio
import flet as ft
from typing import List, Optional
from src.repositories.hino_repository import HinoRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.models.hino import Hino


APP_VERSION = "0.2"


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

    async def build(self, page: ft.Page, initial_search: str = "") -> ft.View:
        page.title = f"Hinário Inteligente - v{APP_VERSION}"

        def _navigate(route_path: str):
            page.go(route_path)

        def _show_about_dialog(e=None):
            bs = ft.BottomSheet(
                content=ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text("Sobre o Aplicativo", weight=ft.FontWeight.BOLD, size=18),
                                    ft.IconButton(ft.Icons.CLOSE, on_click=lambda ev: page.pop_dialog()),
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
            page.show_dialog(bs)

        # Container da lista principal
        list_container = ft.ListView(
            controls=[],
            expand=True,
            spacing=2,
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        )

        # Container de exploração por temas/categorias (visível apenas na aba Explorar)
        explore_container = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=10,
        )

        def _render_hino_tiles(hinos: List[Hino]):
            tiles = []
            for hino in hinos:
                tile = ft.ListTile(
                    leading=ft.Container(
                        content=ft.Text(
                            hino.numero,
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
                    on_click=lambda e, h_id=hino.id: _navigate(f"/hino/{h_id}"),
                )
                tiles.append(tile)

            if not tiles:
                # Empty state específico por filtro
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

                list_container.controls = [
                    ft.Container(
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
                ]
            else:
                list_container.controls = tiles

        async def _load_explore_data():
            """Carrega categorias e temas para a aba Explorar."""
            explore_container.controls = [
                ft.Container(
                    content=ft.ProgressRing(),
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.all(30),
                )
            ]
            page.update()

            categorias = await self.hino_repository.get_categorias()
            temas = await self.hino_repository.get_temas()

            sections = []

            # Seção de Categorias
            if categorias:
                cat_chips = [
                    ft.Chip(
                        label=ft.Text(cat, size=12),
                        bgcolor=ft.Colors.BLUE_900,
                        on_click=lambda e, c=cat: asyncio.create_task(_filter_by_categoria(c)),
                    )
                    for cat in categorias
                ]
                sections.append(
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("📂 Categorias", weight=ft.FontWeight.BOLD, size=16),
                                ft.Row(controls=cat_chips, wrap=True, spacing=6, run_spacing=6),
                            ],
                            spacing=8,
                        ),
                        padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                    )
                )

            # Seção de Temas
            if temas:
                tema_chips = [
                    ft.Chip(
                        label=ft.Text(t, size=11),
                        bgcolor=ft.Colors.AMBER_900,
                        on_click=lambda e, tema=t: asyncio.create_task(_filter_by_tema(tema)),
                    )
                    for t in temas
                ]
                sections.append(
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text("🏷️ Temas", weight=ft.FontWeight.BOLD, size=16),
                                ft.Row(controls=tema_chips, wrap=True, spacing=6, run_spacing=6),
                            ],
                            spacing=8,
                        ),
                        padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                    )
                )

            if not sections:
                sections.append(
                    ft.Container(
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
                )

            explore_container.controls = sections
            page.update()

        async def _filter_by_categoria(cat: str):
            """Filtra hinos por categoria e volta para lista."""
            self.current_filter = "todos"
            filter_bar.selected = ["todos"]
            search_field.value = cat
            list_container.visible = True
            explore_container.visible = False

            hinos = await self.hino_repository.search_by_categoria(cat)
            _render_hino_tiles(hinos)
            page.update()

        async def _filter_by_tema(tema: str):
            """Filtra hinos por tema e volta para lista."""
            self.current_filter = "todos"
            filter_bar.selected = ["todos"]
            search_field.value = tema
            list_container.visible = True
            explore_container.visible = False

            hinos = await self.hino_repository.search_by_tema(tema)
            _render_hino_tiles(hinos)
            page.update()

        async def _load_current_filter_data(search_term: str = ""):
            if self.current_filter == "favoritos":
                hinos = await self.favorito_repository.get_favoritos()
                if search_term.strip():
                    term = search_term.lower().strip()
                    hinos = [
                        h
                        for h in hinos
                        if term in h.numero.lower() or term in h.titulo.lower()
                    ]
            elif self.current_filter == "recentes":
                hinos = await self.historico_repository.get_recentes()
                if search_term.strip():
                    term = search_term.lower().strip()
                    hinos = [
                        h
                        for h in hinos
                        if term in h.numero.lower() or term in h.titulo.lower()
                    ]
            else:
                hinos = await self.hino_repository.search(search_term)

            _render_hino_tiles(hinos)

        # Loading state inicial
        list_container.controls = [
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

        # Carrega dados e substitui o loading state
        if initial_search:
            search_field_value = initial_search
        else:
            search_field_value = ""

        await _load_current_filter_data(search_field_value)

        async def _execute_search(term: str):
            await asyncio.sleep(0.3)
            await _load_current_filter_data(term)
            page.update()

        def _on_search_change(e):
            term = e.control.value
            if self._search_task and not self._search_task.done():
                self._search_task.cancel()

            self._search_task = asyncio.create_task(_execute_search(term))

        search_field = ft.TextField(
            hint_text="Pesquisar hinos, letra, temas...",
            prefix_icon=ft.Icons.SEARCH,
            on_change=_on_search_change,
            border_radius=12,
            expand=True,
            content_padding=ft.Padding.symmetric(vertical=12, horizontal=16),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            value=search_field_value,
        )

        async def _on_filter_select(e):
            selected = e.control.selected
            if "favoritos" in selected:
                self.current_filter = "favoritos"
                list_container.visible = True
                explore_container.visible = False
            elif "recentes" in selected:
                self.current_filter = "recentes"
                list_container.visible = True
                explore_container.visible = False
            elif "explorar" in selected:
                self.current_filter = "explorar"
                list_container.visible = False
                explore_container.visible = True
                await _load_explore_data()
                page.update()
                return
            else:
                self.current_filter = "todos"
                list_container.visible = True
                explore_container.visible = False

            await _load_current_filter_data(search_field.value or "")
            page.update()

        filter_bar = ft.SegmentedButton(
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
            on_change=_on_filter_select,
            expand=True,
        )

        # Explore container começa oculto
        explore_container.visible = False

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
                        on_click=_show_about_dialog,
                    ),
                    ft.IconButton(
                        ft.Icons.AUTO_AWESOME,
                        tooltip="Agente Organizador de Cultos",
                        icon_color=ft.Colors.AMBER_300,
                        on_click=lambda e: _navigate("/agente"),
                    ),
                ],
            ),
            controls=[
                ft.Container(
                    content=search_field,
                    padding=ft.Padding.only(left=16, top=16, right=16, bottom=8),
                ),
                ft.Container(
                    content=filter_bar,
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.symmetric(horizontal=16, vertical=4),
                ),
                ft.Container(
                    content=list_container,
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=4, vertical=4),
                ),
                ft.Container(
                    content=explore_container,
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=4, vertical=4),
                ),
            ],
        )
