import asyncio
import json
import flet as ft
from typing import Optional, Dict, List
from src.repositories.hino_repository import HinoRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.repositories.biblia_repository import BibliaRepository
from src.repositories.comparativo_repository import ComparativoRepository
from src.models.biblia import PassagemBiblica
from src.models.hino import Hino
from src.models.comparativo import HinoComparativo, BlocoDiff, EstatisticasDiff
from src.services.media_service import MediaService

DEFAULT_FONT_FAMILY = "Padrão"
TIMES_NEW_ROMAN_FONT_FAMILY = "Times New Roman"
OPENDYSLEXIC_FONT_FAMILY = "OpenDyslexic"

FONT_FAMILY_MAP = {
    DEFAULT_FONT_FAMILY: None,
    TIMES_NEW_ROMAN_FONT_FAMILY: TIMES_NEW_ROMAN_FONT_FAMILY,
    OPENDYSLEXIC_FONT_FAMILY: OPENDYSLEXIC_FONT_FAMILY,
}

TOOLTIP_LER_PASSAGEM_BIBLICA = "Ler passagem bíblica"



class HinoView:
    """
    View responsável por exibir assincronamente a letra e os detalhes de um hino específico.
    Oferece controles avançados de acessibilidade (tamanho e 3 famílias de fontes), favoritar,
    registro no histórico, metadados cruzados, comparação antes e depois (Hinário Antigo)
    e atalho para o YouTube com link externo.
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
        comparativo_repository: Optional[ComparativoRepository] = None,
        antigo_repository: Optional[HinoRepository] = None,
    ):
        self.hino_id = hino_id
        self.hino_repository = hino_repository
        self.favorito_repository = favorito_repository
        self.historico_repository = historico_repository
        self.media_service = media_service
        self.hino_ids_list = hino_ids_list or []
        self.biblia_repository = biblia_repository or BibliaRepository()
        self.comparativo_repository = comparativo_repository
        self.antigo_repository = antigo_repository

        # Estado da visualização comparativa (Hinário Novo vs Antigo)
        self.comparativo: Optional[HinoComparativo] = None
        self.hino_antigo: Optional[Hino] = None
        self.selected_view_mode: str = "novo"  # "novo", "antigo", "comparacao"
        self.content_container: Optional[ft.Container] = None
        self.segmented_button: Optional[ft.SegmentedButton] = None

        # Estado interno de acessibilidade de fonte (carregado do banco se existir)
        self.font_size: int = 18
        self.selected_font: str = DEFAULT_FONT_FAMILY
        self.is_custom_font: bool = False
        self._prefs_loaded: bool = False
        self._save_pref_task: Optional[asyncio.Task] = None
        self._biblia_task: Optional[asyncio.Task] = None
        self._nav_task: Optional[asyncio.Task] = None

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

        self.current_hino = hino

        # Carrega preferências de fonte persistidas
        await self._load_preferences()

        if not self.is_custom_font:
            self.font_size = self._calculate_responsive_font_size(page)

        # Executa queries em paralelo para reduzir latência de abertura
        historico_task = self.historico_repository.add_acesso(self.hino_id)
        metadados_task = self.hino_repository.get_metadados_relacionados(self.hino_id)
        favorito_task = self.favorito_repository.is_favorito(self.hino_id)
        comparativo_task = (
            self.comparativo_repository.get_by_numero_novo(hino.numero)
            if self.comparativo_repository
            else asyncio.sleep(0, result=None)
        )

        _, self.relacionados, self.is_fav, self.comparativo = await asyncio.gather(
            historico_task, metadados_task, favorito_task, comparativo_task
        )

        # Se houver número antigo e repositório antigo, carrega o hino antigo
        if self.comparativo and self.comparativo.numero_antigo and self.antigo_repository:
            try:
                self.hino_antigo = await self.antigo_repository.get_by_numero(self.comparativo.numero_antigo)
            except Exception:
                self.hino_antigo = None

        # Texto da letra do hino
        self.letra_text = ft.Text(
            hino.letra if hino.letra else "Letra não disponível para este hino.",
            size=self.font_size,
            text_align=ft.TextAlign.CENTER,
            weight=ft.FontWeight.W_400,
            font_family=FONT_FAMILY_MAP.get(self.selected_font),
            expand=True,
        )

        # Content container que alterna entre Letra Novo, Letra Antigo e Comparação
        self.content_container = ft.Container(
            content=self._render_current_mode_content(),
            padding=ft.Padding.symmetric(vertical=20, horizontal=20),
            alignment=ft.Alignment.TOP_CENTER,
            expand=True,
        )

        # Título do hino no corpo da página
        titulo_text = ft.Text(
            hino.titulo,
            size=22,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
            color=ft.Colors.BLUE_200,
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

        # Título na AppBar
        appbar_title = ft.Text(f"Hino {hino.numero}", weight=ft.FontWeight.BOLD)

        # Controles do Cabeçalho
        header_controls: list[ft.Control] = [titulo_text]
        if hino.texto_base and hino.texto_base.strip():
            header_controls.append(
                ft.Container(
                    content=ft.Chip(
                        label=ft.Text(hino.texto_base, size=12),
                        leading=ft.Icon(ft.Icons.MENU_BOOK_OUTLINED, size=15, color=ft.Colors.GREEN_400),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        tooltip=TOOLTIP_LER_PASSAGEM_BIBLICA,
                        on_click=lambda e, ref=hino.texto_base: self._on_biblia_click(
                            page, ref, from_info_modal=False, hino=hino
                        ),
                    ),
                    padding=ft.Padding.only(top=4),
                )
            )

        comparativo_chip = self._build_comparativo_chip(page)
        if comparativo_chip:
            header_controls.append(comparativo_chip)

        column_controls: list[ft.Control] = [
            ft.Container(
                content=ft.Column(
                    controls=header_controls,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2,
                ),
                padding=ft.Padding.symmetric(vertical=15, horizontal=20),
                alignment=ft.Alignment.CENTER,
            ),
        ]

        segmented_btn = self._build_segmented_button(page)
        if segmented_btn:
            column_controls.append(segmented_btn)

        column_controls.append(ft.Divider(height=1))
        column_controls.append(self.content_container)

        # Coluna rolável de conteúdo
        scroll_column = ft.Column(
            controls=column_controls,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

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
            bgcolor=ft.Colors.SURFACE,
            appbar=ft.AppBar(
                leading=ft.IconButton(
                    ft.Icons.ARROW_BACK,
                    on_click=_go_back,
                ),
                title=appbar_title,
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
                ft.SafeArea(
                    content=ft.Container(
                        content=scroll_column,
                        expand=True,
                        padding=0,
                    ),
                    expand=True,
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

    def _on_biblia_click(
        self,
        page: ft.Page,
        ref: str,
        from_info_modal: bool = False,
        hino: Optional[Hino] = None,
    ) -> None:
        """Manipula o clique em um chip bíblico, fechando modal aberto se houver e abrindo a leitura."""
        try:
            page.pop_dialog()
        except Exception:
            pass
        if hasattr(page, "run_task"):
            page.run_task(
                self._abrir_modal_leitura_biblica,
                page,
                ref,
                from_info_modal,
                hino,
            )
        else:
            if self._biblia_task and not self._biblia_task.done():
                self._biblia_task.cancel()
            self._biblia_task = asyncio.create_task(
                self._abrir_modal_leitura_biblica(
                    page,
                    ref,
                    from_info_modal=from_info_modal,
                    hino=hino,
                )
            )

    async def _abrir_modal_leitura_biblica(
        self,
        page: ft.Page,
        referencia: str,
        from_info_modal: bool = False,
        hino: Optional[Hino] = None,
    ) -> None:
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

        def _close_dialog(ev):
            page.pop_dialog()
            if from_info_modal:
                self._show_info_modal(page, hino)

        button_label = "Voltar para Informações" if from_info_modal else "Fechar"
        button_icon = ft.Icons.ARROW_BACK if from_info_modal else ft.Icons.CLOSE

        modal_body = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.MENU_BOOK, color=ft.Colors.GREEN_400, size=22),
                            title_text,
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
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
                                button_label,
                                icon=button_icon,
                                on_click=_close_dialog,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                spacing=8,
                expand=True,
            ),
            padding=ft.Padding.only(left=20, top=20, right=20, bottom=40),
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
        if self.content_container:
            self.content_container.content = self._render_current_mode_content()
        if page:
            page.update()
        # Persiste preferências de forma assíncrona (fire-and-forget)
        self._save_pref_task = asyncio.create_task(self._save_preferences())

    def _build_comparativo_chip(self, page: ft.Page) -> Optional[ft.Control]:
        """Gera o Chip/Badge informativo de status em relação ao Hinário Antigo."""
        if not self.comparativo:
            return None

        status = self.comparativo.status_comparacao
        num_antigo = self.comparativo.numero_antigo

        if status == "IDENTICO":
            return ft.Container(
                content=ft.Chip(
                    label=ft.Text(f"Hino Antigo #{num_antigo} (Letra Idêntica)", size=12),
                    leading=ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=15, color=ft.Colors.GREEN_400),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    tooltip="Letra idêntica ao Hinário Antigo. Clique para alternar.",
                    on_click=lambda e: self._on_chip_comparativo_click(page),
                ),
                padding=ft.Padding.only(top=4),
            )
        elif status == "MODIFICADO":
            resumo = self.comparativo.resumo_alteracoes or "Letra Modificada"
            return ft.Container(
                content=ft.Chip(
                    label=ft.Text(f"Hino Antigo #{num_antigo} ({resumo})", size=12, weight=ft.FontWeight.W_500),
                    leading=ft.Icon(ft.Icons.CHANGE_CIRCLE, size=15, color=ft.Colors.AMBER_400),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    tooltip="Letra modificada em relação ao Hinário Antigo. Clique para ver alterações.",
                    on_click=lambda e: self._on_chip_comparativo_click(page),
                ),
                padding=ft.Padding.only(top=4),
            )
        elif status == "NOVO_INEDITO":
            return ft.Container(
                content=ft.Chip(
                    label=ft.Text("Inédito no Novo Hinário", size=12),
                    leading=ft.Icon(ft.Icons.AUTO_AWESOME, size=15, color=ft.Colors.PURPLE_300),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    tooltip="Este hino foi adicionado exclusivamente na nova edição.",
                ),
                padding=ft.Padding.only(top=4),
            )
        return None

    def _on_chip_comparativo_click(self, page: ft.Page) -> None:
        """Manipula o clique no chip comparativo alternando o modo de visualização."""
        if not self.comparativo:
            return
        if self.comparativo.status_comparacao == "MODIFICADO":
            self.selected_view_mode = "comparacao"
        elif self.comparativo.numero_antigo:
            if self.selected_view_mode == "antigo":
                self.selected_view_mode = "novo"
            else:
                self.selected_view_mode = "antigo"

        if self.segmented_button:
            self.segmented_button.selected = [self.selected_view_mode]
        self._update_content_view(page)

    def _build_segmented_button(self, page: ft.Page) -> Optional[ft.Control]:
        """Gera a barra de alternância (SegmentedButton) entre Novo, Antigo e Comparação."""
        if not self.comparativo or not (self.comparativo.numero_antigo or self.comparativo.status_comparacao == "MODIFICADO"):
            return None

        segments = [
            ft.Segment(
                value="novo",
                label=ft.Text("Novo Hinário", size=12),
                icon=ft.Icon(ft.Icons.MUSIC_NOTE, size=15),
            )
        ]

        if self.comparativo.numero_antigo:
            segments.append(
                ft.Segment(
                    value="antigo",
                    label=ft.Text(f"Antigo #{self.comparativo.numero_antigo}", size=12),
                    icon=ft.Icon(ft.Icons.HISTORY_EDU, size=15),
                )
            )

        if self.comparativo.status_comparacao == "MODIFICADO":
            segments.append(
                ft.Segment(
                    value="comparacao",
                    label=ft.Text("Comparar Mudanças", size=12),
                    icon=ft.Icon(ft.Icons.COMPARE_ARROWS, size=15),
                )
            )

        self.segmented_button = ft.SegmentedButton(
            segments=segments,
            selected=[self.selected_view_mode],
            on_change=lambda e: self._on_segment_change(page, e.control.selected),
            show_selected_icon=False,
        )

        return ft.Container(
            content=self.segmented_button,
            padding=ft.Padding.symmetric(vertical=6, horizontal=10),
            alignment=ft.Alignment.CENTER,
        )

    def _on_segment_change(self, page: ft.Page, selected) -> None:
        """Trata a seleção de abas no SegmentedButton."""
        if selected:
            self.selected_view_mode = next(iter(selected))
            if self.segmented_button:
                self.segmented_button.selected = [self.selected_view_mode]
            self._update_content_view(page)

    def _render_current_mode_content(self) -> ft.Control:
        """Retorna o controle de conteúdo de acordo com o modo ativo."""
        if self.selected_view_mode == "antigo":
            return self._build_antigo_content()
        elif self.selected_view_mode == "comparacao":
            return self._build_comparacao_content()
        return self.letra_text or ft.Text("")

    def _update_content_view(self, page: Optional[ft.Page]) -> None:
        """Atualiza o conteúdo dinâmico da letra/comparação."""
        if self.content_container:
            self.content_container.content = self._render_current_mode_content()
        if page:
            page.update()

    def _build_antigo_content(self) -> ft.Control:
        """Gera a visualização da letra do Hinário Antigo."""
        if not self.hino_antigo and self.comparativo and self.comparativo.numero_antigo:
            letra_antiga = "Letra do hinário antigo não disponível no banco local."
            titulo_antigo = self.comparativo.titulo_antigo or "Hino Antigo"
            num_antigo = self.comparativo.numero_antigo
        elif self.hino_antigo:
            letra_antiga = self.hino_antigo.letra or "Letra não disponível."
            titulo_antigo = self.hino_antigo.titulo
            num_antigo = self.hino_antigo.numero
        else:
            return ft.Container(
                content=ft.Text(
                    "Hino antigo correspondente não encontrado.",
                    italic=True,
                    text_align=ft.TextAlign.CENTER,
                ),
                alignment=ft.Alignment.CENTER,
                padding=20,
            )

        font_fam = FONT_FAMILY_MAP.get(self.selected_font)
        return ft.Column(
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                f"Hino {num_antigo} - {titulo_antigo}",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                text_align=ft.TextAlign.CENTER,
                                color=ft.Colors.AMBER_200,
                            ),
                            ft.Text(
                                "Edição Anterior (Hinário Antigo)",
                                size=12,
                                italic=True,
                                text_align=ft.TextAlign.CENTER,
                                color=ft.Colors.GREY_400,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                    ),
                    padding=ft.Padding.only(bottom=10),
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Text(
                    letra_antiga,
                    size=self.font_size,
                    text_align=ft.TextAlign.CENTER,
                    weight=ft.FontWeight.W_400,
                    font_family=font_fam,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        )

    def _build_comparacao_content(self) -> ft.Control:
        """Gera a visualização diff Antes e Depois esteticamente adaptável e acessível."""
        if not self.comparativo:
            return ft.Text("Dados de comparação não disponíveis.", italic=True)

        stats, blocos = self.comparativo.get_parsed_diff()
        font_fam = FONT_FAMILY_MAP.get(self.selected_font)

        # 1. Painel de Resumo / Estatísticas
        simil_pct = self.comparativo.similaridade_pct
        summary_chips: list[ft.Control] = []

        if stats:
            if stats.linhas_alteradas > 0:
                summary_chips.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.EDIT, size=13, color=ft.Colors.AMBER_400),
                                ft.Text(
                                    f"{stats.linhas_alteradas} alterada(s)",
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.AMBER_400,
                                ),
                            ],
                            spacing=4,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER),
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    )
                )
            if stats.linhas_adicionadas > 0:
                summary_chips.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, size=13, color=ft.Colors.GREEN_400),
                                ft.Text(
                                    f"+{stats.linhas_adicionadas} adicionada(s)",
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.GREEN_400,
                                ),
                            ],
                            spacing=4,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN),
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    )
                )
            if stats.linhas_removidas > 0:
                summary_chips.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.REMOVE_CIRCLE_OUTLINE, size=13, color=ft.Colors.RED_400),
                                ft.Text(
                                    f"-{stats.linhas_removidas} removida(s)",
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.RED_400,
                                ),
                            ],
                            spacing=4,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.RED),
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    )
                )
            if stats.linhas_iguais > 0:
                summary_chips.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.CHECK, size=13, color=ft.Colors.GREY_400),
                                ft.Text(
                                    f"{stats.linhas_iguais} inalterada(s)",
                                    size=11,
                                    color=ft.Colors.GREY_400,
                                ),
                            ],
                            spacing=4,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    )
                )

        header_summary = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.ANALYTICS_OUTLINED, size=16, color=ft.Colors.BLUE_300),
                            ft.Text(
                                f"Similaridade de Letra: {simil_pct:.1f}%",
                                weight=ft.FontWeight.BOLD,
                                size=13,
                                color=ft.Colors.BLUE_200,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=6,
                    ),
                    ft.ProgressBar(
                        value=min(1.0, max(0.0, simil_pct / 100.0)),
                        color=ft.Colors.BLUE_400,
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        height=5,
                        border_radius=3,
                    ),
                    *(
                        [
                            ft.Row(
                                controls=summary_chips,
                                wrap=True,
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=6,
                                run_spacing=6,
                            )
                        ]
                        if summary_chips
                        else []
                    ),
                ],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=12,
            padding=ft.Padding.symmetric(vertical=10, horizontal=14),
            margin=ft.Padding.only(bottom=15),
        )

        diff_controls: list[ft.Control] = [header_summary]

        if not blocos:
            diff_controls.append(
                ft.Text(
                    self.comparativo.diff_texto or "Nenhuma diferença detalhada encontrada.",
                    size=self.font_size,
                    font_family=font_fam,
                    text_align=ft.TextAlign.CENTER,
                )
            )
            return ft.Column(
                controls=diff_controls,
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )

        for b in blocos:
            if b.tipo == "igual":
                if b.texto:
                    diff_controls.append(
                        ft.Container(
                            content=ft.Text(
                                b.texto,
                                size=self.font_size,
                                font_family=font_fam,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            padding=ft.Padding.symmetric(vertical=2, horizontal=8),
                            alignment=ft.Alignment.CENTER,
                        )
                    )
            elif b.tipo == "modificado":
                antigo_lines = b.antigo or []
                novo_lines = b.novo or []

                mod_controls = []
                if antigo_lines:
                    mod_controls.append(
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Icon(ft.Icons.REMOVE_CIRCLE_OUTLINE, size=13, color=ft.Colors.RED_400),
                                            ft.Text(
                                                "Antes (Antigo):",
                                                size=11,
                                                weight=ft.FontWeight.BOLD,
                                                color=ft.Colors.RED_400,
                                            ),
                                        ],
                                        spacing=4,
                                    ),
                                    *(
                                        ft.Text(
                                            f"• {line}",
                                            size=max(12, self.font_size - 1),
                                            font_family=font_fam,
                                            color=ft.Colors.RED_200,
                                        )
                                        for line in antigo_lines
                                    ),
                                ],
                                spacing=3,
                            ),
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.RED),
                            border=ft.Border(left=ft.BorderSide(3, ft.Colors.RED_400)),
                            border_radius=ft.BorderRadius.only(top_right=8, bottom_right=8),
                            padding=ft.Padding.all(10),
                            margin=ft.Padding.symmetric(vertical=2),
                        )
                    )

                if novo_lines:
                    mod_controls.append(
                        ft.Container(
                            content=ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, size=13, color=ft.Colors.GREEN_400),
                                            ft.Text(
                                                "Depois (Novo):",
                                                size=11,
                                                weight=ft.FontWeight.BOLD,
                                                color=ft.Colors.GREEN_400,
                                            ),
                                        ],
                                        spacing=4,
                                    ),
                                    *(
                                        ft.Text(
                                            f"• {line}",
                                            size=self.font_size,
                                            font_family=font_fam,
                                            weight=ft.FontWeight.W_500,
                                            color=ft.Colors.GREEN_200,
                                        )
                                        for line in novo_lines
                                    ),
                                ],
                                spacing=3,
                            ),
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN),
                            border=ft.Border(left=ft.BorderSide(3, ft.Colors.GREEN_400)),
                            border_radius=ft.BorderRadius.only(top_right=8, bottom_right=8),
                            padding=ft.Padding.all(10),
                            margin=ft.Padding.symmetric(vertical=2),
                        )
                    )

                diff_controls.append(
                    ft.Container(
                        content=ft.Column(controls=mod_controls, spacing=4),
                        padding=ft.Padding.symmetric(vertical=4),
                    )
                )

            elif b.tipo == "adicionado":
                diff_controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.ADD, size=14, color=ft.Colors.GREEN_400),
                                ft.Text(
                                    b.texto or "",
                                    size=self.font_size,
                                    font_family=font_fam,
                                    color=ft.Colors.GREEN_200,
                                    weight=ft.FontWeight.W_500,
                                    expand=True,
                                ),
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN),
                        border=ft.Border(left=ft.BorderSide(3, ft.Colors.GREEN_400)),
                        border_radius=ft.BorderRadius.only(top_right=8, bottom_right=8),
                        padding=ft.Padding.all(8),
                        margin=ft.Padding.symmetric(vertical=2),
                    )
                )

            elif b.tipo == "removido":
                diff_controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.REMOVE, size=14, color=ft.Colors.RED_400),
                                ft.Text(
                                    b.texto or "",
                                    size=self.font_size,
                                    font_family=font_fam,
                                    color=ft.Colors.RED_200,
                                    expand=True,
                                ),
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.RED),
                        border=ft.Border(left=ft.BorderSide(3, ft.Colors.RED_400)),
                        border_radius=ft.BorderRadius.only(top_right=8, bottom_right=8),
                        padding=ft.Padding.all(8),
                        margin=ft.Padding.symmetric(vertical=2),
                    )
                )

        return ft.Column(
            controls=diff_controls,
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

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

    async def _toggle_favorito(self, page: ft.Page, hino: Optional[Hino] = None) -> None:
        target_hino = hino or self.current_hino
        if not target_hino:
            return
        if self.is_fav:
            await self.favorito_repository.remove_favorito(self.hino_id)
            self.is_fav = False
            msg = f"Hino {target_hino.numero} removido dos favoritos"
        else:
            await self.favorito_repository.add_favorito(self.hino_id)
            self.is_fav = True
            msg = f"Hino {target_hino.numero} adicionado aos favoritos!"

        self._update_fav_icon_state()
        self._show_snackbar(page, msg)

    async def _open_youtube_link(self, page: ft.Page, hino: Optional[Hino] = None) -> None:
        """Abre o link externo do YouTube no navegador ou app nativo."""
        target_hino = hino or self.current_hino
        if not target_hino or not target_hino.link_video or not target_hino.link_video.strip():
            self._show_snackbar(page, "Este hino não possui link do YouTube cadastrado.")
            return

        url = target_hino.link_video.strip()
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
                padding=ft.Padding.only(left=20, top=20, right=20, bottom=40),
            )
        )
        page.show_dialog(bs)



    async def _navigate_search(self, page: ft.Page, term: str) -> None:
        """Fecha o modal e navega para Home com busca FTS pelo termo."""
        try:
            page.pop_dialog()
        except Exception:
            pass
        await page.push_route(f"/?q={term}")

    def _trigger_search_navigation(self, page: ft.Page, term: str) -> None:
        """Aciona a navegação de busca mantendo a referência da task."""
        if self._nav_task and not self._nav_task.done():
            self._nav_task.cancel()
        self._nav_task = asyncio.create_task(self._navigate_search(page, term))

    def _extract_author_metadata(self, hino: Hino) -> list[tuple[str, str]]:
        """Extrai os pares (rótulo, valor) de autoria do hino."""
        if hino.autor_letra and hino.autor_musica and hino.autor_letra == hino.autor_musica:
            return [("Letra e Música:", hino.autor_letra)]

        metadata = []
        if hino.autor_letra:
            metadata.append(("Autor da Letra:", hino.autor_letra))
        if hino.autor_musica:
            metadata.append(("Autor da Música:", hino.autor_musica))
        if not metadata and hino.autores:
            metadata.append(("Autores:", hino.autores))
        return metadata

    def _build_info_metadata_items(self, hino: Hino) -> list[ft.Control]:
        """Gera os controles visuais para os autores do hino."""
        items: list[ft.Control] = []
        for label, val in self._extract_author_metadata(hino):
            if val and val.strip():
                items.append(
                    ft.Column(
                        controls=[
                            ft.Text(label, weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.BLUE_200),
                            ft.Text(val, size=14),
                        ],
                        spacing=2,
                    )
                )
        return items

    def _build_texto_base_info_control(self, page: ft.Page, hino: Hino) -> Optional[ft.Control]:
        """Gera o controle de texto base bíblico do hino."""
        if not (hino.texto_base and hino.texto_base.strip()):
            return None
        return ft.Column(
            controls=[
                ft.Text("Texto Base Bíblico:", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.BLUE_200),
                ft.Chip(
                    label=ft.Text(hino.texto_base, size=12),
                    leading=ft.Icon(ft.Icons.MENU_BOOK_OUTLINED, size=15, color=ft.Colors.GREEN_400),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    tooltip=TOOLTIP_LER_PASSAGEM_BIBLICA,
                    on_click=lambda e, ref=hino.texto_base: self._on_biblia_click(
                        page, ref, from_info_modal=True, hino=hino
                    ),
                ),
            ],
            spacing=4,
        )

    def _build_category_info_control(self, page: ft.Page, hino: Hino) -> Optional[ft.Control]:
        """Gera a seção de chips de categoria e subcategoria."""
        cat_chips: list[ft.Control] = []
        if hino.categoria and hino.categoria.strip():
            cat_chips.append(
                ft.Chip(
                    label=ft.Text(hino.categoria, size=12),
                    leading=ft.Icon(ft.Icons.FOLDER_OUTLINED, size=16, color=ft.Colors.BLUE_400),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    on_click=lambda e, c=hino.categoria: self._trigger_search_navigation(page, c),
                )
            )
        if hino.subcategoria and hino.subcategoria.strip():
            cat_chips.append(
                ft.Chip(
                    label=ft.Text(hino.subcategoria, size=12),
                    leading=ft.Icon(ft.Icons.FOLDER_SPECIAL_OUTLINED, size=16, color=ft.Colors.BLUE_300),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    on_click=lambda e, sc=hino.subcategoria: self._trigger_search_navigation(page, sc),
                )
            )
        if not cat_chips:
            return None
        return ft.Column(
            controls=[
                ft.Text("Categoria:", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.BLUE_200),
                ft.Row(controls=cat_chips, wrap=True, spacing=6, run_spacing=6),
            ],
            spacing=4,
        )

    def _build_themes_info_control(self, page: ft.Page) -> Optional[ft.Control]:
        """Gera a seção de chips dos temas relacionados."""
        temas = self.relacionados.get("temas", [])
        if not temas:
            return None
        tema_chips: list[ft.Control] = [
            ft.Chip(
                label=ft.Text(t, size=11),
                leading=ft.Icon(ft.Icons.LABEL_OUTLINED, size=15, color=ft.Colors.AMBER_400),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                on_click=lambda e, tema=t: self._trigger_search_navigation(page, tema),
            )
            for t in temas
        ]
        return ft.Column(
            controls=[
                ft.Text("Temas Relacionados:", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.AMBER_200),
                ft.Row(controls=tema_chips, wrap=True, spacing=6, run_spacing=6),
            ],
            spacing=4,
        )

    def _build_biblical_texts_info_control(self, page: ft.Page, hino: Hino) -> Optional[ft.Control]:
        """Gera a seção de chips dos textos bíblicos relacionados."""
        textos_biblicos = self.relacionados.get("textos_biblicos", [])
        if not textos_biblicos:
            return None
        texto_chips: list[ft.Control] = [
            ft.Chip(
                label=ft.Text(tb, size=11),
                leading=ft.Icon(ft.Icons.MENU_BOOK_OUTLINED, size=15, color=ft.Colors.GREEN_400),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                tooltip=TOOLTIP_LER_PASSAGEM_BIBLICA,
                on_click=lambda e, ref=tb: self._on_biblia_click(
                    page, ref, from_info_modal=True, hino=hino
                ),
            )
            for tb in textos_biblicos
        ]
        return ft.Column(
            controls=[
                ft.Text("Textos Bíblicos Relacionados:", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.GREEN_200),
                ft.Row(controls=texto_chips, wrap=True, spacing=6, run_spacing=6),
            ],
            spacing=4,
        )

    def _build_comparativo_info_control(self, page: ft.Page, hino: Hino) -> Optional[ft.Control]:
        """Gera a seção informativa sobre a correspondência com o Hinário Antigo."""
        if not self.comparativo:
            return None

        items: list[ft.Control] = []
        if self.comparativo.status_comparacao == "NOVO_INEDITO":
            items.append(
                ft.Text("Hino inédito inserido nesta edição do hinário.", size=13, color=ft.Colors.PURPLE_200)
            )
        elif self.comparativo.numero_antigo:
            titulo_ant = self.comparativo.titulo_antigo or "(mesmo título)"
            items.append(
                ft.Row(
                    controls=[
                        ft.Text("Hinário Antigo:", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.BLUE_200),
                        ft.Text(f"Hino #{self.comparativo.numero_antigo} - {titulo_ant}", size=13),
                    ],
                    spacing=6,
                    wrap=True,
                )
            )
            if self.comparativo.similaridade_pct is not None:
                items.append(
                    ft.Row(
                        controls=[
                            ft.Text("Similaridade da Letra:", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.BLUE_200),
                            ft.Text(f"{self.comparativo.similaridade_pct:.1f}%", size=13),
                        ],
                        spacing=6,
                    )
                )
            if self.comparativo.resumo_alteracoes:
                items.append(
                    ft.Row(
                        controls=[
                            ft.Text("Resumo de Alterações:", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.BLUE_200),
                            ft.Text(self.comparativo.resumo_alteracoes, size=13, italic=True),
                        ],
                        spacing=6,
                    )
                )

        if not items:
            return None

        return ft.Column(
            controls=[
                ft.Text("Comparativo com Hinário Antigo:", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.BLUE_200),
                *items,
            ],
            spacing=4,
        )

    def _show_info_modal(self, page: ft.Page, hino: Optional[Hino] = None) -> None:
        target_hino = hino or self.current_hino
        if not target_hino:
            return

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

        info_items.extend(self._build_info_metadata_items(target_hino))

        for section in (
            self._build_comparativo_info_control(page, target_hino),
            self._build_texto_base_info_control(page, target_hino),
            self._build_category_info_control(page, target_hino),
            self._build_themes_info_control(page),
            self._build_biblical_texts_info_control(page, target_hino),
        ):
            if section:
                info_items.append(section)

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
                padding=ft.Padding.only(left=20, top=20, right=20, bottom=40),
            )
        )
        page.show_dialog(bs)
