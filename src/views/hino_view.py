import asyncio
import json
from typing import Any

import flet as ft

from src.models.biblia import PassagemBiblica
from src.models.comparativo import BlocoDiff, EstatisticasDiff, HinoComparativo
from src.models.hino import Hino
from src.repositories.biblia_repository import BibliaRepository
from src.repositories.comparativo_repository import ComparativoRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.hino_repository import HinoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.services.media_service import MediaService
from src.services.theme_service import ThemeService

DEFAULT_FONT_FAMILY = "Padrão"
TIMES_NEW_ROMAN_FONT_FAMILY = "Times New Roman"
OPENDYSLEXIC_FONT_FAMILY = "OpenDyslexic"
HELVETICA_FONT_FAMILY = "Helvetica"
MONTSERRAT_FONT_FAMILY = "Montserrat"

FONT_FAMILY_MAP = {
    DEFAULT_FONT_FAMILY: None,
    TIMES_NEW_ROMAN_FONT_FAMILY: TIMES_NEW_ROMAN_FONT_FAMILY,
    OPENDYSLEXIC_FONT_FAMILY: OPENDYSLEXIC_FONT_FAMILY,
    HELVETICA_FONT_FAMILY: HELVETICA_FONT_FAMILY,
    MONTSERRAT_FONT_FAMILY: MONTSERRAT_FONT_FAMILY,
}

TOOLTIP_LER_PASSAGEM_BIBLICA = "Ler passagem bíblica"
BTN_CAPITULO_COMPLETO = "Capítulo Completo"
BTN_APENAS_VERSICULOS = "Apenas Versículos"
MSG_LETRA_NAO_DISPONIVEL = "Letra não disponível no banco local."
MSG_HINO_NAO_ENCONTRADO = "Hino correspondente não encontrado."


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
        media_service: MediaService | None = None,
        hino_ids_list: list[int] | None = None,
        biblia_repository: BibliaRepository | None = None,
        comparativo_repository: ComparativoRepository | None = None,
        antigo_repository: HinoRepository | None = None,
        novo_repository: HinoRepository | None = None,
        edition: str = "novo",
        theme_service: ThemeService | None = None,
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
        self.novo_repository = novo_repository
        self.edition: str = edition
        self.theme_service = theme_service

        # Estado da visualização comparativa (Hinário Novo vs Antigo)
        self.comparativo: HinoComparativo | None = None
        self.hino_antigo: Hino | None = None
        self.selected_view_mode: str = (
            "novo" if edition == "novo" else "antigo"
        )  # "novo", "antigo", "comparacao"
        self.content_container: ft.Container | None = None
        self.segmented_button: ft.SegmentedButton | None = None

        # Estado interno de acessibilidade de fonte e versão da Bíblia (carregado do banco)
        self.font_size: int = 18
        self.selected_font: str = DEFAULT_FONT_FAMILY
        self.selected_biblia_version: str = "ARA"
        self.is_custom_font: bool = False
        self._prefs_loaded: bool = False
        self._save_pref_task: asyncio.Task | None = None
        self._biblia_task: asyncio.Task | None = None
        self._nav_task: asyncio.Task | None = None
        self._background_tasks: set[asyncio.Task] = set()

        # Referências aos elementos dinâmicos da interface
        self.page: ft.Page | None = None
        self.letra_text: ft.Text | None = None
        self.font_size_text: ft.Text | None = None
        self.fav_icon: ft.IconButton | None = None
        self.youtube_btn: ft.IconButton | None = None
        self.is_fav: bool = False
        self.current_hino: Hino | None = None
        self.relacionados: dict[str, list[str]] = {"temas": [], "textos_biblicos": []}

        # Estado da visualização bíblica imersiva
        self.active_biblia_ref: str | None = None
        self.is_biblia_full_chapter: bool = False
        self.current_biblia_passagem: PassagemBiblica | None = None
        self._biblia_loading: bool = False

        # SnackBar singleton reutilizável (evita acúmulo no overlay)
        self._snackbar: ft.SnackBar | None = None

    def _create_background_task(self, coro) -> asyncio.Task:
        """Cria e rastreia uma tarefa assíncrona evitando que seja coletada prematuramente pelo Garbage Collector."""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

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
        """Carrega preferências de fonte e versão da Bíblia do banco de dados (uma vez)."""
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
                self.selected_biblia_version = prefs.get("biblia_version", "ARA")
        except Exception:
            pass
        self._prefs_loaded = True

    async def _save_preferences(self) -> None:
        """Salva preferências de fonte e versão da Bíblia no banco de dados."""
        try:
            prefs = json.dumps(
                {
                    "font_size": self.font_size,
                    "font_family": self.selected_font,
                    "is_custom": self.is_custom_font,
                    "biblia_version": self.selected_biblia_version,
                }
            )
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

    def _create_comparativo_task(self, numero: str):
        """Retorna a corrotina de busca no repositório de comparativo conforme a edição."""
        if not self.comparativo_repository:
            return asyncio.sleep(0, result=None)
        if self.edition == "antigo":
            return self.comparativo_repository.get_by_numero_antigo(numero)
        return self.comparativo_repository.get_by_numero_novo(numero)

    async def _resolve_counterpart_hino(self) -> None:
        """Carrega a entidade do hino correspondente da outra edição com tratamento de falhas."""
        if not self.comparativo:
            return

        if self.edition == "antigo" and self.comparativo.numero_novo:
            repo = self.novo_repository or self.antigo_repository
            target_num = self.comparativo.numero_novo
        elif self.comparativo.numero_antigo and self.antigo_repository:
            repo = self.antigo_repository
            target_num = self.comparativo.numero_antigo
        else:
            return

        if repo and target_num:
            try:
                self.hino_antigo = await repo.get_by_numero(target_num)
            except Exception:
                self.hino_antigo = None

    async def _init_data_and_preferences(self, page: ft.Page, hino: Hino) -> None:
        """Carrega preferências de fonte e executa queries de metadados em paralelo."""
        await self._load_preferences()

        if not self.is_custom_font:
            self.font_size = self._calculate_responsive_font_size(page)

        historico_task = self.historico_repository.add_acesso(self.hino_id)
        metadados_task = self.hino_repository.get_metadados_relacionados(self.hino_id)
        favorito_task = self.favorito_repository.is_favorito(self.hino_id)
        comparativo_task = self._create_comparativo_task(hino.numero)

        _, self.relacionados, self.is_fav, self.comparativo = await asyncio.gather(
            historico_task, metadados_task, favorito_task, comparativo_task
        )

        if hino.texto_base and hino.texto_base.strip():
            self.active_biblia_ref = hino.texto_base.strip()
        elif self.relacionados.get("textos_biblicos"):
            self.active_biblia_ref = self.relacionados["textos_biblicos"][0].strip()

        await self._resolve_counterpart_hino()

    def _build_header_container(self, page: ft.Page, hino: Hino) -> ft.Container:
        """Constrói a seção de cabeçalho do hino (título, texto base, chip comparativo)."""
        titulo_text = ft.Text(
            hino.titulo,
            size=22,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
            color=ft.Colors.BLUE_200,
        )

        header_controls: list[ft.Control] = [titulo_text]
        chips_controls: list[ft.Control] = []

        if hino.texto_base and hino.texto_base.strip():
            chips_controls.append(
                ft.Chip(
                    label=ft.Text(hino.texto_base, size=12),
                    leading=ft.Icon(
                        ft.Icons.MENU_BOOK_OUTLINED, size=15, color=ft.Colors.GREEN_400
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    tooltip=TOOLTIP_LER_PASSAGEM_BIBLICA,
                    on_click=lambda e, ref=hino.texto_base: self._on_biblia_click(
                        page, ref
                    ),
                )
            )

        comparativo_chip = self._build_comparativo_chip(page)
        if comparativo_chip:
            chips_controls.append(comparativo_chip)

        if chips_controls:
            header_controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=chips_controls,
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                        spacing=8,
                        run_spacing=6,
                    ),
                    padding=ft.Padding.only(top=12),
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=header_controls,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
            ),
            padding=ft.Padding.only(top=16, bottom=12, left=20, right=20),
            alignment=ft.Alignment.CENTER,
        )

    def _build_bottom_appbar(
        self, page: ft.Page, youtube_btn: ft.IconButton
    ) -> ft.BottomAppBar:
        """Constrói a barra inferior com atalhos de fonte e YouTube."""
        return ft.BottomAppBar(
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
                            youtube_btn,
                            ft.Text("YouTube", size=10, text_align=ft.TextAlign.CENTER),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=0,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        )

    async def build(self, page: ft.Page) -> ft.View:
        self.page = page
        self.page.on_resize = self._on_page_resize

        hino: Hino | None = await self.hino_repository.get_by_id(self.hino_id)
        if hino is None:
            return self._build_not_found_view(page)

        self.current_hino = hino
        await self._init_data_and_preferences(page, hino)

        self.letra_text = ft.Text(
            hino.letra if hino.letra else "Letra não disponível para este hino.",
            size=self.font_size,
            text_align=ft.TextAlign.CENTER,
            weight=ft.FontWeight.W_400,
            font_family=FONT_FAMILY_MAP.get(self.selected_font),
            expand=True,
        )

        self.content_container = ft.Container(
            content=self._render_current_mode_content(),
            padding=ft.Padding.symmetric(vertical=20, horizontal=20),
            alignment=ft.Alignment.TOP_CENTER,
            expand=True,
        )

        self.fav_icon = ft.IconButton(
            icon=ft.Icons.FAVORITE if self.is_fav else ft.Icons.FAVORITE_BORDER,
            icon_color=ft.Colors.RED_400 if self.is_fav else None,
            tooltip="Desfavoritar" if self.is_fav else "Favoritar",
            on_click=lambda e: page.run_task(self._toggle_favorito, page, hino),
        )

        has_youtube = bool(hino.link_video and hino.link_video.strip())
        self.youtube_btn = ft.IconButton(
            icon=(
                ft.Icons.PLAY_CIRCLE_OUTLINE
                if hasattr(ft.Icons, "PLAY_CIRCLE_OUTLINE")
                else ft.Icons.PLAY_ARROW
            ),
            icon_color=ft.Colors.RED_400 if has_youtube else None,
            tooltip=(
                "Assistir no YouTube (Link Externo)"
                if has_youtube
                else "Link do YouTube indisponível"
            ),
            disabled=not has_youtube,
            on_click=lambda e: page.run_task(self._open_youtube_link, page, hino),
        )

        prev_btn, next_btn = self._build_nav_buttons(page)
        header_container = self._build_header_container(page, hino)

        column_controls: list[ft.Control] = [header_container]
        segmented_btn = self._build_segmented_button(page)
        if segmented_btn:
            column_controls.append(segmented_btn)

        column_controls.append(ft.Divider(height=1))
        column_controls.append(self.content_container)

        scroll_column = ft.Column(
            controls=column_controls,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        if self.theme_service:
            self.theme_service.apply_theme(page, edition=self.edition)

        async def _go_back(e):
            if len(page.views) > 1:
                page.views.pop()
                top_view = page.views[-1]
                await page.push_route(top_view.route)
            else:
                await page.push_route(f"/{self.edition}")

        return ft.View(
            route=f"/{self.edition}/hino/{self.hino_id}",
            bgcolor=ft.Colors.SURFACE,
            appbar=ft.AppBar(
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=_go_back),
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
                ft.SafeArea(
                    maintain_bottom_view_padding=True,
                    content=ft.Container(content=scroll_column, expand=True, padding=0),
                    expand=True,
                ),
            ],
            bottom_appbar=self._build_bottom_appbar(page, self.youtube_btn),
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
                await page.push_route(f"/{self.edition}/hino/{prev_id}")

        async def _go_next(e):
            if has_next:
                next_id = self.hino_ids_list[current_idx + 1]
                await page.push_route(f"/{self.edition}/hino/{next_id}")

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
    ) -> None:
        """Manipula o clique em um chip bíblico, alternando a tela para o modo de leitura bíblica imersiva."""
        try:
            page.pop_dialog()
        except Exception:
            pass
        self.active_biblia_ref = ref.strip() if ref else None
        self.selected_view_mode = "biblia"
        if self.segmented_button:
            self.segmented_button.selected = ["biblia"]
        self._update_content_view(page)
        if hasattr(page, "run_task"):
            page.run_task(
                self._carregar_biblia_passagem,
                page,
            )
        else:
            if self._biblia_task and not self._biblia_task.done():
                self._biblia_task.cancel()
            self._biblia_task = self._create_background_task(
                self._carregar_biblia_passagem(page)
            )

    async def _carregar_biblia_passagem(self, page: ft.Page | None = None) -> None:
        """Carrega assincronamente a passagem bíblica ativa para a visualização imersiva em tela cheia."""
        if not self.active_biblia_ref:
            return

        self._biblia_loading = True
        self._update_content_view(page)

        try:
            if self.is_biblia_full_chapter:
                passagem = await self.biblia_repository.buscar_capitulo_completo(
                    self.active_biblia_ref, versao=self.selected_biblia_version
                )
            else:
                passagem = await self.biblia_repository.buscar_passagem(
                    self.active_biblia_ref, versao=self.selected_biblia_version
                )
        except Exception:
            passagem = None

        self.current_biblia_passagem = passagem
        self._biblia_loading = False
        self._update_content_view(page)

    def _gather_hino_biblical_refs(
        self, target_hino: Hino | None, ref_clean: str
    ) -> list[str]:
        """Reúne todas as referências bíblicas únicas associadas ao hino."""
        all_refs: list[str] = []
        if target_hino and target_hino.texto_base and target_hino.texto_base.strip():
            all_refs.append(target_hino.texto_base.strip())
        for tb in self.relacionados.get("textos_biblicos", []):
            if tb and tb.strip() and tb.strip() not in all_refs:
                all_refs.append(tb.strip())

        if ref_clean not in all_refs:
            all_refs.insert(0, ref_clean)
        return all_refs

    def _build_verse_rows(
        self,
        versiculos: list[Any],
        font_size: int,
        font_family: str | None,
        verse_num_color: str,
    ) -> list[ft.Control]:
        """Constrói a lista de linhas de versículos renderizados com tipografia ajustável."""
        verse_controls: list[ft.Control] = []
        for v in versiculos:
            verse_controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text(
                                    str(v.numero),
                                    weight=ft.FontWeight.BOLD,
                                    size=max(11, font_size - 4),
                                    color=verse_num_color,
                                ),
                                alignment=ft.Alignment.TOP_RIGHT,
                                width=28,
                                padding=ft.Padding.only(top=2),
                            ),
                            ft.Text(
                                v.texto,
                                size=font_size,
                                font_family=font_family,
                                selectable=True,
                                expand=True,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        spacing=8,
                    ),
                    padding=ft.Padding.symmetric(vertical=3, horizontal=4),
                    border_radius=6,
                )
            )
        return verse_controls

    def _build_biblia_error_container(
        self, ref_to_search: str, versao_alvo: str
    ) -> ft.Container:
        """Gera o container informativo de falha ao buscar a passagem bíblica."""
        version_desc = self.biblia_repository.get_version_name(versao_alvo)
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        ft.Icons.AUTO_STORIES,
                        size=48,
                        color=ft.Colors.GREY_500,
                    ),
                    ft.Text(
                        "Não foi possível carregar a passagem bíblica solicitada.",
                        size=15,
                        weight=ft.FontWeight.W_500,
                        text_align=ft.TextAlign.CENTER,
                        color=ft.Colors.GREY_400,
                    ),
                    ft.Text(
                        f"Referência: {ref_to_search} ({versao_alvo} - {version_desc})",
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

    def _build_biblia_modal_ref_chips(
        self,
        all_refs: list[str],
        active_ref: str,
        base_ref: str | None,
        accent_color: str,
        on_select_callback: Any,
    ) -> list[ft.Control]:
        """Gera os chips horizontais de alternância entre referências bíblicas."""
        if len(all_refs) <= 1:
            return []
        chips = []
        for r in all_refs:
            is_active = r == active_ref
            is_base = bool(base_ref and r == base_ref.strip())
            label_prefix = "✦ " if is_base else ""
            label_suffix = " (Base)" if is_base else ""

            chips.append(
                ft.Container(
                    content=ft.Text(
                        f"{label_prefix}{r}{label_suffix}",
                        size=11,
                        weight=(
                            ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL
                        ),
                        color=(
                            accent_color if is_active else ft.Colors.ON_SURFACE_VARIANT
                        ),
                    ),
                    bgcolor=(
                        ft.Colors.with_opacity(0.18, accent_color)
                        if is_active
                        else ft.Colors.SURFACE_CONTAINER_HIGHEST
                    ),
                    border=ft.Border.all(1, accent_color) if is_active else None,
                    border_radius=12,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    on_click=lambda e, ref_target=r: on_select_callback(e, ref_target),
                    ink=True,
                )
            )
        return [
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Passagens deste hino:",
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.GREY_400,
                        ),
                        ft.Row(controls=chips, scroll=ft.ScrollMode.AUTO, spacing=6),
                    ],
                    spacing=4,
                ),
                padding=ft.Padding.only(top=2, bottom=4),
            )
        ]

    def _build_biblia_modal_action_bar(
        self,
        copy_btn: ft.Control,
        chapter_toggle_btn: ft.Control,
        font_minus_btn: ft.Control,
        font_indicator: ft.Control,
        font_plus_btn: ft.Control,
    ) -> ft.Container:
        """Gera a barra de ações inferiores do modal bíblico."""
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Row(
                        controls=[copy_btn, chapter_toggle_btn],
                        spacing=6,
                    ),
                    ft.Row(
                        controls=[font_minus_btn, font_indicator, font_plus_btn],
                        spacing=2,
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
            ),
            padding=ft.Padding.symmetric(vertical=2),
        )

    async def _abrir_modal_leitura_biblica(
        self,
        page: ft.Page,
        referencia: str,
        from_info_modal: bool = False,
        hino: Hino | None = None,
    ) -> None:
        """
        Abre um modal responsivo e moderno (BottomSheet) para leitura da passagem bíblica informada.
        Permite alternar referências do hino, selecionar versões, ver capítulo completo, ajustar zoom
        e copiar a citação formatada para a área de transferência.
        """
        if not referencia or not referencia.strip():
            self._show_snackbar(page, "Referência bíblica inválida.")
            return

        ref_clean = referencia.strip()
        await self._load_preferences()

        target_hino = hino or getattr(self, "current_hino", None)
        all_refs = self._gather_hino_biblical_refs(target_hino, ref_clean)

        current_ref_holder = [ref_clean]
        is_full_chapter_holder = [False]
        current_font_size_holder = [self.font_size]
        current_passagem_holder: list[PassagemBiblica | None] = [None]
        is_expanded_holder = [False]

        accent_color = (
            ft.Colors.PURPLE_200 if self.edition == "antigo" else ft.Colors.BLUE_200
        )
        verse_num_color = (
            ft.Colors.PURPLE_300 if self.edition == "antigo" else ft.Colors.TEAL_300
        )

        versoes_disponiveis = self.biblia_repository.get_available_versions()
        if (
            not self.selected_biblia_version
            or self.selected_biblia_version not in versoes_disponiveis
        ):
            self.selected_biblia_version = (
                versoes_disponiveis[0] if versoes_disponiveis else "ARA"
            )

        title_text = ft.Text(
            ref_clean,
            weight=ft.FontWeight.BOLD,
            size=17,
            color=accent_color,
            expand=True,
        )

        loading_indicator = ft.Container(
            content=ft.Column(
                controls=[
                    ft.ProgressRing(width=36, height=36, stroke_width=3),
                    ft.Text(
                        "Carregando passagem bíblica...",
                        size=14,
                        color=ft.Colors.GREY_400,
                    ),
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
            spacing=8,
        )

        def _render_loaded_verses():
            passagem = current_passagem_holder[0]
            if not passagem or not passagem.versiculos:
                return
            font_fam = FONT_FAMILY_MAP.get(self.selected_font)
            verses_container.controls = self._build_verse_rows(
                passagem.versiculos,
                current_font_size_holder[0],
                font_fam,
                verse_num_color,
            )

        async def _carregar_versiculos(versao_alvo: str):
            verses_container.controls = [loading_indicator]
            page.update()

            ref_to_search = current_ref_holder[0]
            try:
                if is_full_chapter_holder[0]:
                    passagem = await self.biblia_repository.buscar_capitulo_completo(
                        ref_to_search, versao=versao_alvo
                    )
                else:
                    passagem = await self.biblia_repository.buscar_passagem(
                        ref_to_search, versao=versao_alvo
                    )
            except Exception:
                passagem = None

            current_passagem_holder[0] = passagem

            if passagem and passagem.versiculos:
                title_text.value = passagem.referencia
                chapter_toggle_btn.content = (
                    BTN_APENAS_VERSICULOS
                    if is_full_chapter_holder[0]
                    else BTN_CAPITULO_COMPLETO
                )
                chapter_toggle_btn.icon = (
                    ft.Icons.FILTER_LIST
                    if is_full_chapter_holder[0]
                    else ft.Icons.AUTO_STORIES
                )
                copy_btn.disabled = False
                _render_loaded_verses()
            else:
                title_text.value = ref_to_search
                copy_btn.disabled = True
                verses_container.controls = [
                    self._build_biblia_error_container(ref_to_search, versao_alvo)
                ]
            page.update()

        async def _on_versao_changed(e):
            nova_versao = e.control.value
            if not nova_versao:
                return
            self.selected_biblia_version = nova_versao
            self.biblia_repository.set_version(nova_versao)
            if self._save_pref_task and not self._save_pref_task.done():
                self._save_pref_task.cancel()
            self._save_pref_task = self._create_background_task(
                self._save_preferences()
            )
            await _carregar_versiculos(nova_versao)

        version_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option(key=v, text=v) for v in versoes_disponiveis],
            value=self.selected_biblia_version,
            width=92,
            height=36,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=2),
            dense=True,
            border_radius=8,
            tooltip="Versão da Bíblia",
            on_select=_on_versao_changed,
        )

        def _close_dialog(ev):
            page.pop_dialog()
            if from_info_modal:
                self._show_info_modal(page, target_hino)

        def _toggle_expand(ev):
            is_expanded_holder[0] = not is_expanded_holder[0]
            if is_expanded_holder[0]:
                modal_body.height = (
                    max(400, page.height * 0.94) if page and page.height else 720
                )
                expand_btn.icon = ft.Icons.FULLSCREEN_EXIT
                expand_btn.tooltip = "Recolher leitura"
            else:
                modal_body.height = (
                    min(page.height * 0.75, 540) if page and page.height else 450
                )
                expand_btn.icon = ft.Icons.FULLSCREEN
                expand_btn.tooltip = "Expandir leitura (Tela Cheia)"
            page.update()

        expand_btn = ft.IconButton(
            ft.Icons.FULLSCREEN,
            icon_size=20,
            tooltip="Expandir leitura (Tela Cheia)",
            on_click=_toggle_expand,
        )

        header_row = ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.MENU_BOOK, color=accent_color, size=22),
                        title_text,
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    expand=True,
                ),
                version_dropdown,
                expand_btn,
                ft.IconButton(
                    ft.Icons.CLOSE,
                    icon_size=20,
                    tooltip="Fechar",
                    on_click=_close_dialog,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        )

        ref_chips_container = ft.Container()

        async def _on_chip_selected(e, ref_target: str):
            if current_ref_holder[0] != ref_target:
                current_ref_holder[0] = ref_target
                is_full_chapter_holder[0] = False
                _update_ref_chips()
                await _carregar_versiculos(self.selected_biblia_version)

        def _update_ref_chips():
            base_ref = target_hino.texto_base if target_hino else None
            chips = self._build_biblia_modal_ref_chips(
                all_refs,
                current_ref_holder[0],
                base_ref,
                accent_color,
                _on_chip_selected,
            )
            ref_chips_container.content = (
                ft.Column(controls=chips, spacing=0) if chips else ft.Container()
            )

        _update_ref_chips()

        async def _copiar_passagem(ev):
            passagem = current_passagem_holder[0]
            if not passagem or not passagem.versiculos:
                return
            texto_copia = f"{passagem.texto_formatado}\n\n({passagem.referencia} - {self.selected_biblia_version})"
            try:
                await ft.Clipboard().set(texto_copia)
            except Exception:
                pass
            self._show_snackbar(page, f"Passagem '{passagem.referencia}' copiada!")

        copy_btn = ft.OutlinedButton(
            "Copiar",
            icon=ft.Icons.CONTENT_COPY,
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                text_style=ft.TextStyle(size=12),
            ),
            tooltip="Copiar passagem com referência para a área de transferência",
            on_click=_copiar_passagem,
        )

        async def _toggle_capitulo(ev):
            is_full_chapter_holder[0] = not is_full_chapter_holder[0]
            if is_full_chapter_holder[0] and not is_expanded_holder[0]:
                is_expanded_holder[0] = True
                modal_body.height = (
                    max(400, page.height * 0.94) if page and page.height else 720
                )
                expand_btn.icon = ft.Icons.FULLSCREEN_EXIT
                expand_btn.tooltip = "Recolher leitura"
            await _carregar_versiculos(self.selected_biblia_version)

        chapter_toggle_btn = ft.OutlinedButton(
            BTN_CAPITULO_COMPLETO,
            icon=ft.Icons.AUTO_STORIES,
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                text_style=ft.TextStyle(size=12),
            ),
            tooltip="Alternar entre versículos do hino e o capítulo completo",
            on_click=_toggle_capitulo,
        )

        font_indicator = ft.Text(
            f"{current_font_size_holder[0]}pt", size=12, weight=ft.FontWeight.BOLD
        )

        def _zoom_in(ev):
            if current_font_size_holder[0] < 36:
                current_font_size_holder[0] += 2
                font_indicator.value = f"{current_font_size_holder[0]}pt"
                _render_loaded_verses()
                page.update()

        def _zoom_out(ev):
            if current_font_size_holder[0] > 12:
                current_font_size_holder[0] -= 2
                font_indicator.value = f"{current_font_size_holder[0]}pt"
                _render_loaded_verses()
                page.update()

        font_minus_btn = ft.IconButton(
            ft.Icons.REMOVE_CIRCLE_OUTLINE,
            icon_size=18,
            tooltip="Diminuir tamanho da letra",
            on_click=_zoom_out,
        )
        font_plus_btn = ft.IconButton(
            ft.Icons.ADD_CIRCLE_OUTLINE,
            icon_size=18,
            tooltip="Aumentar tamanho da letra",
            on_click=_zoom_in,
        )

        action_bar = self._build_biblia_modal_action_bar(
            copy_btn,
            chapter_toggle_btn,
            font_minus_btn,
            font_indicator,
            font_plus_btn,
        )

        button_label = "Voltar para Informações" if from_info_modal else "Fechar"
        button_icon = ft.Icons.ARROW_BACK if from_info_modal else ft.Icons.CLOSE
        footer_row = ft.Row(
            controls=[
                ft.TextButton(button_label, icon=button_icon, on_click=_close_dialog)
            ],
            alignment=ft.MainAxisAlignment.END,
        )

        modal_body = ft.Container(
            content=ft.Column(
                controls=[
                    header_row,
                    ref_chips_container,
                    ft.Divider(height=1),
                    ft.Container(
                        content=verses_container,
                        expand=True,
                        padding=ft.Padding.symmetric(vertical=4),
                    ),
                    ft.Divider(height=1),
                    action_bar,
                    ft.Divider(height=1),
                    footer_row,
                ],
                spacing=6,
                expand=True,
            ),
            padding=ft.Padding.only(left=20, top=16, right=20, bottom=30),
            height=min(page.height * 0.85, 620) if page and page.height else 520,
        )

        bs = ft.BottomSheet(content=modal_body)
        page.show_dialog(bs)
        await _carregar_versiculos(self.selected_biblia_version)

    def _build_not_found_view(self, page: ft.Page) -> ft.View:
        async def _go_back(e):
            if len(page.views) > 1:
                page.views.pop()
                top_view = page.views[-1]
                await page.push_route(top_view.route)
            else:
                await page.push_route(f"/{self.edition}")

        return ft.View(
            route=f"/{self.edition}/hino/{self.hino_id}",
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

    def _build_comparativo_chip(self, page: ft.Page) -> ft.Control | None:
        """Gera o Chip/Badge informativo de status em relação à outra edição do Hinário."""
        if not self.comparativo:
            return None

        status = self.comparativo.status_comparacao
        if self.edition == "antigo":
            num_outro = self.comparativo.numero_novo
            nome_outro = "Hinário Novo"
        else:
            num_outro = self.comparativo.numero_antigo
            nome_outro = "Hinário Antigo"

        if not num_outro:
            if self.edition == "antigo":
                return ft.Chip(
                    label=ft.Text("Exclusivo do Hinário Antigo", size=12),
                    leading=ft.Icon(
                        ft.Icons.AUTO_AWESOME, size=15, color=ft.Colors.PURPLE_300
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    tooltip="Este hino pertence exclusivamente à edição tradicional de 1996.",
                )
            elif status == "NOVO_INEDITO":
                return ft.Chip(
                    label=ft.Text("Inédito no Novo Hinário", size=12),
                    leading=ft.Icon(
                        ft.Icons.AUTO_AWESOME, size=15, color=ft.Colors.PURPLE_300
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    tooltip="Este hino foi adicionado exclusivamente na nova edição.",
                )
            return None

        if status == "IDENTICO":
            return ft.Chip(
                label=ft.Text(f"{nome_outro} #{num_outro} (Letra Idêntica)", size=12),
                leading=ft.Icon(
                    ft.Icons.CHECK_CIRCLE_OUTLINE, size=15, color=ft.Colors.GREEN_400
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                tooltip=f"Letra idêntica ao {nome_outro}. Clique para alternar.",
                on_click=lambda e: self._on_chip_comparativo_click(page),
            )
        elif status == "MODIFICADO":
            resumo = self.comparativo.resumo_alteracoes or "Letra Modificada"
            return ft.Chip(
                label=ft.Text(
                    f"{nome_outro} #{num_outro} ({resumo})",
                    size=12,
                    weight=ft.FontWeight.W_500,
                ),
                leading=ft.Icon(
                    ft.Icons.CHANGE_CIRCLE, size=15, color=ft.Colors.AMBER_400
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                tooltip=f"Letra modificada em relação ao {nome_outro}. Clique para ver alterações.",
                on_click=lambda e: self._on_chip_comparativo_click(page),
            )
        elif status == "NOVO_INEDITO" and self.edition == "novo":
            return ft.Chip(
                label=ft.Text("Inédito no Novo Hinário", size=12),
                leading=ft.Icon(
                    ft.Icons.AUTO_AWESOME, size=15, color=ft.Colors.PURPLE_300
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                tooltip="Este hino foi adicionado exclusivamente na nova edição.",
            )
        return None

    def _on_chip_comparativo_click(self, page: ft.Page) -> None:
        """Manipula o clique no chip comparativo alternando o modo de visualização."""
        if not self.comparativo:
            return
        if self.comparativo.status_comparacao == "MODIFICADO":
            self.selected_view_mode = "comparacao"
        else:
            other_mode = "antigo" if self.edition == "novo" else "novo"
            if self.selected_view_mode == other_mode:
                self.selected_view_mode = self.edition
            else:
                self.selected_view_mode = other_mode

        if self.segmented_button:
            self.segmented_button.selected = [self.selected_view_mode]
        self._update_content_view(page)

    def _create_edition_segments(self) -> list[ft.Segment]:
        """Gera os segmentos de alternância entre as edições (Novo e Antigo)."""
        segments: list[ft.Segment] = []
        if self.edition == "novo":
            segments.append(
                ft.Segment(
                    value="novo",
                    label=ft.Text("Novo Hinário", size=12),
                    icon=ft.Icon(ft.Icons.MUSIC_NOTE, size=15),
                )
            )
            if self.comparativo and self.comparativo.numero_antigo:
                segments.append(
                    ft.Segment(
                        value="antigo",
                        label=ft.Text(
                            f"Antigo #{self.comparativo.numero_antigo}", size=12
                        ),
                        icon=ft.Icon(ft.Icons.HISTORY_EDU, size=15),
                    )
                )
        else:
            segments.append(
                ft.Segment(
                    value="antigo",
                    label=ft.Text("Hinário Tradicional", size=12),
                    icon=ft.Icon(ft.Icons.HISTORY_EDU, size=15),
                )
            )
            if self.comparativo and self.comparativo.numero_novo:
                segments.append(
                    ft.Segment(
                        value="novo",
                        label=ft.Text(f"Novo #{self.comparativo.numero_novo}", size=12),
                        icon=ft.Icon(ft.Icons.MUSIC_NOTE, size=15),
                    )
                )
        return segments

    def _build_segmented_button(self, page: ft.Page) -> ft.Control | None:
        """Gera a barra de alternância (SegmentedButton) entre Novo, Antigo, Comparação e Texto Bíblico."""
        if not self.comparativo:
            return None

        has_counterpart = bool(
            self.comparativo.numero_antigo
            if self.edition == "novo"
            else self.comparativo.numero_novo
        )
        is_modificado = self.comparativo.status_comparacao == "MODIFICADO"
        if not (has_counterpart or is_modificado):
            return None

        segments = self._create_edition_segments()
        if is_modificado:
            segments.append(
                ft.Segment(
                    value="comparacao",
                    label=ft.Text("Comparar Mudanças", size=12),
                    icon=ft.Icon(ft.Icons.COMPARE_ARROWS, size=15),
                )
            )

        has_biblia = bool(
            (
                self.current_hino
                and self.current_hino.texto_base
                and self.current_hino.texto_base.strip()
            )
            or self.relacionados.get("textos_biblicos")
        )
        if has_biblia:
            segments.append(
                ft.Segment(
                    value="biblia",
                    label=ft.Text("Texto Bíblico", size=12),
                    icon=ft.Icon(ft.Icons.MENU_BOOK, size=15),
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
            padding=ft.Padding.only(top=0, bottom=12, left=10, right=10),
            alignment=ft.Alignment.CENTER,
        )

    def _on_segment_change(self, page: ft.Page, selected) -> None:
        """Trata a seleção de abas no SegmentedButton."""
        if selected:
            self.selected_view_mode = next(iter(selected))
            if self.segmented_button:
                self.segmented_button.selected = [self.selected_view_mode]
            if self.selected_view_mode == "biblia" and not self.current_biblia_passagem:
                if hasattr(page, "run_task"):
                    page.run_task(self._carregar_biblia_passagem, page)
                else:
                    self._create_background_task(self._carregar_biblia_passagem(page))
            self._update_content_view(page)

    def _render_current_mode_content(self) -> ft.Control:
        """Retorna o controle de conteúdo de acordo com o modo ativo."""
        if self.selected_view_mode == "comparacao":
            return self._build_comparacao_content()
        elif (self.edition == "novo" and self.selected_view_mode == "antigo") or (
            self.edition == "antigo" and self.selected_view_mode == "novo"
        ):
            return self._build_outro_content()
        elif self.selected_view_mode == "biblia":
            return self._build_biblia_content()
        return self.letra_text or ft.Text("")

    async def _on_inline_biblia_ref_selected(self, e, ref_target: str) -> None:
        """Manipula a seleção de uma referência bíblica alternativa na visualização inline."""
        if self.active_biblia_ref != ref_target:
            self.active_biblia_ref = ref_target
            self.is_biblia_full_chapter = False
            await self._carregar_biblia_passagem(self.page)

    def _build_biblia_inline_toolbar(self, accent_color: str) -> ft.Container:
        """Gera a barra de ferramentas do leitor bíblico inline."""
        ref_title = ft.Text(
            (
                self.current_biblia_passagem.referencia
                if self.current_biblia_passagem
                else self.active_biblia_ref
            ),
            size=18,
            weight=ft.FontWeight.BOLD,
            color=accent_color,
        )
        versoes_disponiveis = self.biblia_repository.get_available_versions()

        async def _on_versao_changed_inline(e):
            nova_versao = e.control.value
            if not nova_versao:
                return
            self.selected_biblia_version = nova_versao
            self.biblia_repository.set_version(nova_versao)
            self._save_pref_task = self._create_background_task(
                self._save_preferences()
            )
            await self._carregar_biblia_passagem(self.page)

        version_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option(key=v, text=v) for v in versoes_disponiveis],
            value=self.selected_biblia_version,
            width=92,
            height=36,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=2),
            dense=True,
            border_radius=8,
            tooltip="Versão da Bíblia",
            on_select=lambda e: (
                self.page.run_task(_on_versao_changed_inline, e) if self.page else None
            ),
        )

        async def _copiar_passagem_inline(e):
            passagem = self.current_biblia_passagem
            if not passagem or not passagem.versiculos:
                return
            texto_copia = f"{passagem.texto_formatado}\n\n({passagem.referencia} - {self.selected_biblia_version})"
            try:
                await ft.Clipboard().set(texto_copia)
            except Exception:
                pass
            if self.page:
                self._show_snackbar(
                    self.page, f"Passagem '{passagem.referencia}' copiada!"
                )

        copy_btn = ft.OutlinedButton(
            "Copiar",
            icon=ft.Icons.CONTENT_COPY,
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                text_style=ft.TextStyle(size=12),
            ),
            tooltip="Copiar passagem com referência para a área de transferência",
            on_click=lambda e: (
                self.page.run_task(_copiar_passagem_inline, e) if self.page else None
            ),
        )

        async def _toggle_capitulo_inline(e):
            self.is_biblia_full_chapter = not self.is_biblia_full_chapter
            await self._carregar_biblia_passagem(self.page)

        chapter_toggle_btn = ft.OutlinedButton(
            (
                BTN_APENAS_VERSICULOS
                if self.is_biblia_full_chapter
                else BTN_CAPITULO_COMPLETO
            ),
            icon=(
                ft.Icons.FILTER_LIST
                if self.is_biblia_full_chapter
                else ft.Icons.AUTO_STORIES
            ),
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                text_style=ft.TextStyle(size=12),
            ),
            tooltip="Alternar entre versículos do hino e o capítulo completo",
            on_click=lambda e: (
                self.page.run_task(_toggle_capitulo_inline, e) if self.page else None
            ),
        )

        def _voltar_letra(e):
            self.selected_view_mode = self.edition
            self._update_content_view(self.page)

        left_toolbar_controls: list[ft.Control] = []
        if self.segmented_button is None:
            left_toolbar_controls.append(
                ft.OutlinedButton(
                    "Voltar ao Hino",
                    icon=ft.Icons.ARROW_BACK,
                    style=ft.ButtonStyle(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        text_style=ft.TextStyle(size=12),
                    ),
                    tooltip="Voltar para a letra do hino",
                    on_click=_voltar_letra,
                )
            )
        left_toolbar_controls.append(ref_title)

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Row(
                        controls=left_toolbar_controls,
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                    ),
                    ft.Row(
                        controls=[chapter_toggle_btn, version_dropdown, copy_btn],
                        spacing=6,
                        wrap=True,
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=12,
            padding=ft.Padding.symmetric(vertical=8, horizontal=12),
            margin=ft.Margin.only(bottom=8),
        )

    def _build_biblia_inline_chips(
        self, all_refs: list[str], accent_color: str
    ) -> list[ft.Control]:
        """Gera a linha de chips de referências bíblicas na visualização inline."""
        if len(all_refs) <= 1:
            return []
        ref_chips: list[ft.Control] = []
        for r in all_refs:
            is_active = r == self.active_biblia_ref
            is_base = bool(
                self.current_hino
                and self.current_hino.texto_base
                and r == self.current_hino.texto_base.strip()
            )
            label_prefix = "✦ " if is_base else ""
            label_suffix = " (Base)" if is_base else ""

            ref_chips.append(
                ft.Container(
                    content=ft.Text(
                        f"{label_prefix}{r}{label_suffix}",
                        size=11,
                        weight=(
                            ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL
                        ),
                        color=(
                            accent_color if is_active else ft.Colors.ON_SURFACE_VARIANT
                        ),
                    ),
                    bgcolor=(
                        ft.Colors.with_opacity(0.18, accent_color)
                        if is_active
                        else ft.Colors.SURFACE_CONTAINER_HIGHEST
                    ),
                    border=ft.Border.all(1, accent_color) if is_active else None,
                    border_radius=12,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    on_click=lambda e, ref=r: (
                        self.page.run_task(self._on_inline_biblia_ref_selected, e, ref)
                        if self.page
                        else None
                    ),
                    ink=True,
                )
            )

        return [
            ft.Container(
                content=ft.Row(
                    controls=ref_chips, scroll=ft.ScrollMode.AUTO, spacing=6
                ),
                padding=ft.Padding.only(bottom=10),
            )
        ]

    def _build_biblia_inline_verses_content(
        self, f_size: int, font_fam: str | None, verse_num_color: str
    ) -> ft.Control:
        """Gera o corpo dos versículos ou container de carregamento/erro."""
        if self._biblia_loading:
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.ProgressRing(width=36, height=36, stroke_width=3),
                        ft.Text(
                            "Carregando passagem bíblica...",
                            size=14,
                            color=ft.Colors.GREY_400,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=12,
                ),
                padding=ft.Padding.symmetric(vertical=40),
                alignment=ft.Alignment.CENTER,
            )

        if self.current_biblia_passagem and self.current_biblia_passagem.versiculos:
            verse_controls = self._build_verse_rows(
                self.current_biblia_passagem.versiculos,
                f_size,
                font_fam,
                verse_num_color,
            )
            return ft.Column(
                controls=verse_controls,
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            )

        return self._build_biblia_error_container(
            self.active_biblia_ref or "", self.selected_biblia_version
        )

    def _build_biblia_content(self) -> ft.Control:
        """Gera a visualização bíblica imersiva em tela cheia com tipografia e ferramentas completas."""
        if not self.active_biblia_ref:
            if self.current_hino and self.current_hino.texto_base:
                self.active_biblia_ref = self.current_hino.texto_base.strip()
            elif self.relacionados.get("textos_biblicos"):
                self.active_biblia_ref = self.relacionados["textos_biblicos"][0].strip()

        if not self.active_biblia_ref:
            return ft.Container(
                content=ft.Text(
                    "Nenhuma passagem bíblica associada a este hino.", italic=True
                ),
                padding=20,
                alignment=ft.Alignment.CENTER,
            )

        accent_color = (
            ft.Colors.PURPLE_200 if self.edition == "antigo" else ft.Colors.BLUE_200
        )
        verse_num_color = (
            ft.Colors.PURPLE_300 if self.edition == "antigo" else ft.Colors.TEAL_300
        )
        font_fam = FONT_FAMILY_MAP.get(self.selected_font)
        f_size = self.font_size

        all_refs = self._gather_hino_biblical_refs(
            self.current_hino, self.active_biblia_ref
        )
        header_toolbar = self._build_biblia_inline_toolbar(accent_color)
        chips_row = self._build_biblia_inline_chips(all_refs, accent_color)
        verses_content = self._build_biblia_inline_verses_content(
            f_size, font_fam, verse_num_color
        )

        return ft.Column(
            controls=[
                header_toolbar,
                *chips_row,
                verses_content,
            ],
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    def _update_content_view(self, page: ft.Page | None) -> None:
        """Atualiza o conteúdo dinâmico da letra/comparação."""
        if self.content_container:
            self.content_container.content = self._render_current_mode_content()
        if page:
            page.update()

    def _extract_counterpart_info(self) -> tuple[str, str, str, str]:
        """Extrai metadados (nome da edição, número, título e letra) da edição alternativa."""
        is_novo = self.edition == "novo"
        edition_name = (
            "Edição Anterior (Hinário Tradicional)"
            if is_novo
            else "Edição Atual (Hinário Novo 2022)"
        )

        if self.hino_antigo:
            num = str(self.hino_antigo.numero or "")
            titulo = self.hino_antigo.titulo or ""
            letra = self.hino_antigo.letra or "Letra não disponível no banco local."
            return edition_name, num, titulo, letra

        if self.comparativo:
            num_val = (
                self.comparativo.numero_antigo
                if is_novo
                else self.comparativo.numero_novo
            )
            titulo_val = (
                self.comparativo.titulo_antigo
                if is_novo
                else self.comparativo.titulo_novo
            )
            fallback_title = "Hino Antigo" if is_novo else "Hino Novo"
            return (
                edition_name,
                str(num_val or ""),
                titulo_val or fallback_title,
                "Letra não disponível no banco local.",
            )

        return edition_name, "", "", ""

    def _build_outro_content(self) -> ft.Control:
        """Gera a visualização da letra da outra edição do Hinário."""
        edition_name, num, titulo, letra = self._extract_counterpart_info()

        if not letra or not titulo:
            return ft.Container(
                content=ft.Text(
                    "Hino correspondente não encontrado.",
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
                                f"Hino {num} - {titulo}",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                text_align=ft.TextAlign.CENTER,
                                color=ft.Colors.AMBER_200,
                            ),
                            ft.Text(
                                edition_name,
                                size=12,
                                italic=True,
                                text_align=ft.TextAlign.CENTER,
                                color=ft.Colors.GREY_400,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                    ),
                    padding=ft.Padding.only(bottom=16),
                ),
                ft.Text(
                    letra,
                    size=self.font_size,
                    text_align=ft.TextAlign.CENTER,
                    weight=ft.FontWeight.W_400,
                    font_family=font_fam,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    @staticmethod
    def _create_diff_stat_chip(
        icon: Any, label: str, color: Any, is_surface: bool = False
    ) -> ft.Container:
        """Cria um chip individual de estatística de diff."""
        text_color = color if not is_surface else ft.Colors.GREY_400
        bgcolor = (
            ft.Colors.SURFACE_CONTAINER_HIGHEST
            if is_surface
            else ft.Colors.with_opacity(0.12, color)
        )
        weight = ft.FontWeight.BOLD if not is_surface else ft.FontWeight.NORMAL
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, size=13, color=color),
                    ft.Text(label, size=11, weight=weight, color=text_color),
                ],
                spacing=4,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=bgcolor,
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        )

    def _build_diff_stats_summary(
        self, stats: EstatisticasDiff | None, simil_pct: float
    ) -> ft.Container:
        """Constrói o cabeçalho com barra de similaridade e chips de estatísticas do diff."""
        summary_chips: list[ft.Control] = []
        if stats:
            if stats.linhas_alteradas > 0:
                summary_chips.append(
                    self._create_diff_stat_chip(
                        ft.Icons.EDIT,
                        f"{stats.linhas_alteradas} alterada(s)",
                        ft.Colors.AMBER,
                    )
                )
            if stats.linhas_adicionadas > 0:
                summary_chips.append(
                    self._create_diff_stat_chip(
                        ft.Icons.ADD_CIRCLE_OUTLINE,
                        f"+{stats.linhas_adicionadas} adicionada(s)",
                        ft.Colors.GREEN,
                    )
                )
            if stats.linhas_removidas > 0:
                summary_chips.append(
                    self._create_diff_stat_chip(
                        ft.Icons.REMOVE_CIRCLE_OUTLINE,
                        f"-{stats.linhas_removidas} removida(s)",
                        ft.Colors.RED,
                    )
                )
            if stats.linhas_iguais > 0:
                summary_chips.append(
                    self._create_diff_stat_chip(
                        ft.Icons.CHECK,
                        f"{stats.linhas_iguais} inalterada(s)",
                        ft.Colors.GREY_400,
                        is_surface=True,
                    )
                )

        chips_row = (
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
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.ANALYTICS_OUTLINED,
                                size=16,
                                color=ft.Colors.BLUE_300,
                            ),
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
                    *chips_row,
                ],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=12,
            padding=ft.Padding.symmetric(vertical=10, horizontal=14),
            margin=ft.Margin.only(bottom=15),
        )

    def _build_diff_block_control(
        self, b: BlocoDiff, font_fam: str | None
    ) -> ft.Control | None:
        """Constrói a representação visual de um bloco de diff (igual, modificado, adicionado, removido)."""
        if b.tipo == "igual":
            if not b.texto:
                return None
            return ft.Container(
                content=ft.Text(
                    b.texto,
                    size=self.font_size,
                    font_family=font_fam,
                    text_align=ft.TextAlign.CENTER,
                ),
                padding=ft.Padding.symmetric(vertical=2, horizontal=8),
                alignment=ft.Alignment.CENTER,
            )

        if b.tipo == "modificado":
            antigo_lines = b.antigo or []
            novo_lines = b.novo or []
            mod_controls: list[ft.Control] = []

            if antigo_lines:
                mod_controls.append(
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(
                                            ft.Icons.REMOVE_CIRCLE_OUTLINE,
                                            size=13,
                                            color=ft.Colors.RED_400,
                                        ),
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
                        margin=ft.Margin.symmetric(vertical=2),
                    )
                )

            if novo_lines:
                mod_controls.append(
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(
                                            ft.Icons.ADD_CIRCLE_OUTLINE,
                                            size=13,
                                            color=ft.Colors.GREEN_400,
                                        ),
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
                        margin=ft.Margin.symmetric(vertical=2),
                    )
                )

            return ft.Container(
                content=ft.Column(controls=mod_controls, spacing=4),
                padding=ft.Padding.symmetric(vertical=4),
            )

        if b.tipo == "adicionado":
            return ft.Container(
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
                margin=ft.Margin.symmetric(vertical=2),
            )

        if b.tipo == "removido":
            return ft.Container(
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
                margin=ft.Margin.symmetric(vertical=2),
            )

        return None

    def _build_comparacao_content(self) -> ft.Control:
        """Gera a visualização diff Antes e Depois esteticamente adaptável e acessível."""
        if not self.comparativo:
            return ft.Text("Dados de comparação não disponíveis.", italic=True)

        stats, blocos = self.comparativo.get_parsed_diff()
        font_fam = FONT_FAMILY_MAP.get(self.selected_font)

        header_summary = self._build_diff_stats_summary(
            stats, self.comparativo.similaridade_pct
        )
        diff_controls: list[ft.Control] = [header_summary]

        if not blocos:
            diff_controls.append(
                ft.Text(
                    self.comparativo.diff_texto
                    or "Nenhuma diferença detalhada encontrada.",
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
            block_ctrl = self._build_diff_block_control(b, font_fam)
            if block_ctrl:
                diff_controls.append(block_ctrl)

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
            self.fav_icon.icon = (
                ft.Icons.FAVORITE if self.is_fav else ft.Icons.FAVORITE_BORDER
            )
            self.fav_icon.icon_color = ft.Colors.RED_400 if self.is_fav else None
            self.fav_icon.tooltip = "Desfavoritar" if self.is_fav else "Favoritar"

    async def _toggle_favorito(self, page: ft.Page, hino: Hino | None = None) -> None:
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

    async def _open_youtube_link(self, page: ft.Page, hino: Hino | None = None) -> None:
        """Abre o link externo do YouTube no navegador ou app nativo."""
        target_hino = hino or self.current_hino
        if (
            not target_hino
            or not target_hino.link_video
            or not target_hino.link_video.strip()
        ):
            self._show_snackbar(
                page, "Este hino não possui link do YouTube cadastrado."
            )
            return

        url = target_hino.link_video.strip()
        try:
            await ft.UrlLauncher().launch_url(url)
        except Exception:
            self._show_snackbar(page, "Não foi possível abrir o link do YouTube.")

    def _show_accessibility_modal(self, page: ft.Page) -> None:
        self.font_size_text = ft.Text(f"{self.font_size}pt", weight=ft.FontWeight.BOLD)

        font_radio_group = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(
                        value=DEFAULT_FONT_FAMILY,
                        label=f"{DEFAULT_FONT_FAMILY} (Sans-Serif)",
                    ),
                    ft.Radio(
                        value=TIMES_NEW_ROMAN_FONT_FAMILY,
                        label=f"Serifada ({TIMES_NEW_ROMAN_FONT_FAMILY})",
                    ),
                    ft.Radio(
                        value=HELVETICA_FONT_FAMILY,
                        label=f"{HELVETICA_FONT_FAMILY} (Standard)",
                    ),
                    ft.Radio(
                        value=MONTSERRAT_FONT_FAMILY,
                        label=f"{MONTSERRAT_FONT_FAMILY} (Standard)",
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
                                ft.Text(
                                    "Acessibilidade de Fonte",
                                    weight=ft.FontWeight.BOLD,
                                    size=18,
                                ),
                                ft.IconButton(
                                    ft.Icons.CLOSE,
                                    on_click=lambda ev: page.pop_dialog(),
                                ),
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
                                ft.TextButton(
                                    "Resetar", on_click=lambda e: self._reset_font(page)
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            wrap=True,
                            spacing=6,
                            run_spacing=6,
                        ),
                        ft.Divider(),
                        ft.Text(
                            "Família de Fonte:", weight=ft.FontWeight.BOLD, size=14
                        ),
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
        if (
            hino.autor_letra
            and hino.autor_musica
            and hino.autor_letra == hino.autor_musica
        ):
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
                            ft.Text(
                                label,
                                weight=ft.FontWeight.BOLD,
                                size=12,
                                color=ft.Colors.BLUE_200,
                            ),
                            ft.Text(val, size=14),
                        ],
                        spacing=2,
                    )
                )
        return items

    def _build_texto_base_info_control(
        self, page: ft.Page, hino: Hino
    ) -> ft.Control | None:
        """Gera o controle de texto base bíblico do hino."""
        if not (hino.texto_base and hino.texto_base.strip()):
            return None
        return ft.Column(
            controls=[
                ft.Text(
                    "Texto Base Bíblico:",
                    weight=ft.FontWeight.BOLD,
                    size=12,
                    color=ft.Colors.BLUE_200,
                ),
                ft.Chip(
                    label=ft.Text(hino.texto_base, size=12),
                    leading=ft.Icon(
                        ft.Icons.MENU_BOOK_OUTLINED, size=15, color=ft.Colors.GREEN_400
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    tooltip=TOOLTIP_LER_PASSAGEM_BIBLICA,
                    on_click=lambda e, ref=hino.texto_base: self._on_biblia_click(
                        page, ref
                    ),
                ),
            ],
            spacing=4,
        )

    def _build_category_info_control(
        self, page: ft.Page, hino: Hino
    ) -> ft.Control | None:
        """Gera a seção de chips de categoria e subcategoria."""
        cat_chips: list[ft.Control] = []
        if hino.categoria and hino.categoria.strip():
            cat_chips.append(
                ft.Chip(
                    label=ft.Text(hino.categoria, size=12),
                    leading=ft.Icon(
                        ft.Icons.FOLDER_OUTLINED, size=16, color=ft.Colors.BLUE_400
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    on_click=lambda e, c=hino.categoria: self._trigger_search_navigation(
                        page, c
                    ),
                )
            )
        if hino.subcategoria and hino.subcategoria.strip():
            cat_chips.append(
                ft.Chip(
                    label=ft.Text(hino.subcategoria, size=12),
                    leading=ft.Icon(
                        ft.Icons.FOLDER_SPECIAL_OUTLINED,
                        size=16,
                        color=ft.Colors.BLUE_300,
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    on_click=lambda e, sc=hino.subcategoria: self._trigger_search_navigation(
                        page, sc
                    ),
                )
            )
        if not cat_chips:
            return None
        return ft.Column(
            controls=[
                ft.Text(
                    "Categoria:",
                    weight=ft.FontWeight.BOLD,
                    size=12,
                    color=ft.Colors.BLUE_200,
                ),
                ft.Row(controls=cat_chips, wrap=True, spacing=6, run_spacing=6),
            ],
            spacing=4,
        )

    def _build_themes_info_control(self, page: ft.Page) -> ft.Control | None:
        """Gera a seção de chips dos temas relacionados."""
        temas = self.relacionados.get("temas", [])
        if not temas:
            return None
        tema_chips: list[ft.Control] = [
            ft.Chip(
                label=ft.Text(t, size=11),
                leading=ft.Icon(
                    ft.Icons.LABEL_OUTLINED, size=15, color=ft.Colors.AMBER_400
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                on_click=lambda e, tema=t: self._trigger_search_navigation(page, tema),
            )
            for t in temas
        ]
        return ft.Column(
            controls=[
                ft.Text(
                    "Temas Relacionados:",
                    weight=ft.FontWeight.BOLD,
                    size=12,
                    color=ft.Colors.AMBER_200,
                ),
                ft.Row(controls=tema_chips, wrap=True, spacing=6, run_spacing=6),
            ],
            spacing=4,
        )

    def _build_biblical_texts_info_control(
        self, page: ft.Page,
    ) -> ft.Control | None:
        """Gera a seção de chips dos textos bíblicos relacionados."""
        textos_biblicos = self.relacionados.get("textos_biblicos", [])
        if not textos_biblicos:
            return None
        texto_chips: list[ft.Control] = [
            ft.Chip(
                label=ft.Text(tb, size=11),
                leading=ft.Icon(
                    ft.Icons.MENU_BOOK_OUTLINED, size=15, color=ft.Colors.GREEN_400
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                tooltip=TOOLTIP_LER_PASSAGEM_BIBLICA,
                on_click=lambda e, ref=tb: self._on_biblia_click(page, ref),
            )
            for tb in textos_biblicos
        ]
        return ft.Column(
            controls=[
                ft.Text(
                    "Textos Bíblicos Relacionados:",
                    weight=ft.FontWeight.BOLD,
                    size=12,
                    color=ft.Colors.GREEN_200,
                ),
                ft.Row(controls=texto_chips, wrap=True, spacing=6, run_spacing=6),
            ],
            spacing=4,
        )

    def _build_comparativo_info_control(self) -> ft.Control | None:
        """Gera a seção informativa sobre a correspondência com o Hinário Antigo."""
        if not self.comparativo:
            return None

        items: list[ft.Control] = []
        if self.comparativo.status_comparacao == "NOVO_INEDITO":
            items.append(
                ft.Text(
                    "Hino inédito inserido nesta edição do hinário.",
                    size=13,
                    color=ft.Colors.PURPLE_200,
                )
            )
        elif self.comparativo.numero_antigo:
            titulo_ant = self.comparativo.titulo_antigo or "(mesmo título)"
            items.append(
                ft.Row(
                    controls=[
                        ft.Text(
                            "Hinário Antigo:",
                            weight=ft.FontWeight.BOLD,
                            size=12,
                            color=ft.Colors.BLUE_200,
                        ),
                        ft.Text(
                            f"Hino #{self.comparativo.numero_antigo} - {titulo_ant}",
                            size=13,
                        ),
                    ],
                    spacing=6,
                    wrap=True,
                )
            )
            if self.comparativo.similaridade_pct is not None:
                items.append(
                    ft.Row(
                        controls=[
                            ft.Text(
                                "Similaridade da Letra:",
                                weight=ft.FontWeight.BOLD,
                                size=12,
                                color=ft.Colors.BLUE_200,
                            ),
                            ft.Text(
                                f"{self.comparativo.similaridade_pct:.1f}%", size=13
                            ),
                        ],
                        spacing=6,
                    )
                )
            if self.comparativo.resumo_alteracoes:
                items.append(
                    ft.Row(
                        controls=[
                            ft.Text(
                                "Resumo:",
                                weight=ft.FontWeight.BOLD,
                                size=12,
                                color=ft.Colors.BLUE_200,
                            ),
                            ft.Text(
                                self.comparativo.resumo_alteracoes, size=13, italic=True
                            ),
                        ],
                        spacing=6,
                    )
                )

        if not items:
            return None

        return ft.Column(
            controls=[
                ft.Text(
                    "Comparativo com Hinário Antigo:",
                    weight=ft.FontWeight.BOLD,
                    size=12,
                    color=ft.Colors.BLUE_200,
                ),
                *items,
            ],
            spacing=4,
        )

    def _show_info_modal(self, page: ft.Page, hino: Hino | None = None) -> None:
        target_hino = hino or self.current_hino
        if not target_hino:
            return

        info_items: list[ft.Control] = [
            ft.Row(
                controls=[
                    ft.Text("Informações do Hino", weight=ft.FontWeight.BOLD, size=18),
                    ft.IconButton(
                        ft.Icons.CLOSE, on_click=lambda ev: page.pop_dialog()
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Divider(),
        ]

        info_items.extend(self._build_info_metadata_items(target_hino))

        for section in (
            self._build_comparativo_info_control(),
            self._build_texto_base_info_control(page, target_hino),
            self._build_category_info_control(page, target_hino),
            self._build_themes_info_control(page),
            self._build_biblical_texts_info_control(page, target_hino),
        ):
            if section:
                info_items.append(section)

        if len(info_items) == 2:
            info_items.append(
                ft.Text(
                    "Nenhum metadado adicional cadastrado para este hino.", italic=True
                )
            )

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
