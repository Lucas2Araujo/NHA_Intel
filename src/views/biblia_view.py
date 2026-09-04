import asyncio
from typing import Any

import flet as ft

from src.models.biblia import PassagemBiblica
from src.repositories.biblia_repository import BibliaRepository
from src.services.theme_service import ThemeService


class BibliaView:
    """
    Tela completa e responsiva para leitura e navegação da Bíblia Sagrada.
    Permite alternar versões (ARA, NVI, etc.), selecionar livros do Antigo/Novo Testamento
    e capítulos através de um modal/BottomSheet intuitivo, além de navegação rápida
    entre capítulos anteriores e posteriores.
    """

    def __init__(
        self,
        biblia_repository: BibliaRepository,
        theme_service: ThemeService | None = None,
    ):
        self.biblia_repository = biblia_repository
        self.theme_service = theme_service

        # Estado da navegação da Bíblia
        self.current_book_id: int = 1  # Gênesis por padrão
        self.current_chapter: int = 1
        self.selected_version: str = self.biblia_repository.active_version or "ARA"
        self.total_chapters: int = 50

        # Cache de livros e metadados
        self.livros: list[dict[str, Any]] = []
        self.current_passagem: PassagemBiblica | None = None
        self.is_loading: bool = False

        # Configurações de exibição de texto
        self.font_size: int = 17

        # Referências de controles Flet
        self.page: ft.Page | None = None
        self.appbar_title_btn: ft.TextButton | None = None
        self.version_dropdown: ft.Dropdown | None = None
        self.prev_btn: ft.IconButton | None = None
        self.next_btn: ft.IconButton | None = None
        self.prev_chip_btn: ft.OutlinedButton | None = None
        self.next_chip_btn: ft.OutlinedButton | None = None
        self.verses_list: ft.ListView | None = None
        self.header_info_text: ft.Text | None = None

    def _get_accent_color(self) -> str:
        if self.theme_service:
            return self.theme_service.get_accent_color("novo")
        return ft.Colors.BLUE_400

    def _get_current_book_name(self) -> str:
        for b in self.livros:
            if b["id"] == self.current_book_id:
                return b["name"]
        return f"Livro {self.current_book_id}"

    async def _load_books(self) -> None:
        """Carrega a lista de livros se ainda não carregada."""
        if not self.livros:
            self.livros = await self.biblia_repository.listar_livros(
                versao=self.selected_version
            )

    async def _carregar_capitulo(
        self, book_id: int, chapter: int, versao: str | None = None
    ) -> None:
        """Carrega o capítulo do banco SQLite e atualiza a interface."""
        self.is_loading = True
        self.current_book_id = book_id
        self.current_chapter = chapter
        if versao:
            self.selected_version = versao.strip().upper()
            self.biblia_repository.set_version(self.selected_version)

        # Atualiza o total de capítulos do livro atual
        self.total_chapters = await self.biblia_repository.get_total_capitulos(
            self.current_book_id, versao=self.selected_version
        )
        if self.total_chapters <= 0:
            self.total_chapters = 1

        if self.current_chapter > self.total_chapters:
            self.current_chapter = self.total_chapters
        elif self.current_chapter < 1:
            self.current_chapter = 1

        if self.verses_list and self.page:
            self.verses_list.controls = [
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.ProgressRing(color=self._get_accent_color()),
                            ft.Text("Carregando versículos...", italic=True, size=14),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                    ),
                    padding=ft.Padding.symmetric(vertical=60),
                    alignment=ft.Alignment.CENTER,
                )
            ]
            self._update_appbar_and_nav_states()
            self.page.update()

        # Busca assíncrona do capítulo no repositório
        self.current_passagem = await self.biblia_repository.buscar_capitulo(
            self.current_book_id, self.current_chapter, versao=self.selected_version
        )

        self.is_loading = False
        self._render_verses()

    def _update_appbar_and_nav_states(self) -> None:
        """Atualiza rótulos do AppBar e estados dos botões de anterior/próximo."""
        book_name = self._get_current_book_name()
        title_label = f"{book_name} {self.current_chapter}"

        if self.appbar_title_btn:
            self.appbar_title_btn.content = title_label

        if self.header_info_text:
            self.header_info_text.value = f"{title_label} ({self.selected_version})"

        # Navegação de Anterior
        has_prev = not (self.current_book_id == 1 and self.current_chapter == 1)
        if self.prev_btn:
            self.prev_btn.disabled = not has_prev
        if self.prev_chip_btn:
            self.prev_chip_btn.disabled = not has_prev

        # Navegação de Próximo
        has_next = not (
            self.current_book_id == 66 and self.current_chapter >= self.total_chapters
        )
        if self.next_btn:
            self.next_btn.disabled = not has_next
        if self.next_chip_btn:
            self.next_chip_btn.disabled = not has_next

    def _render_verses(self) -> None:
        """Renderiza os versículos na ListView."""
        if not self.verses_list or not self.page:
            return

        self._update_appbar_and_nav_states()

        if not self.current_passagem or not self.current_passagem.versiculos:
            self.verses_list.controls = [
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(
                                ft.Icons.ERROR_OUTLINE,
                                size=42,
                                color=ft.Colors.RED_400,
                            ),
                            ft.Text(
                                "Nenhum versículo encontrado para este capítulo.",
                                size=15,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                f"{self._get_current_book_name()} {self.current_chapter} ({self.selected_version})",
                                size=13,
                                color=ft.Colors.GREY_400,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    padding=ft.Padding.symmetric(vertical=60),
                    alignment=ft.Alignment.CENTER,
                )
            ]
            self.page.update()
            return

        accent_color = self._get_accent_color()
        controls: list[ft.Control] = []

        # Cabeçalho decorativo do capítulo
        controls.append(
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            self._get_current_book_name().upper(),
                            size=13,
                            style=ft.TextStyle(letter_spacing=1.5),
                            weight=ft.FontWeight.BOLD,
                            color=accent_color,
                        ),
                        ft.Text(
                            f"Capítulo {self.current_chapter}",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Container(
                            content=ft.Text(
                                f"{len(self.current_passagem.versiculos)} versículos • {self.biblia_repository.get_version_name(self.selected_version)}",
                                size=11,
                                color=ft.Colors.GREY_400,
                            ),
                            padding=ft.Padding.only(bottom=8),
                        ),
                        ft.Divider(height=1),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=3,
                ),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.only(top=8, bottom=16),
            )
        )

        # Itens de versículo com número destacado
        for v in self.current_passagem.versiculos:
            controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text(
                                    str(v.numero),
                                    size=max(11, self.font_size - 4),
                                    weight=ft.FontWeight.BOLD,
                                    color=accent_color,
                                ),
                                width=32,
                                alignment=ft.Alignment.TOP_RIGHT,
                                padding=ft.Padding.only(top=3),
                            ),
                            ft.Text(
                                v.texto,
                                size=self.font_size,
                                selectable=True,
                                expand=True,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        spacing=10,
                    ),
                    padding=ft.Padding.symmetric(vertical=5, horizontal=4),
                    border_radius=8,
                )
            )

        # Rodapé de navegação rápida entre capítulos
        footer_nav = ft.Container(
            content=ft.Row(
                controls=[
                    self.prev_chip_btn,
                    ft.Text(
                        f"{self.current_chapter} / {self.total_chapters}",
                        size=12,
                        color=ft.Colors.GREY_400,
                        weight=ft.FontWeight.BOLD,
                    ),
                    self.next_chip_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.only(top=24, bottom=40),
        )
        controls.append(footer_nav)

        self.verses_list.controls = controls
        self.page.update()

    async def _navigate_prev_chapter(self, e=None) -> None:
        """Avança para o capítulo anterior (ou último capítulo do livro anterior)."""
        if self.current_chapter > 1:
            await self._carregar_capitulo(self.current_book_id, self.current_chapter - 1)
        elif self.current_book_id > 1:
            prev_book_id = self.current_book_id - 1
            prev_total = await self.biblia_repository.get_total_capitulos(
                prev_book_id, versao=self.selected_version
            )
            await self._carregar_capitulo(prev_book_id, prev_total)

    async def _navigate_next_chapter(self, e=None) -> None:
        """Avança para o próximo capítulo (ou primeiro capítulo do próximo livro)."""
        if self.current_chapter < self.total_chapters:
            await self._carregar_capitulo(self.current_book_id, self.current_chapter + 1)
        elif self.current_book_id < 66:
            await self._carregar_capitulo(self.current_book_id + 1, 1)

    def _show_selector_dialog(self, e=None) -> None:
        """Abre o BottomSheet/Modal de seleção de Livro e Capítulo."""
        if not self.page:
            return

        at_books = [b for b in self.livros if b.get("testament") == "AT"]
        nt_books = [b for b in self.livros if b.get("testament") == "NT"]

        # Componente que exibirá os botões de capítulos do livro selecionado no modal
        selected_modal_book = {"id": self.current_book_id, "name": self._get_current_book_name()}
        chapters_container = ft.Column(controls=[], spacing=8)
        content_switcher = ft.AnimatedSwitcher(
            content=ft.Container(),
            transition=ft.AnimatedSwitcherTransition.FADE,
            duration=200,
        )

        modal_title = ft.Text("Selecione o Livro", weight=ft.FontWeight.BOLD, size=18)
        back_to_books_btn = ft.IconButton(
            icon=ft.Icons.ARROW_BACK,
            visible=False,
            tooltip="Voltar aos livros",
        )

        def _render_chapters_view(book_id: int, book_name: str) -> None:
            selected_modal_book["id"] = book_id
            selected_modal_book["name"] = book_name
            modal_title.value = f"{book_name} • Escolha o Capítulo"
            back_to_books_btn.visible = True

            async def _load_and_show_chapters():
                total = await self.biblia_repository.get_total_capitulos(
                    book_id, versao=self.selected_version
                )
                chapter_buttons: list[ft.Control] = []
                for ch in range(1, total + 1):
                    is_current = (
                        book_id == self.current_book_id and ch == self.current_chapter
                    )
                    btn = ft.Container(
                        content=ft.Text(
                            str(ch),
                            weight=ft.FontWeight.BOLD if is_current else ft.FontWeight.NORMAL,
                            size=13,
                            color=ft.Colors.WHITE if is_current else None,
                        ),
                        bgcolor=(
                            self._get_accent_color()
                            if is_current
                            else ft.Colors.SURFACE_CONTAINER_HIGHEST
                        ),
                        border_radius=8,
                        alignment=ft.Alignment.CENTER,
                        ink=True,
                        height=42,
                        on_click=lambda ev, c=ch: _on_chapter_selected(c),
                    )
                    chapter_buttons.append(btn)

                grid = ft.GridView(
                    runs_count=5,
                    max_extent=56,
                    spacing=8,
                    run_spacing=8,
                    controls=chapter_buttons,
                    expand=True,
                )
                chapters_container.controls = [grid]
                content_switcher.content = chapters_container
                self.page.update()

            asyncio.create_task(_load_and_show_chapters())

        def _on_chapter_selected(ch: int) -> None:
            self.page.pop_dialog()
            asyncio.create_task(
                self._carregar_capitulo(
                    selected_modal_book["id"], ch, versao=self.selected_version
                )
            )

        def _show_books_list() -> ft.Control:
            back_to_books_btn.visible = False
            modal_title.value = "Selecione o Livro"

            def _build_book_list_view(book_subset: list[dict[str, Any]]) -> ft.ListView:
                items: list[ft.Control] = []
                for b in book_subset:
                    is_current = b["id"] == self.current_book_id
                    items.append(
                        ft.ListTile(
                            leading=ft.Icon(
                                ft.Icons.BOOKMARK if is_current else ft.Icons.BOOKMARK_BORDER,
                                color=self._get_accent_color() if is_current else ft.Colors.GREY_400,
                                size=20,
                            ),
                            title=ft.Text(
                                b["name"],
                                weight=ft.FontWeight.BOLD if is_current else ft.FontWeight.NORMAL,
                                color=self._get_accent_color() if is_current else None,
                                size=15,
                            ),
                            trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT, size=18, color=ft.Colors.GREY_400),
                            on_click=lambda ev, bid=b["id"], bname=b["name"]: _render_chapters_view(bid, bname),
                        )
                    )
                return ft.ListView(controls=items, spacing=2, expand=True)

            selected_testament = "AT" if self.current_book_id <= 39 else "NT"
            book_list_container = ft.Container(
                content=_build_book_list_view(at_books if selected_testament == "AT" else nt_books),
                expand=True,
            )

            def _on_testament_change(ev):
                val = list(ev.control.selected)[0]
                book_list_container.content = _build_book_list_view(at_books if val == "AT" else nt_books)
                self.page.update()

            testament_bar = ft.SegmentedButton(
                selected=[selected_testament],
                allow_empty_selection=False,
                show_selected_icon=False,
                segments=[
                    ft.Segment(value="AT", label=ft.Text("Antigo Testamento (39)", size=12)),
                    ft.Segment(value="NT", label=ft.Text("Novo Testamento (27)", size=12)),
                ],
                on_change=_on_testament_change,
            )

            return ft.Column(
                controls=[
                    ft.Container(content=testament_bar, padding=ft.Padding.only(bottom=8)),
                    book_list_container,
                ],
                spacing=4,
                expand=True,
            )

        back_to_books_btn.on_click = lambda ev: _switch_to_books()

        def _switch_to_books() -> None:
            content_switcher.content = _show_books_list()
            self.page.update()

        content_switcher.content = _show_books_list()

        bs = ft.BottomSheet(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Row(
                                    controls=[back_to_books_btn, modal_title],
                                    spacing=4,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    expand=True,
                                ),
                                ft.IconButton(
                                    ft.Icons.CLOSE,
                                    tooltip="Fechar",
                                    on_click=lambda ev: self.page.pop_dialog(),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Divider(height=1),
                        ft.Container(content=content_switcher, expand=True),
                    ],
                    spacing=8,
                    expand=True,
                ),
                padding=ft.Padding.only(left=16, top=16, right=16, bottom=30),
                height=min(self.page.height * 0.85, 580) if self.page.height else 520,
            )
        )
        self.page.show_dialog(bs)

    async def _on_version_changed(self, e) -> None:
        """Manipula a troca de versão da Bíblia."""
        nova_versao = e.control.value
        if not nova_versao or nova_versao == self.selected_version:
            return
        self.selected_version = nova_versao.strip().upper()
        self.biblia_repository.set_version(self.selected_version)
        # Recarrega a lista de livros para os nomes da nova versão (se aplicável)
        self.livros = await self.biblia_repository.listar_livros(
            versao=self.selected_version
        )
        await self._carregar_capitulo(
            self.current_book_id, self.current_chapter, versao=self.selected_version
        )

    def _zoom_in(self, e=None) -> None:
        if self.font_size < 30:
            self.font_size += 2
            self._render_verses()

    def _zoom_out(self, e=None) -> None:
        if self.font_size > 12:
            self.font_size -= 2
            self._render_verses()

    async def build(
        self,
        page: ft.Page,
        initial_book_id: int = 1,
        initial_chapter: int = 1,
        initial_version: str | None = None,
    ) -> ft.View:
        self.page = page

        if self.theme_service:
            self.theme_service.apply_theme(page, edition="novo")

        if initial_version:
            self.selected_version = initial_version.strip().upper()
            self.biblia_repository.set_version(self.selected_version)

        self.current_book_id = initial_book_id
        self.current_chapter = initial_chapter

        # Carrega os livros da Bíblia
        await self._load_books()

        # Botão central com o Livro e Capítulo no AppBar
        self.appbar_title_btn = ft.TextButton(
            f"{self._get_current_book_name()} {self.current_chapter}",
            icon=ft.Icons.KEYBOARD_ARROW_DOWN,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE if self.theme_service and self.theme_service.is_amoled else None,
                text_style=ft.TextStyle(size=16, weight=ft.FontWeight.BOLD),
            ),
            tooltip="Selecionar Livro e Capítulo",
            on_click=self._show_selector_dialog,
        )

        versoes_disponiveis = self.biblia_repository.get_available_versions()
        self.version_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option(key=v, text=v) for v in versoes_disponiveis],
            value=self.selected_version,
            width=90,
            height=36,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=2),
            dense=True,
            border_radius=8,
            tooltip="Versão da Bíblia",
            on_select=self._on_version_changed,
        )

        self.prev_btn = ft.IconButton(
            ft.Icons.CHEVRON_LEFT,
            tooltip="Capítulo Anterior",
            on_click=self._navigate_prev_chapter,
        )
        self.next_btn = ft.IconButton(
            ft.Icons.CHEVRON_RIGHT,
            tooltip="Próximo Capítulo",
            on_click=self._navigate_next_chapter,
        )

        self.prev_chip_btn = ft.OutlinedButton(
            "Anterior",
            icon=ft.Icons.NAVIGATE_BEFORE,
            on_click=self._navigate_prev_chapter,
        )
        self.next_chip_btn = ft.OutlinedButton(
            "Próximo",
            icon=ft.Icons.NAVIGATE_NEXT,
            on_click=self._navigate_next_chapter,
        )

        self.header_info_text = ft.Text(
            f"{self._get_current_book_name()} {self.current_chapter} ({self.selected_version})",
            size=12,
            color=ft.Colors.GREY_400,
        )

        self.verses_list = ft.ListView(
            controls=[],
            expand=True,
            spacing=2,
            padding=ft.Padding.symmetric(horizontal=16, vertical=8),
        )

        # Inicia o carregamento assíncrono do capítulo inicial
        asyncio.create_task(
            self._carregar_capitulo(
                self.current_book_id, self.current_chapter, versao=self.selected_version
            )
        )

        return ft.View(
            route="/biblia",
            bgcolor=ft.Colors.SURFACE,
            appbar=ft.AppBar(
                leading=ft.IconButton(
                    ft.Icons.ARROW_BACK,
                    tooltip="Voltar",
                    on_click=lambda e: asyncio.create_task(page.push_route("/")),
                ),
                title=self.appbar_title_btn,
                center_title=True,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                actions=[
                    self.prev_btn,
                    self.next_btn,
                    self.version_dropdown,
                    ft.PopupMenuButton(
                        icon=ft.Icons.MORE_VERT,
                        tooltip="Opções de Leitura",
                        items=[
                            ft.PopupMenuItem(
                                "Aumentar Fonte (+)",
                                icon=ft.Icons.TEXT_INCREASE,
                                on_click=self._zoom_in,
                            ),
                            ft.PopupMenuItem(
                                "Diminuir Fonte (-)",
                                icon=ft.Icons.TEXT_DECREASE,
                                on_click=self._zoom_out,
                            ),
                            ft.PopupMenuItem(
                                "Selecionar Livro / Capítulo",
                                icon=ft.Icons.MENU_BOOK,
                                on_click=self._show_selector_dialog,
                            ),
                        ],
                    ),
                ],
            ),
            controls=[
                ft.SafeArea(
                    maintain_bottom_view_padding=True,
                    content=self.verses_list,
                    expand=True,
                )
            ],
        )
