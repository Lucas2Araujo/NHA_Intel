import asyncio
import inspect
import json
from typing import Any, cast
import urllib.parse

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
from src.views.biblia_view import (
    build_bible_version_button,
    update_bible_version_button,
)
from src.views.settings_dialog import ensure_page_dialogs

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


class _BibliaModalSession:
    """Controlador e construtor do BottomSheet de leitura bíblica."""

    def __init__(
        self,
        view: "HinoView",
        page: ft.Page,
        referencia: str,
        from_info_modal: bool = False,
        hino: Hino | None = None,
    ) -> None:
        self.view = view
        self.page = page
        self.referencia = referencia
        self.from_info_modal = from_info_modal
        self.target_hino = hino or getattr(view, "current_hino", None)
        self.current_ref = referencia
        self.is_full_chapter = False
        self.font_size = view.font_size
        self.current_passagem: PassagemBiblica | None = None
        self.is_expanded = False

        self.accent_color = (
            view.theme_service.get_accent_color()
            if view.theme_service
            else ft.Colors.PRIMARY
        )
        self.verse_num_color = self.accent_color

        versoes = view.biblia_repository.get_available_versions()
        if (
            not view.selected_biblia_version
            or view.selected_biblia_version not in versoes
        ):
            view.selected_biblia_version = versoes[0] if versoes else "ARA"
        self.selected_version = view.selected_biblia_version

        self.all_refs = view._gather_hino_biblical_refs(self.target_hino, referencia)

        self._build_components()

    @property
    def is_simplified_bible(self) -> bool:
        return self.view.is_simplified_bible

    def _build_components(self) -> None:
        self.title_text = ft.Text(
            self.current_ref,
            weight=ft.FontWeight.BOLD,
            size=17,
            color=self.accent_color,
            expand=True,
        )

        self.loading_indicator = ft.Container(
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

        self.verses_container = ft.Column(
            controls=[self.loading_indicator],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=8,
        )

        self.version_btn = build_bible_version_button(
            biblia_repository=self.view.biblia_repository,
            current_version=self.selected_version,
            on_version_selected=self._on_versao_selected,
            theme_service=self.view.theme_service,
        )
        if self.is_simplified_bible:
            self.version_btn.visible = False
            self.version_btn.disabled = True
        self.copy_btn = ft.OutlinedButton(
            "Copiar",
            icon=ft.Icons.CONTENT_COPY,
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                text_style=ft.TextStyle(size=12),
            ),
            tooltip="Copiar passagem com referência para a área de transferência",
            on_click=self._copiar_passagem,
        )

        self.font_indicator = ft.Text(
            f"{self.font_size}pt", size=12, weight=ft.FontWeight.BOLD
        )

        self.font_minus_btn = ft.IconButton(
            ft.Icons.REMOVE_CIRCLE_OUTLINE,
            icon_size=18,
            tooltip="Diminuir tamanho da letra",
            on_click=self._zoom_out,
        )
        self.font_plus_btn = ft.IconButton(
            ft.Icons.ADD_CIRCLE_OUTLINE,
            icon_size=18,
            tooltip="Aumentar tamanho da letra",
            on_click=self._zoom_in,
        )

        self.ref_chips_container = ft.Container()
        self._update_ref_chips()

        self.header_row = ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.MENU_BOOK, color=self.accent_color, size=22),
                        self.title_text,
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    expand=True,
                ),
                self.version_btn,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        )

        self.action_bar = self.view._build_biblia_modal_action_bar(
            self.copy_btn,
            self.font_minus_btn,
            self.font_indicator,
            self.font_plus_btn,
        )

        button_label = "Voltar para Informações" if self.from_info_modal else "Fechar"
        button_icon = ft.Icons.ARROW_BACK if self.from_info_modal else ft.Icons.CLOSE
        fechar_btn = ft.TextButton(
            button_label, icon=button_icon, on_click=self._close_dialog
        )
        abrir_biblia_btn = ft.FilledButton(
            "Abrir na Bíblia",
            icon=ft.Icons.OPEN_IN_NEW,
            on_click=self._abrir_na_biblia_completa,
        )
        self.footer_row = ft.Row(
            controls=[
                fechar_btn,
                abrir_biblia_btn,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.modal_body = ft.Container(
            content=ft.Column(
                controls=[
                    self.header_row,
                    self.ref_chips_container,
                    ft.Divider(height=1),
                    ft.Container(
                        content=self.verses_container,
                        expand=True,
                        padding=ft.Padding.symmetric(vertical=4),
                    ),
                    ft.Divider(height=1),
                    self.action_bar,
                    ft.Divider(height=1),
                    self.footer_row,
                ],
                spacing=6,
                expand=True,
            ),
            padding=ft.Padding.only(left=20, top=16, right=20, bottom=24),
            height=(
                min(float(self.page.height) * 0.85, 620)
                if (self.page and isinstance(self.page.height, (int, float)))
                else 520
            ),
        )

    def _render_loaded_verses(self) -> None:
        if not self.current_passagem or not self.current_passagem.versiculos:
            return
        font_fam = FONT_FAMILY_MAP.get(self.view.selected_font)
        self.verses_container.controls = self.view._build_verse_rows(
            self.current_passagem.versiculos,
            self.font_size,
            font_fam,
            self.verse_num_color,
        )

    async def carregar_versiculos(self, versao_alvo: str) -> None:
        self.verses_container.controls = [self.loading_indicator]
        self.page.update()

        try:
            if self.is_full_chapter:
                passagem = await self.view.biblia_repository.buscar_capitulo_completo(
                    self.current_ref, versao=versao_alvo
                )
            else:
                passagem = await self.view.biblia_repository.buscar_passagem(
                    self.current_ref, versao=versao_alvo
                )
        except Exception:
            passagem = None

        self.current_passagem = passagem

        if passagem and passagem.versiculos:
            self.title_text.value = passagem.referencia
            self.copy_btn.disabled = False
            self._render_loaded_verses()
        else:
            self.title_text.value = self.current_ref
            self.copy_btn.disabled = True
            self.verses_container.controls = [
                self.view._build_biblia_error_container(self.current_ref, versao_alvo)
            ]
        self.page.update()

    async def _on_versao_selected(self, nova_versao: str) -> None:
        if not nova_versao:
            return
        self.selected_version = nova_versao
        self.view.selected_biblia_version = nova_versao
        self.view.biblia_repository.set_version(nova_versao)
        update_bible_version_button(
            self.version_btn,
            nova_versao,
            self.view.biblia_repository,
            self._on_versao_selected,
        )
        if self.view._save_pref_task and not self.view._save_pref_task.done():
            self.view._save_pref_task.cancel()
        self.view._save_pref_task = self.view._create_background_task(
            self.view._save_preferences()
        )
        await self.carregar_versiculos(nova_versao)

    async def _on_versao_changed(self, e) -> None:
        nova_versao = getattr(e.control, "value", None)
        if nova_versao:
            await self._on_versao_selected(nova_versao)

    def _close_dialog(self, ev=None) -> None:
        self.page.pop_dialog()
        if self.from_info_modal:
            self.view._show_info_modal(self.page, self.target_hino)

    def _abrir_na_biblia_completa(self, ev=None) -> None:
        """Fecha o modal e dispara a navegação para /biblia com livro, cap, ver e hino_id."""
        self._close_dialog(ev)
        livro = "Sl"
        cap = 1
        ver = 1
        if self.current_passagem:
            livro = self.current_passagem.livro
            cap = self.current_passagem.capitulo
            if self.current_passagem.versiculos:
                ver = self.current_passagem.versiculos[0].numero
        elif self.current_ref:
            parsed = self.view.biblia_repository.parse_referencia(self.current_ref)
            if parsed:
                livro = parsed.get("book_name", "Sl")
                cap = parsed.get("chapter", 1)
                verses = parsed.get("verses")
                ver = verses[0] if verses else 1

        hino_id = (
            self.target_hino.id
            if self.target_hino and self.target_hino.id is not None
            else getattr(self.view, "hino_id", 0)
        )
        route = f"/biblia?livro={urllib.parse.quote(str(livro))}&cap={cap}&ver={ver}&hino_id={hino_id}"
        if hasattr(self.page, "go") and callable(self.page.go):
            self.page.go(route)
        elif hasattr(self.page, "push_route"):
            asyncio.create_task(self.page.push_route(route))

    async def _on_chip_selected(self, e, ref_target: str) -> None:
        if self.current_ref != ref_target:
            self.current_ref = ref_target
            self.is_full_chapter = False
            self._update_ref_chips()
            await self.carregar_versiculos(self.selected_version)

    def _update_ref_chips(self) -> None:
        base_ref = self.target_hino.texto_base if self.target_hino else None
        chips = self.view._build_biblia_modal_ref_chips(
            self.all_refs,
            self.current_ref,
            base_ref,
            self.accent_color,
            self._on_chip_selected,
        )
        self.ref_chips_container.content = (
            ft.Column(controls=chips, spacing=0) if chips else ft.Container()
        )

    async def _copiar_passagem(self, ev=None) -> None:
        passagem = self.current_passagem
        if not passagem or not passagem.versiculos:
            return
        texto_copia = f'"{passagem.texto_formatado}"\n— {passagem.referencia} ({self.selected_version})'
        try:
            await ft.Clipboard().set(texto_copia)
        except Exception:
            pass
        self.view._show_snackbar(
            self.page, f"Passagem '{passagem.referencia} ({self.selected_version})' copiada!"
        )

    def _zoom_in(self, ev=None) -> None:
        if self.font_size < 36:
            self.font_size += 2
            self.font_indicator.value = f"{self.font_size}pt"
            self._render_loaded_verses()
            self.page.update()

    def _zoom_out(self, ev=None) -> None:
        if self.font_size > 12:
            self.font_size -= 2
            self.font_indicator.value = f"{self.font_size}pt"
            self._render_loaded_verses()
            self.page.update()

    async def show(self) -> None:
        bs = ft.BottomSheet(content=self.modal_body)
        ensure_page_dialogs(self.page)
        self.page.show_dialog(bs)
        await self.carregar_versiculos(self.selected_version)


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
        self.inline_version_btn: ft.PopupMenuButton | None = None

        self.animated_container: ft.Container | None = None
        self.header_container: ft.Container | None = None
        self.segmented_container: ft.Container | None = None
        self.edition_feedback_banner: ft.Container | None = None
        self.edition_feedback_text: ft.Text | None = None
        self.edition_feedback_icon: ft.Icon | None = None
        self.scroll_column: ft.Column | None = None
        self.appbar_title: ft.Text | None = None
        self.prev_btn: ft.IconButton | None = None
        self.next_btn: ft.IconButton | None = None
        self.view: ft.View | None = None
        self._is_navigating: bool = False

        # SnackBar singleton reutilizável (evita acúmulo no overlay)
        self._snackbar: ft.SnackBar | None = None

    @property
    def is_simplified_bible(self) -> bool:
        """Informa se a Bíblia está no modo simplificado (sem traduções completas instaladas)."""
        if not self.biblia_repository:
            return True
        versoes = self.biblia_repository.get_available_versions()
        has_installed = getattr(self.biblia_repository, "has_installed_bibles", None)
        return (has_installed() is False if callable(has_installed) else False) or len(versoes) == 0

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
            try:
                conn = await self.hino_repository.db_connection.get_connection()
                await conn.rollback()
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

        results = await asyncio.gather(
            historico_task,
            metadados_task,
            favorito_task,
            comparativo_task,
            return_exceptions=True,
        )
        _, metadados, is_fav, comparativo = results

        self.relacionados = (
            metadados
            if isinstance(metadados, dict)
            else {"temas": [], "textos_biblicos": []}
        )
        self.is_fav = bool(is_fav) if not isinstance(is_fav, Exception) else False
        self.comparativo = (
            comparativo if isinstance(comparativo, HinoComparativo) else None
        )

        if hino.texto_base and hino.texto_base.strip():
            self.active_biblia_ref = hino.texto_base.strip()
        elif self.relacionados.get("textos_biblicos"):
            self.active_biblia_ref = self.relacionados["textos_biblicos"][0].strip()

        await self._resolve_counterpart_hino()

    def _build_header_container(self, page: ft.Page, hino: Hino) -> ft.Container:
        """Constrói a seção de cabeçalho do hino (título e chip de texto base)."""
        accent = (
            self.theme_service.get_accent_color()
            if self.theme_service
            else ft.Colors.PRIMARY
        )
        titulo_text = ft.Text(
            hino.titulo,
            size=22,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
            color=accent,
        )

        header_controls: list[ft.Control] = [titulo_text]
        chips_controls: list[ft.Control] = []

        if hino.texto_base and hino.texto_base.strip():
            chips_controls.append(
                ft.Chip(
                    label=ft.Text(hino.texto_base, size=12),
                    leading=ft.Icon(
                        ft.Icons.MENU_BOOK_OUTLINED, size=15, color=accent
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    tooltip=TOOLTIP_LER_PASSAGEM_BIBLICA,
                    on_click=lambda e, ref=hino.texto_base: self._on_biblia_click(
                        page, ref
                    ),
                )
            )

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

    def _build_view_structure(self, page: ft.Page, hino: Hino) -> None:
        """Inicializa os componentes visuais principais da tela do hino."""
        self.letra_text = ft.Text(
            hino.letra if hino.letra else MSG_LETRA_NAO_DISPONIVEL,
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
            on_click=lambda e: page.run_task(self._toggle_favorito, page, self.current_hino),
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
            on_click=lambda e: page.run_task(self._open_youtube_link, page, self.current_hino),
        )

        self.appbar_title = ft.Text(f"Hino {hino.numero}", weight=ft.FontWeight.BOLD)
        self.header_container = self._build_header_container(page, hino)

        segmented_btn = self._build_segmented_button(page)
        self.segmented_container = ft.Container(
            content=segmented_btn,
            visible=segmented_btn is not None,
        )

        column_controls: list[ft.Control] = [
            self.header_container,
            self.segmented_container,
            ft.Divider(height=1),
            self.content_container,
        ]

        self.scroll_column = ft.Column(
            controls=column_controls,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        self.animated_container = ft.Container(
            content=self.scroll_column,
            expand=True,
            padding=0,
            offset=ft.Offset(0, 0),
            animate_offset=ft.Animation(220, ft.AnimationCurve.EASE_OUT_CUBIC),
        )

    async def build(self, page: ft.Page) -> ft.View:
        self.page = page
        self.page.on_resize = self._on_page_resize

        hino: Hino | None = await self.hino_repository.get_by_id(self.hino_id)
        if hino is None:
            return self._build_not_found_view(page)

        self.current_hino = hino
        await self._init_data_and_preferences(page, hino)
        self._build_view_structure(page, hino)
        prev_btn, next_btn = self._build_nav_buttons(page)

        if self.theme_service:
            self.theme_service.apply_theme(page, edition=self.edition)

        async def _go_back(e):
            try:
                if hasattr(page, "pop_dialog") and page.pop_dialog():
                    return
            except Exception:
                pass

            if hasattr(page, "on_view_pop") and page.on_view_pop:
                res = cast(Any, page.on_view_pop)(None)
                if inspect.iscoroutine(res):
                    await res
            elif len(page.views) > 1:
                page.views.pop()
                top_view = page.views[-1]
                page.route = top_view.route or f"/{self.edition}"
                if hasattr(page, "on_route_change") and page.on_route_change:
                    res = cast(Any, page.on_route_change)(None)
                    if inspect.iscoroutine(res):
                        await res
                else:
                    await page.push_route(page.route)
            else:
                await page.push_route(f"/{self.edition}")

        self.view = ft.View(
            route=f"/{self.edition}/hino/{self.hino_id}",
            bgcolor=ft.Colors.SURFACE,
            appbar=ft.AppBar(
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=_go_back),
                title=self.appbar_title,
                center_title=True,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                actions=[
                    prev_btn,
                    next_btn,
                    self.fav_icon,
                    ft.IconButton(
                        icon=ft.Icons.INFO_OUTLINE,
                        tooltip="Informações do Hino",
                        on_click=lambda e: self._show_info_modal(page, self.current_hino),
                    ),
                ],
            ),
            controls=[
                ft.SafeArea(
                    maintain_bottom_view_padding=True,
                    content=self.animated_container,
                    expand=True,
                ),
            ],
            bottom_appbar=self._build_bottom_appbar(page, self.youtube_btn),
        )
        return self.view

    def _get_adjacent_hino_id(self, offset: int) -> int | None:
        """Retorna o ID do hino adjacente dado um deslocamento (+1 para próximo, -1 para anterior)."""
        if not self.hino_ids_list or self.hino_id not in self.hino_ids_list:
            return None
        idx = self.hino_ids_list.index(self.hino_id) + offset
        if 0 <= idx < len(self.hino_ids_list):
            return self.hino_ids_list[idx]
        return None

    async def _navigate_to_adjacent(self, page: ft.Page, offset: int, direction: str) -> None:
        """Navega para o hino adjacente com animação ou rota direta."""
        target_id = self._get_adjacent_hino_id(offset)
        if target_id is None:
            return
        if self.animated_container is not None:
            await self._navigate_hino_directional(page, target_id, direction=direction)
        elif hasattr(page, "push_route"):
            await page.push_route(f"/{self.edition}/hino/{target_id}")

    def _build_nav_buttons(self, page: ft.Page) -> tuple:
        """Constrói botões de navegação anterior/próximo baseados na lista de IDs."""
        has_prev = self._get_adjacent_hino_id(-1) is not None
        has_next = self._get_adjacent_hino_id(1) is not None

        async def _go_prev(_e=None):
            await self._navigate_to_adjacent(page, -1, "prev")

        async def _go_next(_e=None):
            await self._navigate_to_adjacent(page, 1, "next")

        self.prev_btn = ft.IconButton(
            ft.Icons.NAVIGATE_BEFORE,
            tooltip="Hino Anterior",
            on_click=_go_prev,
            disabled=not has_prev,
        )
        self.next_btn = ft.IconButton(
            ft.Icons.NAVIGATE_NEXT,
            tooltip="Próximo Hino",
            on_click=_go_next,
            disabled=not has_next,
        )

        return self.prev_btn, self.next_btn

    def _update_nav_buttons_state(self) -> None:
        """Atualiza o estado habilitado/desabilitado dos botões de navegação."""
        has_prev = self._get_adjacent_hino_id(-1) is not None
        has_next = self._get_adjacent_hino_id(1) is not None

        if self.prev_btn:
            self.prev_btn.disabled = not has_prev
            try:
                self.prev_btn.update()
            except Exception:
                pass
        if self.next_btn:
            self.next_btn.disabled = not has_next
            try:
                self.next_btn.update()
            except Exception:
                pass

    async def _animate_exit(self, exit_x: float) -> None:
        """Anima a saída do container para navegação direcional."""
        if self.animated_container:
            self.animated_container.animate_offset = ft.Animation(
                160, ft.AnimationCurve.EASE_IN
            )
            self.animated_container.offset = ft.Offset(exit_x, 0)
            try:
                self.animated_container.update()
            except Exception:
                pass
            await asyncio.sleep(0.16)

    async def _animate_entry(self, enter_x: float) -> None:
        """Anima a entrada do container para navegação direcional."""
        if self.animated_container:
            self.animated_container.animate_offset = None
            self.animated_container.offset = ft.Offset(enter_x, 0)
            try:
                self.animated_container.update()
            except Exception:
                pass

            await asyncio.sleep(0.02)

            self.animated_container.animate_offset = ft.Animation(
                200, ft.AnimationCurve.EASE_OUT_CUBIC
            )
            self.animated_container.offset = ft.Offset(0, 0)
            try:
                self.animated_container.update()
            except Exception:
                pass

    async def _update_hino_ui_elements(self, page: ft.Page, new_hino: Hino) -> None:
        """Atualiza os controles da interface após mudar de hino."""
        if self.appbar_title:
            self.appbar_title.value = f"Hino {new_hino.numero}"
            try:
                self.appbar_title.update()
            except Exception:
                pass

        self._update_nav_buttons_state()
        self._update_fav_icon_state()

        has_youtube = bool(new_hino.link_video and new_hino.link_video.strip())
        if self.youtube_btn:
            self.youtube_btn.disabled = not has_youtube
            self.youtube_btn.icon_color = (
                ft.Colors.RED_400 if has_youtube else None
            )
            try:
                self.youtube_btn.update()
            except Exception:
                pass

        if self.letra_text:
            self.letra_text.value = (
                new_hino.letra if new_hino.letra else MSG_LETRA_NAO_DISPONIVEL
            )

        self.selected_view_mode = self.edition

        if self.content_container:
            self.content_container.content = self._render_current_mode_content()

        if self.header_container:
            self.header_container.content = (
                self._build_header_container(page, new_hino).content
            )

        if self.segmented_container:
            new_seg = self._build_segmented_button(page)
            self.segmented_container.content = new_seg
            self.segmented_container.visible = new_seg is not None

        if self.scroll_column:
            try:
                res = self.scroll_column.scroll_to(offset=0, duration=0)
                if inspect.iscoroutine(res):
                    await res
            except Exception:
                pass

    async def _navigate_hino_directional(
        self, page: ft.Page, target_id: int, direction: str
    ) -> None:
        """Transiciona para o hino anterior ou próximo com animação direcional de deslizamento."""
        if self._is_navigating:
            return
        self._is_navigating = True
        try:
            exit_x = -1.0 if direction == "next" else 1.0
            enter_x = 1.0 if direction == "next" else -1.0

            await self._animate_exit(exit_x)

            new_hino = await self.hino_repository.get_by_id(target_id)
            if not new_hino:
                return

            self.hino_id = target_id
            self.current_hino = new_hino
            await self._init_data_and_preferences(page, new_hino)
            await self._update_hino_ui_elements(page, new_hino)

            new_route = f"/{self.edition}/hino/{target_id}"
            if self.view:
                self.view.route = new_route
            page.route = new_route

            await self._animate_entry(enter_x)

            try:
                page.update()
            except Exception:
                pass
        finally:
            self._is_navigating = False

    def _on_menu_biblia_click(self, page: ft.Page) -> None:
        """Abre o modal bíblico a partir do menu superior direito."""
        ref = None
        if self.current_hino and self.current_hino.texto_base and self.current_hino.texto_base.strip():
            ref = self.current_hino.texto_base.strip()
        elif self.relacionados.get("textos_biblicos"):
            ref = self.relacionados["textos_biblicos"][0]

        if not ref:
            self._show_snackbar(page, "Nenhum texto bíblico cadastrado para este hino.")
            return

        self._on_biblia_click(page, ref)

    def _on_biblia_click(
        self,
        page: ft.Page,
        ref: str,
    ) -> None:
        """Manipula o clique em um chip bíblico, abrindo o modal BottomSheet de leitura bíblica."""
        try:
            page.pop_dialog()
        except Exception:
            pass
        clean_ref = ref.strip() if ref else ""
        if hasattr(page, "run_task"):
            page.run_task(
                self._abrir_modal_leitura_biblica,
                page,
                clean_ref,
                False,
                self.current_hino,
            )
        else:
            self._create_background_task(
                self._abrir_modal_leitura_biblica(
                    page, clean_ref, from_info_modal=False, hino=self.current_hino
                )
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

    def _create_modal_ref_chip(
        self,
        r: str,
        is_active: bool,
        is_base: bool,
        accent_color: str,
        click_handler: Any,
    ) -> ft.Container:
        """Cria o chip individual de referência para o modal bíblico."""
        label_prefix = "✦ " if is_base else ""
        label_suffix = " (Base)" if is_base else ""
        return ft.Container(
            content=ft.Text(
                f"{label_prefix}{r}{label_suffix}",
                size=11,
                weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
                color=accent_color if is_active else ft.Colors.ON_SURFACE_VARIANT,
            ),
            bgcolor=(
                ft.Colors.with_opacity(0.18, accent_color)
                if is_active
                else ft.Colors.SURFACE_CONTAINER_HIGHEST
            ),
            border=ft.Border.all(1, accent_color) if is_active else None,
            border_radius=12,
            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
            on_click=click_handler,
            ink=True,
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
        def _make_chip_click_handler(target_ref: str):
            async def _on_chip_click(e):
                res = on_select_callback(e, target_ref)
                if inspect.iscoroutine(res):
                    await res

            return _on_chip_click

        chips = []
        for r in all_refs:
            is_active = r == active_ref
            is_base = bool(base_ref and r == base_ref.strip())
            chip = self._create_modal_ref_chip(
                r, is_active, is_base, accent_color, _make_chip_click_handler(r)
            )
            chips.append(chip)
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
        font_minus_btn: ft.Control,
        font_indicator: ft.Control,
        font_plus_btn: ft.Control,
    ) -> ft.Container:
        """Gera a barra de ações inferiores do modal bíblico."""
        return ft.Container(
            content=ft.Row(
                controls=[
                    copy_btn,
                    ft.Row(
                        controls=[
                            font_minus_btn,
                            ft.Container(
                                content=font_indicator,
                                width=36,
                                alignment=ft.Alignment.CENTER,
                            ),
                            font_plus_btn,
                        ],
                        spacing=2,
                        alignment=ft.MainAxisAlignment.END,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(vertical=4),
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

        await self._load_preferences()
        session = _BibliaModalSession(
            view=self,
            page=page,
            referencia=referencia.strip(),
            from_info_modal=from_info_modal,
            hino=hino,
        )
        await session.show()

    def _build_not_found_view(self, page: ft.Page) -> ft.View:
        async def _go_back(e):
            try:
                if hasattr(page, "pop_dialog") and page.pop_dialog():
                    return
            except Exception:
                pass

            if hasattr(page, "on_view_pop") and page.on_view_pop:
                res = cast(Any, page.on_view_pop)(None)
                if inspect.iscoroutine(res):
                    await res
            elif len(page.views) > 1:
                page.views.pop()
                top_view = page.views[-1]
                page.route = top_view.route or f"/{self.edition}"
                if hasattr(page, "on_route_change") and page.on_route_change:
                    res = cast(Any, page.on_route_change)(None)
                    if inspect.iscoroutine(res):
                        await res
                else:
                    await page.push_route(page.route)
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

    def _get_edition_feedback_info(self) -> tuple[str, str, str, ft.IconData]:
        """Retorna (label, bgcolor, text_color, icon) para o feedback visual suave da edição selecionada."""
        mode = self.selected_view_mode
        if mode == "letra":
            mode = self.edition

        if mode == "novo":
            return (
                "Novo Hinário selecionado",
                ft.Colors.PRIMARY_CONTAINER,
                ft.Colors.ON_PRIMARY_CONTAINER,
                ft.Icons.CHECK_CIRCLE_OUTLINE,
            )
        elif mode == "antigo":
            return (
                "Hinário Tradicional selecionado",
                ft.Colors.SECONDARY_CONTAINER,
                ft.Colors.ON_SECONDARY_CONTAINER,
                ft.Icons.HISTORY_EDU_OUTLINED,
            )
        elif mode == "comparacao":
            return (
                "Modo de Comparação selecionado",
                ft.Colors.TERTIARY_CONTAINER,
                ft.Colors.ON_TERTIARY_CONTAINER,
                ft.Icons.COMPARE_ARROWS,
            )
        elif mode == "biblia":
            return (
                "Texto Bíblico selecionado",
                ft.Colors.SURFACE_CONTAINER_HIGHEST,
                ft.Colors.ON_SURFACE_VARIANT,
                ft.Icons.MENU_BOOK,
            )

        if self.edition == "antigo":
            return (
                "Hinário Tradicional selecionado",
                ft.Colors.SECONDARY_CONTAINER,
                ft.Colors.ON_SECONDARY_CONTAINER,
                ft.Icons.HISTORY_EDU_OUTLINED,
            )
        return (
            "Novo Hinário selecionado",
            ft.Colors.PRIMARY_CONTAINER,
            ft.Colors.ON_PRIMARY_CONTAINER,
            ft.Icons.CHECK_CIRCLE_OUTLINE,
        )

    def _build_edition_feedback_banner(self) -> ft.Container:
        """Cria o banner pill de feedback visual da edição ativa com cor suave."""
        label, bgcolor, text_color, icon = self._get_edition_feedback_info()
        self.edition_feedback_icon = ft.Icon(icon, size=14, color=text_color)
        self.edition_feedback_text = ft.Text(
            label,
            size=12,
            weight=ft.FontWeight.W_500,
            color=text_color,
        )
        self.edition_feedback_banner = ft.Container(
            content=ft.Row(
                controls=[
                    self.edition_feedback_icon,
                    self.edition_feedback_text,
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
            ),
            bgcolor=bgcolor,
            border_radius=20,
            padding=ft.Padding.symmetric(horizontal=14, vertical=5),
            tooltip="Edição ou modo de exibição ativo",
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )
        return self.edition_feedback_banner

    def _update_edition_feedback_banner(self) -> None:
        """Atualiza dinamicamente o texto, cor de fundo e ícone do banner de feedback."""
        if not self.edition_feedback_banner:
            return
        label, bgcolor, text_color, icon = self._get_edition_feedback_info()
        self.edition_feedback_banner.bgcolor = bgcolor
        if hasattr(self, "edition_feedback_icon") and self.edition_feedback_icon:
            setattr(self.edition_feedback_icon, "name", icon)
            setattr(self.edition_feedback_icon, "icon", icon)
            self.edition_feedback_icon.color = text_color
        if hasattr(self, "edition_feedback_text") and self.edition_feedback_text:
            self.edition_feedback_text.value = label
            self.edition_feedback_text.color = text_color

    def _build_segmented_button(self, page: ft.Page) -> ft.Control | None:
        """Gera a barra de alternância (SegmentedButton) apenas entre versões da letra (ex.: NHA vs HA)."""
        if not self.comparativo:
            return None

        has_counterpart = bool(
            self.comparativo.numero_antigo
            if self.edition == "novo"
            else self.comparativo.numero_novo
        )
        if not has_counterpart:
            return None

        segments = self._create_edition_segments()
        if not segments:
            return None

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

    async def _on_inline_biblia_ref_selected(self, _e, ref_target: str) -> None:
        """Manipula a seleção de uma referência bíblica alternativa na visualização inline."""
        if self.active_biblia_ref != ref_target:
            self.active_biblia_ref = ref_target
            self.is_biblia_full_chapter = False
            await self._carregar_biblia_passagem(self.page)

    async def _on_inline_versao_selected(self, nova_versao: str) -> None:
        """Manipula a alteração de versão da Bíblia na barra de ferramentas inline."""
        if not nova_versao or nova_versao == self.selected_biblia_version:
            return
        self.selected_biblia_version = nova_versao
        self.biblia_repository.set_version(nova_versao)
        if hasattr(self, "inline_version_btn") and self.inline_version_btn:
            update_bible_version_button(
                self.inline_version_btn,
                nova_versao,
                self.biblia_repository,
                self._on_inline_versao_selected,
            )
        self._save_pref_task = self._create_background_task(self._save_preferences())
        await self._carregar_biblia_passagem(self.page)

    async def _on_inline_versao_changed(self, e) -> None:
        """Manipula a alteração de versão da Bíblia a partir do Dropdown (legado)."""
        nova_versao = getattr(e.control, "value", None)
        if nova_versao:
            await self._on_inline_versao_selected(nova_versao)

    async def _on_inline_copiar_passagem(self, e) -> None:
        """Copia a passagem bíblica ativa para a área de transferência."""
        passagem = self.current_biblia_passagem
        if not passagem or not passagem.versiculos:
            return
        texto_copia = f'"{passagem.texto_formatado}"\n— {passagem.referencia} ({self.selected_biblia_version})'
        try:
            await ft.Clipboard().set(texto_copia)
        except Exception:
            pass
        if self.page:
            self._show_snackbar(self.page, f"Passagem '{passagem.referencia} ({self.selected_biblia_version})' copiada!")

    async def _on_inline_toggle_capitulo(self, e) -> None:
        """Alterna entre versículos do hino e o capítulo completo na visualização inline."""
        self.is_biblia_full_chapter = not self.is_biblia_full_chapter
        await self._carregar_biblia_passagem(self.page)

    def _on_inline_voltar_letra(self, e) -> None:
        """Retorna da visualização bíblica para a letra do hino."""
        self.selected_view_mode = self.edition
        self._update_content_view(self.page)

    def _build_biblia_inline_toolbar(self, accent_color: str) -> ft.Container:
        """Gera a barra de ferramentas do leitor bíblico inline."""
        ref_title_text = (
            self.current_biblia_passagem.referencia
            if self.current_biblia_passagem and self.current_biblia_passagem.referencia
            else (self.active_biblia_ref or "")
        )
        ref_title = ft.Text(
            ref_title_text,
            size=18,
            weight=ft.FontWeight.BOLD,
            color=accent_color,
        )
        self.inline_version_btn = build_bible_version_button(
            biblia_repository=self.biblia_repository,
            current_version=self.selected_biblia_version,
            on_version_selected=self._on_inline_versao_selected,
            theme_service=self.theme_service,
        )
        if self.is_simplified_bible:
            self.inline_version_btn.visible = False
            self.inline_version_btn.disabled = True

        copy_btn = ft.OutlinedButton(
            "Copiar",
            icon=ft.Icons.CONTENT_COPY,
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                text_style=ft.TextStyle(size=12),
            ),
            tooltip="Copiar passagem com referência para a área de transferência",
            on_click=lambda e: (
                self.page.run_task(self._on_inline_copiar_passagem, e)
                if self.page
                else None
            ),
        )

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
                self.page.run_task(self._on_inline_toggle_capitulo, e)
                if self.page
                else None
            ),
        )

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
                    on_click=self._on_inline_voltar_letra,
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
                        controls=[
                            chapter_toggle_btn,
                            self.inline_version_btn,
                            copy_btn,
                        ],
                        spacing=6,
                        wrap=True,
                        alignment=ft.MainAxisAlignment.END,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
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


    def _build_single_biblia_chip(
        self, r: str, is_active: bool, is_base: bool, accent_color: str
    ) -> ft.Control:
        """Constrói um único chip de navegação bíblica com feedback visual de seleção."""
        label_prefix = "✦ " if is_base else ""
        label_suffix = " (Base)" if is_base else ""
        def _make_inline_chip_handler(target_ref: str):
            async def _on_inline_chip_click(e):
                await self._on_inline_biblia_ref_selected(e, target_ref)

            return _on_inline_chip_click

        return ft.Container(
            content=ft.Text(
                f"{label_prefix}{r}{label_suffix}",
                size=11,
                weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
                color=accent_color if is_active else ft.Colors.ON_SURFACE_VARIANT,
            ),
            bgcolor=(
                ft.Colors.with_opacity(0.18, accent_color)
                if is_active
                else ft.Colors.SURFACE_CONTAINER_HIGHEST
            ),
            border=ft.Border.all(1, accent_color) if is_active else None,
            border_radius=12,
            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
            on_click=_make_inline_chip_handler(r),
            ink=True,
        )

    def _build_biblia_inline_chips(
        self, all_refs: list[str], accent_color: str
    ) -> list[ft.Control]:
        """Gera a linha de chips de referências bíblicas na visualização inline."""
        if len(all_refs) <= 1:
            return []
        base_ref = (
            self.current_hino.texto_base.strip()
            if (self.current_hino and self.current_hino.texto_base)
            else None
        )
        chips = [
            self._build_single_biblia_chip(
                r=r,
                is_active=(r == self.active_biblia_ref),
                is_base=bool(base_ref and r == base_ref),
                accent_color=accent_color,
            )
            for r in all_refs
        ]
        return [
            ft.Container(
                content=ft.Row(controls=chips, scroll=ft.ScrollMode.AUTO, spacing=6),
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
        """Atualiza o conteúdo dinâmico da letra/comparação e o banner de feedback da edição."""
        self._update_edition_feedback_banner()
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
            num = self.hino_antigo.numero or ""
            titulo = self.hino_antigo.titulo or ""
            letra = self.hino_antigo.letra or MSG_LETRA_NAO_DISPONIVEL
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
                num_val or "",
                titulo_val or fallback_title,
                MSG_LETRA_NAO_DISPONIVEL,
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
        ensure_page_dialogs(page)
        page.show_dialog(bs)

    async def _navigate_filter(
        self, page: ft.Page, filter_type: str, filter_val: str
    ) -> None:
        """Fecha o modal e navega para a lista de hinos com filtro de categoria/tema e origem do hino."""
        try:
            page.pop_dialog()
        except Exception:
            pass
        encoded_val = urllib.parse.quote(filter_val.strip())
        edition_route = f"/{self.edition}" if self.edition in ("novo", "antigo") else "/novo"
        await page.push_route(
            f"{edition_route}?{filter_type}={encoded_val}&from_hino={self.hino_id}"
        )

    def _trigger_filter_navigation(
        self, page: ft.Page, filter_type: str, filter_val: str
    ) -> None:
        """Aciona a navegação de filtro mantendo a referência da task."""
        if self._nav_task and not self._nav_task.done():
            self._nav_task.cancel()
        self._nav_task = asyncio.create_task(
            self._navigate_filter(page, filter_type, filter_val)
        )

    async def _navigate_search(self, page: ft.Page, term: str) -> None:
        """Compatibilidade: navega como categoria preservando o hino de origem."""
        await self._navigate_filter(page, "categoria", term)

    def _trigger_search_navigation(self, page: ft.Page, term: str) -> None:
        """Compatibilidade: aciona a navegação de categoria."""
        self._trigger_filter_navigation(page, "categoria", term)


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
                                color=ft.Colors.PRIMARY,
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
                    color=ft.Colors.PRIMARY,
                ),
                ft.Chip(
                    label=ft.Text(hino.texto_base, size=12),
                    leading=ft.Icon(
                        ft.Icons.MENU_BOOK_OUTLINED, size=15, color=ft.Colors.PRIMARY
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
                        ft.Icons.FOLDER_OUTLINED, size=16, color=ft.Colors.PRIMARY
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    on_click=lambda e, c=hino.categoria: self._trigger_filter_navigation(
                        page, "categoria", c
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
                        color=ft.Colors.PRIMARY,
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    on_click=lambda e, sc=hino.subcategoria: self._trigger_filter_navigation(
                        page, "categoria", sc
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
                    ft.Icons.LABEL_OUTLINED, size=15, color=ft.Colors.TERTIARY
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                on_click=lambda e, tema=t: self._trigger_filter_navigation(
                    page, "tema", tema
                ),
            )
            for t in temas
        ]
        return ft.Column(
            controls=[
                ft.Text(
                    "Temas Relacionados:",
                    weight=ft.FontWeight.BOLD,
                    size=12,
                    color=ft.Colors.TERTIARY,
                ),
                ft.Row(controls=tema_chips, wrap=True, spacing=6, run_spacing=6),
            ],
            spacing=4,
        )

    def _build_biblical_texts_info_control(self, page: ft.Page) -> ft.Control | None:
        """Gera a seção de chips dos textos bíblicos relacionados."""
        textos_biblicos = self.relacionados.get("textos_biblicos", [])
        if not textos_biblicos:
            return None
        texto_chips: list[ft.Control] = [
            ft.Chip(
                label=ft.Text(tb, size=11),
                leading=ft.Icon(
                    ft.Icons.MENU_BOOK_OUTLINED, size=15, color=ft.Colors.PRIMARY
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
                    color=ft.Colors.PRIMARY,
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
                    color=ft.Colors.PRIMARY,
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
                            color=ft.Colors.PRIMARY,
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
                                color=ft.Colors.PRIMARY,
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
                                color=ft.Colors.PRIMARY,
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
                    color=ft.Colors.PRIMARY,
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
            self._build_biblical_texts_info_control(page),
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
        ensure_page_dialogs(page)
        page.show_dialog(bs)
