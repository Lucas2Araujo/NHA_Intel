import asyncio
import flet as ft
from typing import List, Optional
from src.repositories.hino_repository import HinoRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.models.hino import Hino


class HomeView:
    """
    Interface da Home do Hinário Inteligente.
    Exibe uma lista rolável virtualizada (ft.ListView) totalmente responsiva por toda a largura da tela,
    com busca assíncrona com debounce, abas de filtragem (Todos os Hinos, Favoritos, Recentes)
    e atalho para o Agente Organizador de Cultos.
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

    async def build(self, page: ft.Page) -> ft.View:
        page.title = "Hinário Inteligente"
        page.theme_mode = ft.ThemeMode.DARK

        def _navigate(route_path: str):
            page.go(route_path)

        list_container = ft.ListView(
            controls=[],
            expand=True,
            spacing=2,
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
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
                    subtitle=ft.Text(
                        f"Hino {hino.numero}",
                        size=12,
                        color=ft.Colors.GREY_400,
                    ),
                    on_click=lambda e, h_id=hino.id: _navigate(f"/hino/{h_id}"),
                )
                tiles.append(tile)

            if not tiles:
                list_container.controls = [
                    ft.Container(
                        content=ft.Text(
                            "Nenhum hino encontrado.", italic=True, size=14
                        ),
                        alignment=ft.Alignment.CENTER,
                        padding=ft.Padding.all(30),
                    )
                ]
            else:
                list_container.controls = tiles

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

        await _load_current_filter_data()

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
            hint_text="Pesquisar por número ou título...",
            prefix_icon=ft.Icons.SEARCH,
            on_change=_on_search_change,
            border_radius=12,
            expand=True,
            content_padding=ft.Padding.symmetric(vertical=12, horizontal=16),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        )

        async def _on_filter_select(e):
            selected = e.control.selected
            if "favoritos" in selected:
                self.current_filter = "favoritos"
            elif "recentes" in selected:
                self.current_filter = "recentes"
            else:
                self.current_filter = "todos"

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
            ],
            on_change=_on_filter_select,
            expand=True,
        )

        return ft.View(
            route="/",
            appbar=ft.AppBar(
                title=ft.Text("Hinário", weight=ft.FontWeight.BOLD),
                center_title=True,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                actions=[
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
            ],
        )
