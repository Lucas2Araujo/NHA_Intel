import asyncio
import json
import flet as ft
from typing import Optional, Dict, List
from src.repositories.hino_repository import HinoRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.repositories.biblia_repository import BibliaRepository
from src.services.media_service import MediaService
from src.models.hino import Hino
from src.models.biblia import PassagemBiblica

DEFAULT_FONT_FAMILY = "Padrão"
TIMES_NEW_ROMAN_FONT_FAMILY = "Times New Roman"
OPENDYSLEXIC_FONT_FAMILY = "OpenDyslexic"

FONT_FAMILY_MAP = {
    DEFAULT_FONT_FAMILY: None,
    TIMES_NEW_ROMAN_FONT_FAMILY: TIMES_NEW_ROMAN_FONT_FAMILY,
    OPENDYSLEXIC_FONT_FAMILY: OPENDYSLEXIC_FONT_FAMILY,
}



class HinoView:
    """
    View responsável por exibir assincronamente a letra e os detalhes de um hino específico.
    Oferece controles avançados de acessibilidade (tamanho e 3 famílias de fontes), favoritar,
    registro no histórico, metadados cruzados e atalho para o YouTube com link externo.
    Segue as diretrizes do Flet 0.85+.
    """

    def __init__(
        self,
        hino_id: int,
        hino_repository: HinoRepository,
        favorito_repository: FavoritoRepository,
        historico_repository: HistoricoRepository,
        media_service: Optional[MediaService] = None,
        hino_ids_list: Optional[List[int]] = None,
        biblia_repository: Optional[BibliaRepository] = None,
    ):
        self.hino_id = hino_id
        self.hino_repository = hino_repository
        self.favorito_repository = favorito_repository
        self.historico_repository = historico_repository
        self.media_service = media_service
        self.hino_ids_list = hino_ids_list or []
        self.biblia_repository = biblia_repository or BibliaRepository()

        # Estado interno de acessibilidade de fonte (carregado do banco se existir)
        self.font_size: int = 18
        self.selected_font: str = DEFAULT_FONT_FAMILY
        self.is_custom_font: bool = False
        self._prefs_loaded: bool = False
        self._save_pref_task: Optional[asyncio.Task] = None

        # Referências aos elementos dinâmicos da interface
        self.page: Optional[ft.Page] = None
        self.letra_text: Optional[ft.Text] = None
        self.font_size_text: Optional[ft.Text] = None
        self.fav_icon: Optional[ft.IconButton] = None
        self.youtube_btn: Optional[ft.IconButton] = None
        self.is_fav: bool = False
        self.relacionados: Dict[str, List[str]] = {"temas": [], "textos_biblicos": []}

        # SnackBar singleton reutilizável (evita acúmulo no overlay)
        self._snackbar: Optional[ft.SnackBar] = None

    def _calculate_responsive_font_size(self, page: ft.Page) -> int:
        """Calcula o tamanho de fonte responsivo padrão proporcional à altura útil da tela."""
        if not page or not page.height:
            return 18
        h = float(page.height)
        return int(max(18, min(36, h * 0.026)))

    def _show_snackbar(self, page: ft.Page, msg: str) -> None:
        """Exibe um SnackBar reutilizável, evitando acúmulo no overlay."""
        if self._snackbar is None:
            self._snackbar = ft.SnackBar(content=ft.Text(msg))
            page.overlay.append(self._snackbar)
        else:
            self._snackbar.content = ft.Text(msg)
        self._snackbar.open = True
        page.update()

    async def _load_preferences(self) -> None:
        """Carrega preferências de fonte do banco de dados (uma vez)."""
        if self._prefs_loaded:
            return
        try:
            conn = await self.hino_repository.db_connection.get_connection()
            async with conn.execute(
                "SELECT valor FROM preferencias WHERE chave = ?", ("font_prefs",)
            ) as cursor:
                row = await cursor.fetchone()
            if row and row[0]:
                prefs = json.loads(row[0])
                if "font_size" in prefs:
                    self.font_size = prefs.get("font_size", 18)
                    self.is_custom_font = prefs.get("is_custom", True)
                self.selected_font = prefs.get("font_family", DEFAULT_FONT_FAMILY)
        except Exception:
            pass
        self._prefs_loaded = True

    async def _save_preferences(self) -> None:
        """Salva preferências de fonte no banco de dados."""
        try:
            prefs = json.dumps({
                "font_size": self.font_size,
                "font_family": self.selected_font,
                "is_custom": self.is_custom_font,
            })
            conn = await self.hino_repository.db_connection.get_connection()
            await conn.execute(
                "INSERT OR REPLACE INTO preferencias (chave, valor) VALUES (?, ?)",
                ("font_prefs", prefs),
            )
            await conn.commit()
        except Exception:
            pass

    def _on_page_resize(self, e):
        """Redimensiona o tamanho da fonte dinamicamente se a janela mudar de tamanho (caso o usuário não tenha travado um tamanho customizado)."""
        if not self.is_custom_font and self.page:
            self.font_size = self._calculate_responsive_font_size(self.page)
            self._update_font(self.page)

    async def build(self, page: ft.Page) -> ft.View:
        self.page = page
        self.page.on_resize = self._on_page_resize

        hino: Optional[Hino] = await self.hino_repository.get_by_id(self.hino_id)

        if hino is None:
            return self._build_not_found_view(page)

        # Carrega preferências de fonte persistidas
        await self._load_preferences()

        if not self.is_custom_font:
            self.font_size = self._calculate_responsive_font_size(page)

        # Executa queries em paralelo para reduzir latência de abertura
        historico_task = self.historico_repository.add_acesso(self.hino_id)
        metadados_task = self.hino_repository.get_metadados_relacionados(self.hino_id)
        favorito_task = self.favorito_repository.is_favorito(self.hino_id)

        _, self.relacionados, self.is_fav = await asyncio.gather(
            historico_task, metadados_task, favorito_task
        )

        # Texto da letra do hino
        self.letra_text = ft.Text(
            hino.letra if hino.letra else "Letra não disponível para este hino.",
            size=self.font_size,
            text_align=ft.TextAlign.CENTER,
            weight=ft.FontWeight.W_400,
            font_family=FONT_FAMILY_MAP.get(self.selected_font),
            expand=True,
        )

        # Toggle de Favorito
        self.fav_icon = ft.IconButton(
            icon=ft.Icons.FAVORITE if self.is_fav else ft.Icons.FAVORITE_BORDER,
            icon_color=ft.Colors.RED_400 if self.is_fav else None,
            tooltip="Desfavoritar" if self.is_fav else "Favoritar",
            on_click=lambda e: page.run_task(self._toggle_favorito, page, hino),
        )

        # Botão de Link Externo do YouTube
        has_youtube = bool(hino.link_video and hino.link_video.strip())
        self.youtube_btn = ft.IconButton(
            icon=ft.Icons.PLAY_CIRCLE_OUTLINE if hasattr(ft.Icons, "PLAY_CIRCLE_OUTLINE") else ft.Icons.PLAY_ARROW,
            icon_color=ft.Colors.RED_400 if has_youtube else None,
            tooltip="Assistir no YouTube (Link Externo)" if has_youtube else "Link do YouTube indisponível",
            disabled=not has_youtube,
            on_click=lambda e: page.run_task(self._open_youtube_link, page, hino),
        )

        # Navegação anterior/próximo
        prev_btn, next_btn = self._build_nav_buttons(page)

        # Botão voltar usa stack de views
        async def _go_back(e):
            if len(page.views) > 1:
                page.views.pop()
                top_view = page.views[-1]
                await page.push_route(top_view.route)
            else:
                await page.push_route("/")

        return ft.View(
            route=f"/hino/{self.hino_id}",
            appbar=ft.AppBar(
                leading=ft.IconButton(
                    ft.Icons.ARROW_BACK,
                    on_click=_go_back,
                ),
                title=ft.Text(f"Hino {hino.numero}", weight=ft.FontWeight.BOLD),
                center_title=True,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                actions=[
                    prev_btn,
                    next_btn,
                    self.fav_icon,
                    ft.IconButton(
                        ft.Icons.INFO_OUTLINED,
                        tooltip="Informações do Hino",
                        on_click=lambda e: self._show_info_modal(page, hino),
                    ),
                ],
            ),
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                content=ft.Column(
                                    controls=[
                                        ft.Text(
                                            hino.titulo,
                                            size=22,
                                            weight=ft.FontWeight.BOLD,
                                            text_align=ft.TextAlign.CENTER,
                                            color=ft.Colors.BLUE_200,
                                        ),
                                        *(
                                            [
                                                ft.Container(
                                                    content=ft.Chip(
                                                        label=ft.Text(hino.texto_base, size=12),
                                                        leading=ft.Icon(
                                                            ft.Icons.MENU_BOOK_OUTLINED,
                                                            size=15,
                                                            color=ft.Colors.GREEN_400,
                                                        ),
                                                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                                                        tooltip="Ler texto bíblico",
                                                        on_click=lambda e, ref=hino.texto_base: page.run_task(
                                                            self._abrir_modal_leitura_biblica, page, ref
                                                        ),
                                                    ),
                                                    padding=ft.Padding.only(top=4),
                                                )
                                            ]
                                            if hino.texto_base and hino.texto_base.strip()
                                            else []
                                        ),
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=2,
                                ),
                                padding=ft.Padding.symmetric(vertical=15, horizontal=20),
                                alignment=ft.Alignment.CENTER,
                            ),
                            ft.Divider(height=1),
                            ft.Container(
                                content=self.letra_text,
                                padding=ft.Padding.symmetric(vertical=20, horizontal=20),
                                alignment=ft.Alignment.TOP_CENTER,
                                expand=True,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                    expand=True,
                    padding=0,
                ),
            ],
            bottom_appbar=ft.BottomAppBar(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.IconButton(
                                    ft.Icons.TEXT_FIELDS,
                                    tooltip="Tamanho e Família de Fonte",
                                    on_click=lambda e: self._show_accessibility_modal(page),
                                ),
                                ft.Text("Fonte", size=10, text_align=ft.TextAlign.CENTER),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=0,
                        ),
                        ft.Column(
                            controls=[
                                self.youtube_btn,
                                ft.Text("YouTube", size=10, text_align=ft.TextAlign.CENTER),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=0,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_AROUND,
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            ),
        )

    def _build_nav_buttons(self, page: ft.Page) -> tuple:
        """Constrói botões de navegação anterior/próximo baseados na lista de IDs."""
        current_idx = -1
        if self.hino_ids_list and self.hino_id in self.hino_ids_list:
            current_idx = self.hino_ids_list.index(self.hino_id)

        has_prev = current_idx > 0
        has_next = current_idx >= 0 and current_idx < len(self.hino_ids_list) - 1

        async def _go_prev(e):
            if has_prev:
                prev_id = self.hino_ids_list[current_idx - 1]
                await page.push_route(f"/hino/{prev_id}")

        async def _go_next(e):
            if has_next:
                next_id = self.hino_ids_list[current_idx + 1]
                await page.push_route(f"/hino/{next_id}")

        prev_btn = ft.IconButton(
            ft.Icons.NAVIGATE_BEFORE,
            tooltip="Hino Anterior",
            on_click=_go_prev,
            disabled=not has_prev,
        )
        next_btn = ft.IconButton(
            ft.Icons.NAVIGATE_NEXT,
            tooltip="Próximo Hino",
            on_click=_go_next,
            disabled=not has_next,
        )

        return prev_btn, next_btn

    def _build_not_found_view(self, page: ft.Page) -> ft.View:
        async def _go_back(e):
            if len(page.views) > 1:
                page.views.pop()
                top_view = page.views[-1]
                await page.push_route(top_view.route)
            else:
                await page.push_route("/")

        return ft.View(
            route=f"/hino/{self.hino_id}",
            appbar=ft.AppBar(
                leading=ft.IconButton(
                    ft.Icons.ARROW_BACK,
                    on_click=_go_back,
                ),
                title=ft.Text("Hino não encontrado"),
            ),
            controls=[
                ft.Container(
                    content=ft.Text("O hino solicitado não foi encontrado."),
                    alignment=ft.Alignment.CENTER,
                    expand=True,
                )
            ],
        )

    def _update_font(self, page: ft.Page) -> None:
        if self.letra_text:
            self.letra_text.size = self.font_size
            self.letra_text.font_family = FONT_FAMILY_MAP.get(self.selected_font)
        if self.font_size_text:
            self.font_size_text.value = f"{self.font_size}pt"
        if page:
            page.update()
        # Persiste preferências de forma assíncrona (fire-and-forget)
        self._save_pref_task = asyncio.create_task(self._save_preferences())

    def _increase_font(self, page: ft.Page) -> None:
        if self.font_size < 36:
            self.font_size += 2
            self.is_custom_font = True
            self._update_font(page)

    def _decrease_font(self, page: ft.Page) -> None:
        if self.font_size > 12:
            self.font_size -= 2
            self.is_custom_font = True
            self._update_font(page)

    def _reset_font(self, page: ft.Page) -> None:
        self.font_size = self._calculate_responsive_font_size(page)
        self.selected_font = DEFAULT_FONT_FAMILY
        self.is_custom_font = False
        self._update_font(page)

    def _set_font_family(self, page: ft.Page, font_family: str) -> None:
        self.selected_font = font_family
        self._update_font(page)

    def _update_fav_icon_state(self) -> None:
        if self.fav_icon:
            self.fav_icon.icon = ft.Icons.FAVORITE if self.is_fav else ft.Icons.FAVORITE_BORDER
            self.fav_icon.icon_color = ft.Colors.RED_400 if self.is_fav else None
            self.fav_icon.tooltip = "Desfavoritar" if self.is_fav else "Favoritar"

    async def _toggle_favorito(self, page: ft.Page, hino: Hino) -> None:
        if self.is_fav:
            await self.favorito_repository.remove_favorito(self.hino_id)
            self.is_fav = False
            msg = f"Hino {hino.numero} removido dos favoritos"
        else:
            await self.favorito_repository.add_favorito(self.hino_id)
            self.is_fav = True
            msg = f"Hino {hino.numero} adicionado aos favoritos!"

        self._update_fav_icon_state()
        self._show_snackbar(page, msg)

    async def _open_youtube_link(self, page: ft.Page, hino: Hino) -> None:
        """Abre o link externo do YouTube no navegador ou app nativo."""
        if not hino.link_video or not hino.link_video.strip():
            self._show_snackbar(page, "Este hino não possui link do YouTube cadastrado.")
            return

        url = hino.link_video.strip()
        try:
            await ft.UrlLauncher().launch_url(url)
        except Exception:
            try:
                await page.launch_url(url)
            except Exception:
                self._show_snackbar(page, "Não foi possível abrir o link do YouTube.")


    def _show_accessibility_modal(self, page: ft.Page) -> None:
        self.font_size_text = ft.Text(f"{self.font_size}pt", weight=ft.FontWeight.BOLD)

        font_radio_group = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value=DEFAULT_FONT_FAMILY, label=f"{DEFAULT_FONT_FAMILY} (Sans-Serif)"),
                    ft.Radio(
                        value=TIMES_NEW_ROMAN_FONT_FAMILY,
                        label=f"Serifada ({TIMES_NEW_ROMAN_FONT_FAMILY})",
                    ),
                    ft.Radio(
                        value=OPENDYSLEXIC_FONT_FAMILY,
                        label=f"{OPENDYSLEXIC_FONT_FAMILY} (Acessível)",
                    ),
                ],
                spacing=8,
            ),
            value=self.selected_font,
            on_change=lambda e: self._set_font_family(page, e.control.value),
        )

        bs = ft.BottomSheet(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text("Acessibilidade de Fonte", weight=ft.FontWeight.BOLD, size=18),
                                ft.IconButton(ft.Icons.CLOSE, on_click=lambda ev: page.pop_dialog()),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Divider(),
                        ft.Row(
                            controls=[
                                ft.Text("Tamanho da Letra:"),
                                ft.IconButton(
                                    ft.Icons.REMOVE_CIRCLE_OUTLINE,
                                    on_click=lambda e: self._decrease_font(page),
                                    tooltip="Diminuir",
                                ),
                                self.font_size_text,
                                ft.IconButton(
                                    ft.Icons.ADD_CIRCLE_OUTLINE,
                                    on_click=lambda e: self._increase_font(page),
                                    tooltip="Aumentar",
                                ),
                                ft.TextButton("Resetar", on_click=lambda e: self._reset_font(page)),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            wrap=True,
                            spacing=6,
                            run_spacing=6,
                        ),
                        ft.Divider(),
                        ft.Text("Família de Fonte:", weight=ft.FontWeight.BOLD, size=14),
                        font_radio_group,
                    ],
                    tight=True,
                    spacing=12,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=ft.Padding.all(20),
            )
        )
        page.show_dialog(bs)



    def _on_biblia_click(self, page: ft.Page, ref: str) -> None:
        """Fecha o modal de informações e abre o modal de leitura bíblica."""
        page.pop_dialog()
        page.run_task(self._abrir_modal_leitura_biblica, page, ref)

    async def _abrir_modal_leitura_biblica(self, page: ft.Page, referencia: str) -> None:
        """
        Abre um modal responsivo e assíncrono (BottomSheet) para leitura da passagem bíblica informada.
        Exibe indicador de carregamento e depois os versículos formatados ou mensagem amigável de erro.
        """
        if not referencia or not referencia.strip():
            self._show_snackbar(page, "Referência bíblica inválida.")
            return

        ref_clean = referencia.strip()

        title_text = ft.Text(
            ref_clean,
            weight=ft.FontWeight.BOLD,
            size=18,
            color=ft.Colors.GREEN_200,
            expand=True,
        )

        loading_indicator = ft.Container(
            content=ft.Column(
                controls=[
                    ft.ProgressRing(width=36, height=36, stroke_width=3),
                    ft.Text("Carregando passagem bíblica...", size=14, color=ft.Colors.GREY_400),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12,
            ),
            padding=ft.Padding.symmetric(vertical=40),
            alignment=ft.Alignment.CENTER,
        )

        verses_container = ft.Column(
            controls=[loading_indicator],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=10,
        )

        modal_body = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.MENU_BOOK, color=ft.Colors.GREEN_400, size=22),
                            title_text,
                            ft.IconButton(ft.Icons.CLOSE, on_click=lambda ev: page.pop_dialog()),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Divider(height=1),
                    ft.Container(
                        content=verses_container,
                        expand=True,
                        padding=ft.Padding.symmetric(vertical=8),
                    ),
                    ft.Divider(height=1),
                    ft.Row(
                        controls=[
                            ft.TextButton(
                                "Fechar",
                                icon=ft.Icons.CLOSE,
                                on_click=lambda ev: page.pop_dialog(),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                spacing=8,
                expand=True,
            ),
            padding=ft.Padding.all(20),
            height=min(page.height * 0.75, 550) if page and page.height else 450,
        )

        bs = ft.BottomSheet(
            content=modal_body,
        )
        page.show_dialog(bs)

        # Consulta assíncrona da passagem bíblica
        try:
            passagem: Optional[PassagemBiblica] = await self.biblia_repository.buscar_passagem(ref_clean)
        except Exception:
            passagem = None

        if passagem and passagem.versiculos:
            title_text.value = passagem.referencia

            verse_controls: list[ft.Control] = []
            for v in passagem.versiculos:
                verse_controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(
                                    content=ft.Text(
                                        str(v.versiculo),
                                        weight=ft.FontWeight.BOLD,
                                        size=13,
                                        color=ft.Colors.GREEN_400,
                                    ),
                                    alignment=ft.Alignment.TOP_RIGHT,
                                    width=28,
                                    padding=ft.Padding.only(top=2),
                                ),
                                ft.Text(
                                    v.texto,
                                    size=15,
                                    selectable=True,
                                    expand=True,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.START,
                            spacing=8,
                        ),
                        padding=ft.Padding.symmetric(vertical=3),
                    )
                )

            verses_container.controls = verse_controls
        else:
            verses_container.controls = [
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.AUTO_STORIES, size=48, color=ft.Colors.GREY_500),
                            ft.Text(
                                "Não foi possível carregar a passagem bíblica solicitada.",
                                size=15,
                                weight=ft.FontWeight.W_500,
                                text_align=ft.TextAlign.CENTER,
                                color=ft.Colors.GREY_400,
                            ),
                            ft.Text(
                                f"Referência: {ref_clean}",
                                size=12,
                                italic=True,
                                text_align=ft.TextAlign.CENTER,
                                color=ft.Colors.GREY_600,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=10,
                    ),
                    padding=ft.Padding.symmetric(vertical=30),
                    alignment=ft.Alignment.CENTER,
                )
            ]

        page.update()

    def _show_info_modal(self, page: ft.Page, hino: Hino) -> None:
        async def _navigate_search(term: str):
            """Fecha o modal e navega para Home com busca FTS pelo termo."""
            page.pop_dialog()
            await page.push_route(f"/?q={term}")

        info_items: list[ft.Control] = [
            ft.Row(
                controls=[
                    ft.Text("Informações do Hino", weight=ft.FontWeight.BOLD, size=18),
                    ft.IconButton(ft.Icons.CLOSE, on_click=lambda ev: page.pop_dialog()),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Divider(),
        ]

        metadata = []
        if hino.autor_letra and hino.autor_musica and hino.autor_letra == hino.autor_musica:
            metadata.append(("Letra e Música:", hino.autor_letra))
        else:
            if hino.autor_letra:
                metadata.append(("Autor da Letra:", hino.autor_letra))
            if hino.autor_musica:
                metadata.append(("Autor da Música:", hino.autor_musica))
            if not hino.autor_letra and not hino.autor_musica and hino.autores:
                metadata.append(("Autores:", hino.autores))

        for label, val in metadata:
            if val and val.strip():
                info_items.append(
                    ft.Column(
                        controls=[
                            ft.Text(label, weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.BLUE_200),
                            ft.Text(val, size=14),
                        ],
                        spacing=2,
                    )
                )

        # Texto Base Bíblico como chip clicável para leitura direta
        if hino.texto_base and hino.texto_base.strip():
            info_items.append(
                ft.Column(
                    controls=[
                        ft.Text("Texto Base Bíblico:", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.BLUE_200),
                        ft.Chip(
                            label=ft.Text(hino.texto_base, size=12),
                            leading=ft.Icon(ft.Icons.MENU_BOOK_OUTLINED, size=15, color=ft.Colors.GREEN_400),
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                            tooltip="Ler passagem bíblica",
                            on_click=lambda e, ref=hino.texto_base: self._on_biblia_click(page, ref),
                        ),
                    ],
                    spacing=4,
                )
            )

        # Categoria e Subcategoria como chips clicáveis
        cat_chips: list[ft.Control] = []
        if hino.categoria and hino.categoria.strip():
            cat_chips.append(
                ft.Chip(
                    label=ft.Text(hino.categoria, size=12),
                    leading=ft.Icon(ft.Icons.FOLDER_OUTLINED, size=16, color=ft.Colors.BLUE_400),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    on_click=lambda e, c=hino.categoria: asyncio.create_task(_navigate_search(c)),
                )
            )
        if hino.subcategoria and hino.subcategoria.strip():
            cat_chips.append(
                ft.Chip(
                    label=ft.Text(hino.subcategoria, size=12),
                    leading=ft.Icon(ft.Icons.FOLDER_SPECIAL_OUTLINED, size=16, color=ft.Colors.BLUE_300),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    on_click=lambda e, sc=hino.subcategoria: asyncio.create_task(_navigate_search(sc)),
                )
            )
        if cat_chips:
            info_items.append(
                ft.Column(
                    controls=[
                        ft.Text("Categoria:", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.BLUE_200),
                        ft.Row(controls=cat_chips, wrap=True, spacing=6, run_spacing=6),
                    ],
                    spacing=4,
                )
            )

        # Temas como chips clicáveis que filtram busca
        temas = self.relacionados.get("temas", [])
        if temas:
            tema_chips: list[ft.Control] = [
                ft.Chip(
                    label=ft.Text(t, size=11),
                    leading=ft.Icon(ft.Icons.LABEL_OUTLINED, size=15, color=ft.Colors.AMBER_400),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    on_click=lambda e, tema=t: asyncio.create_task(_navigate_search(tema)),
                )
                for t in temas
            ]
            info_items.append(
                ft.Column(
                    controls=[
                        ft.Text("Temas Relacionados:", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.AMBER_200),
                        ft.Row(controls=tema_chips, wrap=True, spacing=6, run_spacing=6),
                    ],
                    spacing=4,
                )
            )

        # Textos Bíblicos Relacionados como chips clicáveis para leitura bíblica
        textos_biblicos = self.relacionados.get("textos_biblicos", [])
        if textos_biblicos:
            texto_chips: list[ft.Control] = [
                ft.Chip(
                    label=ft.Text(tb, size=11),
                    leading=ft.Icon(ft.Icons.MENU_BOOK_OUTLINED, size=15, color=ft.Colors.GREEN_400),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    tooltip="Ler passagem bíblica",
                    on_click=lambda e, ref=tb: self._on_biblia_click(page, ref),
                )
                for tb in textos_biblicos
            ]
            info_items.append(
                ft.Column(
                    controls=[
                        ft.Text("Textos Bíblicos Relacionados:", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.GREEN_200),
                        ft.Row(controls=texto_chips, wrap=True, spacing=6, run_spacing=6),
                    ],
                    spacing=4,
                )
            )

        if len(info_items) == 2:
            info_items.append(ft.Text("Nenhum metadado adicional cadastrado para este hino.", italic=True))

        bs = ft.BottomSheet(
            content=ft.Container(
                content=ft.Column(
                    controls=info_items,
                    tight=True,
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=ft.Padding.all(20),
            )
        )
        page.show_dialog(bs)
