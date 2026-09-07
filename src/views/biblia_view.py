import asyncio
import json
from typing import Any, Callable

import flet as ft

from src.models.biblia import PassagemBiblica
from src.repositories.biblia_repository import BibliaRepository
from src.services.theme_service import ThemeService
from src.views.settings_dialog import ensure_page_dialogs

PREF_BIBLIA_KEY = "biblia_prefs"
PREF_MARCADORES_KEY = "biblia_marcadores"

__all__ = [
    "BibliaView",
    "build_bible_version_button",
    "update_bible_version_button",
    "format_verse_numbers",
    "format_verse_citation",
]

CANONICAL_BOOK_ABBREVIATIONS: dict[int, str] = {
    # Antigo Testamento (1 a 39)
    1: "Gn", 2: "Êx", 3: "Lv", 4: "Nm", 5: "Dt",
    6: "Js", 7: "Jz", 8: "Rt", 9: "1Sm", 10: "2Sm",
    11: "1Rs", 12: "2Rs", 13: "1Cr", 14: "2Cr", 15: "Ed",
    16: "Ne", 17: "Et", 18: "Jó", 19: "Sl", 20: "Pv",
    21: "Ec", 22: "Ct", 23: "Is", 24: "Jr", 25: "Lm",
    26: "Ez", 27: "Dn", 28: "Os", 29: "Jl", 30: "Am",
    31: "Ob", 32: "Jn", 33: "Mq", 34: "Na", 35: "Hc",
    36: "Sf", 37: "Ag", 38: "Zc", 39: "Ml",
    # Novo Testamento (40 a 66)
    40: "Mt", 41: "Mc", 42: "Lc", 43: "Jo", 44: "At",
    45: "Rm", 46: "1Co", 47: "2Co", 48: "Gl", 49: "Ef",
    50: "Fp", 51: "Cl", 52: "1Ts", 53: "2Ts", 54: "1Tm",
    55: "2Tm", 56: "Tt", 57: "Fm", 58: "Hb", 59: "Tg",
    60: "1Pe", 61: "2Pe", 62: "1Jo", 63: "2Jo", 64: "3Jo",
    65: "Jd", 66: "Ap",
}


def format_verse_numbers(nums: list[int]) -> str:
    """
    Agrupa números de versículos em intervalos canônicos.
    Exemplos:
      [1, 2, 3] -> "1-3"
      [1, 3, 8] -> "1, 3, 8"
      [1, 2, 3, 7, 10, 11, 12] -> "1-3, 7, 10-12"
      [5] -> "5"
    """
    if not nums:
        return ""
    sorted_nums = sorted(set(nums))
    ranges: list[str] = []
    start = sorted_nums[0]
    prev = sorted_nums[0]

    for n in sorted_nums[1:]:
        if n == prev + 1:
            prev = n
        else:
            if start == prev:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{prev}")
            start = n
            prev = n

    if start == prev:
        ranges.append(str(start))
    else:
        ranges.append(f"{start}-{prev}")

    return ", ".join(ranges)


def format_verse_citation(
    book_name: str,
    chapter: int,
    verses: list[tuple[int, str]],
    version: str,
) -> str:
    """
    Formata versículos selecionados e gera citação canônica estruturada.
    Exemplo sequencial:
      "No princípio criou Deus os céus e a terra. E a terra era sem forma e vazia."
      — Gênesis 1:1-2 (ARA)
    Exemplo não sequencial ou intercalado:
      "1 No princípio criou Deus os céus e a terra.
      3 E disse Deus: Haja luz; e houve luz."
      — Gênesis 1:1, 3 (ARA)
    """
    if not verses:
        return ""

    sorted_verses = sorted(verses, key=lambda item: item[0])
    nums = [item[0] for item in sorted_verses]
    range_str = format_verse_numbers(nums)
    ref_suffix = f"— {book_name} {chapter}:{range_str} ({version})"

    is_strictly_sequential = len(nums) > 1 and nums == list(range(nums[0], nums[0] + len(nums)))

    if len(sorted_verses) == 1:
        body = sorted_verses[0][1].strip()
    elif is_strictly_sequential:
        body = " ".join(v[1].strip() for v in sorted_verses)
    else:
        lines = [f"{v[0]} {v[1].strip()}" for v in sorted_verses]
        body = "\n".join(lines)

    return f'"{body}"\n{ref_suffix}'


def build_bible_version_button(
    biblia_repository: BibliaRepository,
    current_version: str,
    on_version_selected: Callable[[str], Any],
    theme_service: ThemeService | None = None,
    tooltip: str = "Selecionar versão da Bíblia",
) -> ft.PopupMenuButton:
    """
    Constrói um botão estilizado M3 pill com PopupMenuButton para seleção rápida de versão da Bíblia.
    Exibe a versão atual com ícone drop down e um checkmark (✓) na versão selecionada no menu popup.
    """
    versoes = biblia_repository.get_available_versions()

    def _handle_select(ver: str):
        res = on_version_selected(ver)
        if asyncio.iscoroutine(res):
            asyncio.create_task(res)

    version_text = ft.Text(
        current_version,
        size=12,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.ON_SURFACE,
    )

    items = [
        ft.PopupMenuItem(
            f"{v}  ✓" if v == current_version else v,
            on_click=lambda ev, ver=v: _handle_select(ver),
        )
        for v in versoes
    ]

    button = ft.PopupMenuButton(
        content=ft.Container(
            content=ft.Row(
                controls=[
                    version_text,
                    ft.Icon(
                        ft.Icons.ARROW_DROP_DOWN,
                        size=18,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=2,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            margin=ft.Margin.symmetric(horizontal=4),
            border_radius=16,
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            tooltip=tooltip,
        ),
        items=items,
        tooltip=tooltip,
    )
    return button


def update_bible_version_button(
    btn: ft.PopupMenuButton,
    new_version: str,
    biblia_repository: BibliaRepository,
    on_version_selected: Callable[[str], Any],
) -> None:
    """Atualiza o texto visual e os checkmarks dos itens do botão de versão da Bíblia."""
    if not btn:
        return
    try:
        if hasattr(btn, "content") and hasattr(btn.content, "content"):
            row = btn.content.content
            if hasattr(row, "controls") and len(row.controls) > 0:
                row.controls[0].value = new_version

        def _handle_select(ver: str):
            res = on_version_selected(ver)
            if asyncio.iscoroutine(res):
                asyncio.create_task(res)

        versoes = biblia_repository.get_available_versions()
        btn.items = [
            ft.PopupMenuItem(
                f"{v}  ✓" if v == new_version else v,
                on_click=lambda ev, ver=v: _handle_select(ver),
            )
            for v in versoes
        ]
        if hasattr(btn, "update"):
            btn.update()
    except Exception:
        pass


class BibliaView:
    """
    Tela completa e responsiva para leitura e navegação da Bíblia Sagrada.
    Permite alternar versões (ARA, NVI, etc.), selecionar livros do Antigo/Novo Testamento
    em grade de 66 botões e capítulos através de um modal/BottomSheet intuitivo, navegação rápida,
    marcação de versículos favoritos e persistência de sessão entre reinicializações.
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

        # Configurações de exibição de texto, marcadores e persistência
        self.font_size: int = 17
        self.font_family: str = "Roboto"
        self.marcadores: dict[str, dict[str, Any]] = {}
        self._prefs_loaded: bool = False
        self._prefs_db: Any | None = None

        # Estado do modo de seleção múltipla de versículos
        self.selected_verses: set[int] = set()
        self.is_selection_mode: bool = False

        # Referências de controles Flet
        self.page: ft.Page | None = None
        self.view: ft.View | None = None
        self.normal_appbar: ft.AppBar | None = None
        self.appbar_title_btn: ft.TextButton | None = None
        self.version_dropdown: ft.Dropdown | None = None
        self.version_btn: ft.PopupMenuButton | None = None
        self.prev_btn: ft.IconButton | None = None
        self.next_btn: ft.IconButton | None = None
        self.prev_chip_btn: ft.OutlinedButton | None = None
        self.next_chip_btn: ft.OutlinedButton | None = None
        self.verses_list: ft.ListView | None = None
        self.header_info_text: ft.Text | None = None

        # Telas ativas de navegação sequencial em tela cheia (Plano B + Sprint 4)
        self.active_screen: str = "leitor"  # "leitor", "livros", "capitulos", "pesquisa"
        self.selected_modal_book: dict[str, Any] = {"id": 1, "name": "Gênesis"}
        self.selected_testament: str = "AT"
        self.books_grid_container: ft.Container | None = None
        self.chapters_grid_container: ft.Container | None = None

        # Estado da pesquisa bíblica (Sprint 4)
        self.search_query: str = ""
        self.search_scope: str = "todos"  # "todos", "livro", "at", "nt"
        self.search_results: list[dict[str, Any]] = []
        self.is_searching: bool = False
        self.search_input: ft.TextField | None = None

    def _show_snackbar(self, message: str, duration: int = 2500) -> None:
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

    async def _get_prefs_connection(self):
        """Retorna uma conexão de banco com suporte à tabela 'preferencias'."""
        if (
            self.theme_service
            and hasattr(self.theme_service, "db_connection")
            and self.theme_service.db_connection
        ):
            return await self.theme_service.db_connection.get_connection()
        if not self._prefs_db:
            from src.database.connection import DatabaseConnection

            self._prefs_db = DatabaseConnection(db_path="hinario.db")
        return await self._prefs_db.get_connection()

    async def _load_preferences_and_bookmarks(
        self, restore_session: bool = True
    ) -> None:
        """Carrega a última leitura e a coleção de versículos marcados."""
        if self._prefs_loaded:
            return
        try:
            conn = await self._get_prefs_connection()
            # 1. Carrega biblia_prefs
            async with conn.execute(
                "SELECT valor FROM preferencias WHERE chave = ?", (PREF_BIBLIA_KEY,)
            ) as cursor:
                row = await cursor.fetchone()
            if row and row[0]:
                data = json.loads(row[0])
                if restore_session:
                    self.current_book_id = int(data.get("book_id", self.current_book_id))
                    self.current_chapter = int(data.get("chapter", self.current_chapter))
                    v_saved = data.get("version")
                    if v_saved:
                        self.selected_version = str(v_saved).strip().upper()
                        self.biblia_repository.set_version(self.selected_version)
                if "font_size" in data:
                    self.font_size = int(data.get("font_size", self.font_size))
                if "font_family" in data:
                    self.font_family = str(data.get("font_family", self.font_family))

            # 2. Carrega biblia_marcadores
            async with conn.execute(
                "SELECT valor FROM preferencias WHERE chave = ?",
                (PREF_MARCADORES_KEY,),
            ) as cursor:
                row_m = await cursor.fetchone()
            if row_m and row_m[0]:
                self.marcadores = json.loads(row_m[0])
        except Exception:
            pass
        self._prefs_loaded = True

    async def _save_preferences(self) -> None:
        """Persiste a sessão atual (livro, capítulo, versão, tamanho e família de fonte)."""
        try:
            conn = await self._get_prefs_connection()
            payload = json.dumps(
                {
                    "book_id": self.current_book_id,
                    "chapter": self.current_chapter,
                    "version": self.selected_version,
                    "font_size": self.font_size,
                    "font_family": self.font_family,
                }
            )
            await conn.execute(
                "INSERT OR REPLACE INTO preferencias (chave, valor) VALUES (?, ?)",
                (PREF_BIBLIA_KEY, payload),
            )
            await conn.commit()
        except Exception:
            pass

    async def _save_bookmarks(self) -> None:
        """Persiste os versículos marcados no SQLite."""
        try:
            conn = await self._get_prefs_connection()
            payload = json.dumps(self.marcadores)
            await conn.execute(
                "INSERT OR REPLACE INTO preferencias (chave, valor) VALUES (?, ?)",
                (PREF_MARCADORES_KEY, payload),
            )
            await conn.commit()
        except Exception:
            pass

    async def _toggle_marcador(self, versiculo_num: int, texto: str) -> None:
        """Marca ou desmarca um versículo e persiste no banco SQLite."""
        key = f"{self.current_book_id}_{self.current_chapter}_{versiculo_num}"
        book_name = self._get_current_book_name()
        if key in self.marcadores:
            del self.marcadores[key]
            msg = f"Marcador removido de {book_name} {self.current_chapter}:{versiculo_num}"
        else:
            self.marcadores[key] = {
                "id": key,
                "book_id": self.current_book_id,
                "book_name": book_name,
                "chapter": self.current_chapter,
                "verse": versiculo_num,
                "text": texto,
                "version": self.selected_version,
            }
            msg = f"Versículo {book_name} {self.current_chapter}:{versiculo_num} marcado!"

        await self._save_bookmarks()
        self._show_snackbar(msg)
        self._render_verses()

    async def _remover_marcador_por_id(self, key: str) -> None:
        """Remove um marcador diretamente e atualiza a interface."""
        if key in self.marcadores:
            del self.marcadores[key]
            await self._save_bookmarks()
            self._show_snackbar("Marcador removido com sucesso!")
            self._render_verses()
            if self.page:
                try:
                    self.page.pop_dialog()
                except Exception:
                    pass
                self._show_marcadores_dialog()

    async def _copiar_versiculo(self, versiculo_num: int, texto: str) -> None:
        """Copia um versículo específico incluindo a versão da Bíblia utilizada."""
        book_name = self._get_current_book_name()
        texto_copia = format_verse_citation(
            book_name=book_name,
            chapter=self.current_chapter,
            verses=[(versiculo_num, texto)],
            version=self.selected_version,
        )
        try:
            await ft.Clipboard().set(texto_copia)
        except Exception:
            pass
        if self.page:
            try:
                self.page.set_clipboard(texto_copia)
            except Exception:
                pass
        self._show_snackbar(
            f"{book_name} {self.current_chapter}:{versiculo_num} ({self.selected_version}) copiado!"
        )

    async def _copiar_capitulo(self, e=None) -> None:
        """Copia todo o capítulo atual com a versão da Bíblia utilizada."""
        if not self.current_passagem or not self.current_passagem.versiculos:
            return
        book_name = self._get_current_book_name()
        texto_copia = f'"{self.current_passagem.texto_formatado}"\n— {book_name} {self.current_chapter} ({self.selected_version})'
        try:
            await ft.Clipboard().set(texto_copia)
        except Exception:
            pass
        if self.page:
            try:
                self.page.set_clipboard(texto_copia)
            except Exception:
                pass
        self._show_snackbar(
            f"Capítulo {book_name} {self.current_chapter} ({self.selected_version}) copiado!"
        )

    # ---------------------------------------------------------
    # Métodos do Modo de Seleção Múltipla de Versículos
    # ---------------------------------------------------------
    def _enter_selection_mode(self, v_num: int) -> None:
        """Entra no modo de seleção com o versículo inicial."""
        self.is_selection_mode = True
        self.selected_verses = {v_num}
        self._update_appbar_for_selection()
        self._render_verses()

    def _exit_selection_mode(self) -> None:
        """Cancela o modo de seleção e restaura a navegação normal."""
        self.is_selection_mode = False
        self.selected_verses.clear()
        if self.view and self.normal_appbar:
            self.view.appbar = self.normal_appbar
        self._render_verses()
        if self.page:
            self.page.update()

    def _toggle_verse_selection(self, v_num: int) -> None:
        """Alterna a seleção de um versículo (adiciona ou remove)."""
        if v_num in self.selected_verses:
            self.selected_verses.remove(v_num)
            if not self.selected_verses:
                self._exit_selection_mode()
                return
        else:
            self.selected_verses.add(v_num)
        self._update_appbar_for_selection()
        self._render_verses()

    def _select_all_verses(self) -> None:
        """Seleciona todos os versículos do capítulo atual."""
        if self.current_passagem and self.current_passagem.versiculos:
            self.selected_verses = {v.numero for v in self.current_passagem.versiculos}
            self._update_appbar_for_selection()
            self._render_verses()

    def _on_verse_tap(self, v_num: int) -> None:
        """Manipula o toque simples no versículo."""
        if self.is_selection_mode:
            self._toggle_verse_selection(v_num)

    def _on_verse_long_press(self, v_num: int, v_text: str = "") -> None:
        """Manipula o toque longo ou clique com botão direito no versículo."""
        if not self.is_selection_mode:
            self._enter_selection_mode(v_num)
        else:
            self._toggle_verse_selection(v_num)

    async def _toggle_marcadores_selected(self) -> None:
        """Marca ou desmarca todos os versículos selecionados."""
        if not self.selected_verses or not self.current_passagem:
            return
        book_name = self._get_current_book_name()
        all_marked = all(
            f"{self.current_book_id}_{self.current_chapter}_{vn}" in self.marcadores
            for vn in self.selected_verses
        )
        verse_map = {v.numero: v.texto for v in self.current_passagem.versiculos}

        for vn in sorted(self.selected_verses):
            v_key = f"{self.current_book_id}_{self.current_chapter}_{vn}"
            if all_marked:
                self.marcadores.pop(v_key, None)
            else:
                self.marcadores[v_key] = {
                    "book_id": self.current_book_id,
                    "book_name": book_name,
                    "chapter": self.current_chapter,
                    "verse": vn,
                    "version": self.selected_version,
                    "text": verse_map.get(vn, "").strip(),
                }

        await self._save_bookmarks()
        count = len(self.selected_verses)
        msg = (
            f"{count} versículo(s) desmarcado(s)."
            if all_marked
            else f"{count} versículo(s) grifado(s) com sucesso!"
        )
        self._show_snackbar(msg)
        self._exit_selection_mode()

    async def _copy_selected_verses(self) -> None:
        """Copia os versículos selecionados com formatação canônica inteligente."""
        if not self.selected_verses or not self.current_passagem:
            return
        book_name = self._get_current_book_name()
        verse_map = {v.numero: v.texto for v in self.current_passagem.versiculos}
        selected_items = [
            (vn, verse_map.get(vn, ""))
            for vn in sorted(self.selected_verses)
            if vn in verse_map
        ]
        formatted_text = format_verse_citation(
            book_name=book_name,
            chapter=self.current_chapter,
            verses=selected_items,
            version=self.selected_version,
        )
        try:
            await ft.Clipboard().set(formatted_text)
        except Exception:
            pass
        if self.page:
            try:
                self.page.set_clipboard(formatted_text)
            except Exception:
                pass
        count = len(selected_items)
        self._show_snackbar(f"{count} versículo(s) copiado(s)!")
        self._exit_selection_mode()

    def _update_appbar_for_selection(self) -> None:
        """Exibe a barra contextual fixa no topo quando em modo de seleção."""
        if not self.view or not self.page:
            return

        all_marked = bool(self.selected_verses) and all(
            f"{self.current_book_id}_{self.current_chapter}_{vn}" in self.marcadores
            for vn in self.selected_verses
        )

        count_text = (
            f"{len(self.selected_verses)} versículo selecionado"
            if len(self.selected_verses) == 1
            else f"{len(self.selected_verses)} versículos selecionados"
        )

        selection_actions: list[ft.Control] = [
            ft.IconButton(
                icon=ft.Icons.SELECT_ALL,
                tooltip="Selecionar todos os versículos",
                on_click=lambda e: self._select_all_verses(),
            ),
            ft.IconButton(
                icon=(
                    ft.Icons.BOOKMARK_REMOVE
                    if all_marked
                    else ft.Icons.BOOKMARK_ADD
                ),
                icon_color=ft.Colors.ERROR if all_marked else None,
                tooltip=(
                    "Desmarcar versículos selecionados"
                    if all_marked
                    else "Marcar / Grifar versículos selecionados"
                ),
                on_click=lambda e: asyncio.create_task(self._toggle_marcadores_selected()),
            ),
            ft.IconButton(
                icon=ft.Icons.CONTENT_COPY,
                tooltip="Copiar versículos selecionados",
                on_click=lambda e: asyncio.create_task(self._copy_selected_verses()),
            ),
        ]

        if len(self.selected_verses) == 1:
            selection_actions.append(
                ft.IconButton(
                    icon=ft.Icons.COMPARE_ARROWS,
                    tooltip="Comparar versões do versículo",
                    on_click=lambda e: asyncio.create_task(self._abrir_comparador_selecionado()),
                )
            )

        selection_appbar = ft.AppBar(
            leading=ft.IconButton(
                ft.Icons.CLOSE,
                tooltip="Cancelar seleção (Esc)",
                on_click=lambda e: self._exit_selection_mode(),
            ),
            title=ft.Text(count_text, size=15, weight=ft.FontWeight.BOLD),
            center_title=False,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            actions=selection_actions,
        )
        self.view.appbar = selection_appbar
        self.page.update()

    # Alias de compatibilidade com chamadas de renderização
    _render_selection_appbar = _update_appbar_for_selection

    async def _abrir_comparador_selecionado(self) -> None:
        """Abre o comparador de versões para o versículo único selecionado."""
        if not self.selected_verses:
            return
        v_num = min(self.selected_verses)
        await self._abrir_comparador_versoes(
            self.current_book_id, self.current_chapter, v_num
        )

    async def _abrir_comparador_versoes(
        self,
        book_id: int | None = None,
        chapter: int | None = None,
        verse_num: int | None = None,
    ) -> None:
        """
        Abre um modal (BottomSheet) moderno com scroll vertical comparando o versículo
        selecionado em todas as versões da Bíblia disponíveis no aplicativo.
        """
        if not self.page:
            return

        b_id = book_id if book_id is not None else self.current_book_id
        ch = chapter if chapter is not None else self.current_chapter
        vn = verse_num if verse_num is not None else 1
        b_name = self._get_book_name(b_id)
        accent_color = self._get_accent_color()

        comparacoes = await self.biblia_repository.comparar_versiculo(b_id, ch, vn)
        if not comparacoes:
            self._show_snackbar("Nenhuma versão encontrada para comparação.")
            return

        ref_title = f"{b_name} {ch}:{vn}"

        async def _copiar_todas_as_versoes(e):
            linhas: list[str] = [f"{ref_title} em diferentes traduções:\n"]
            for item in comparacoes:
                linhas.append(f"[{item['versao']}] {item['texto']}")
            texto_consolidado = "\n\n".join(linhas)
            try:
                await ft.Clipboard().set(texto_consolidado)
            except Exception:
                pass
            self._show_snackbar("Comparações copiadas para a área de transferência!")

        async def _copiar_versao_individual(item: dict[str, Any]):
            texto_ind = f'"{item["texto"]}"\n— {ref_title} ({item["versao"]})'
            try:
                await ft.Clipboard().set(texto_ind)
            except Exception:
                pass
            self._show_snackbar(f"Versículo na versão {item['versao']} copiado!")

        async def _ler_nesta_versao(nova_versao: str):
            if self.page:
                try:
                    self.page.pop_dialog()
                except Exception:
                    pass
            await self._select_version(nova_versao)

        version_cards: list[ft.Control] = []
        for item in comparacoes:
            is_active = item.get("is_active", False)
            ver = item["versao"]
            nome_ver = item["nome_versao"]
            txt = item["texto"]

            badge_controls: list[ft.Control] = [
                ft.Container(
                    content=ft.Text(
                        ver,
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.ON_PRIMARY_CONTAINER
                        if is_active
                        else ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    bgcolor=ft.Colors.PRIMARY_CONTAINER
                    if is_active
                    else ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                ),
                ft.Text(
                    nome_ver,
                    size=13,
                    weight=ft.FontWeight.W_500,
                    color=ft.Colors.ON_SURFACE,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ]
            if is_active:
                badge_controls.append(
                    ft.Container(
                        content=ft.Text(
                            "Em Leitura",
                            size=10,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.ON_SECONDARY_CONTAINER,
                        ),
                        bgcolor=ft.Colors.SECONDARY_CONTAINER,
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        border_radius=4,
                    )
                )

            actions_row_controls: list[ft.Control] = [
                ft.TextButton(
                    "Copiar",
                    icon=ft.Icons.CONTENT_COPY,
                    style=ft.ButtonStyle(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        text_style=ft.TextStyle(size=12),
                    ),
                    on_click=lambda e, it=item: asyncio.create_task(
                        _copiar_versao_individual(it)
                    ),
                )
            ]
            if not is_active:
                actions_row_controls.append(
                    ft.TextButton(
                        "Ler nesta versão",
                        icon=ft.Icons.MENU_BOOK,
                        style=ft.ButtonStyle(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            text_style=ft.TextStyle(size=12),
                        ),
                        on_click=lambda e, v=ver: asyncio.create_task(
                            _ler_nesta_versao(v)
                        ),
                    )
                )

            card = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=badge_controls,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                        ),
                        ft.Text(
                            txt,
                            size=self.font_size,
                            font_family=self.font_family,
                            color=ft.Colors.ON_SURFACE,
                            selectable=True,
                        ),
                        ft.Row(
                            controls=actions_row_controls,
                            alignment=ft.MainAxisAlignment.END,
                            spacing=4,
                        ),
                    ],
                    spacing=8,
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                border_radius=12,
                padding=12,
                border=ft.Border.all(
                    1,
                    ft.Colors.PRIMARY
                    if is_active
                    else ft.Colors.OUTLINE_VARIANT,
                ),
            )
            version_cards.append(card)

        bs = ft.BottomSheet(
            scrollable=True,
            show_drag_handle=True,
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(
                                            ft.Icons.COMPARE_ARROWS,
                                            size=20,
                                            color=accent_color,
                                        ),
                                        ft.Text(
                                            f"Comparar Versões — {ref_title}",
                                            weight=ft.FontWeight.BOLD,
                                            size=16,
                                            color=ft.Colors.ON_SURFACE,
                                        ),
                                    ],
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Row(
                                    controls=[
                                        ft.IconButton(
                                            ft.Icons.COPY_ALL,
                                            tooltip="Copiar todas as versões",
                                            on_click=lambda e: asyncio.create_task(
                                                _copiar_todas_as_versoes(e)
                                            ),
                                        ),
                                        ft.IconButton(
                                            ft.Icons.CLOSE,
                                            tooltip="Fechar",
                                            on_click=lambda e: self.page.pop_dialog()
                                            if self.page
                                            else None,
                                        ),
                                    ],
                                    spacing=2,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Divider(height=1),
                        ft.Column(
                            controls=version_cards,
                            spacing=10,
                            scroll=ft.ScrollMode.AUTO,
                            expand=True,
                        ),
                    ],
                    spacing=12,
                    expand=True,
                ),
                padding=ft.Padding.only(left=16, top=8, right=16, bottom=24),
                height=520,
            ),
        )
        ensure_page_dialogs(self.page)
        self.page.show_dialog(bs)


    def _navegar_para_marcador(self, book_id: int, chapter: int, versao: str) -> None:
        """Navega diretamente para o versículo/capítulo salvo."""
        if self.page:
            try:
                self.page.pop_dialog()
            except Exception:
                pass
        asyncio.create_task(
            self._carregar_capitulo(book_id, chapter, versao=versao)
        )

    def _show_marcadores_dialog(self, e=None) -> None:
        """Exibe a lista de textos bíblicos marcados e guardados."""
        if not self.page:
            return

        accent_color = self._get_accent_color()

        if not self.marcadores:
            items: list[ft.Control] = [
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(
                                ft.Icons.BOOKMARK_BORDER,
                                size=48,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                            ft.Text(
                                "Nenhum texto bíblico marcado ainda",
                                weight=ft.FontWeight.BOLD,
                                size=15,
                            ),
                            ft.Text(
                                "Toque no ícone de marcador ao lado de qualquer versículo durante a leitura para guardá-lo aqui.",
                                size=13,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    padding=ft.Padding.symmetric(vertical=40, horizontal=20),
                    alignment=ft.Alignment.CENTER,
                )
            ]
        else:
            items = []
            for k, data in sorted(
                self.marcadores.items(),
                key=lambda x: str(x[1].get("id", "")),
            ):
                book_id = data.get("book_id", 1)
                chapter = data.get("chapter", 1)
                verse = data.get("verse", 1)
                versao = data.get("version", self.selected_version)
                bname = data.get("book_name", f"Livro {book_id}")
                texto = data.get("text", "")
                marcador_key = k

                tile = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.BOOKMARK,
                                color=accent_color,
                                size=22,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Text(
                                                f"{bname} {chapter}:{verse}",
                                                weight=ft.FontWeight.BOLD,
                                                size=14,
                                            ),
                                            ft.Container(
                                                content=ft.Text(
                                                    versao,
                                                    size=10,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=accent_color,
                                                ),
                                                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                                                border_radius=4,
                                                padding=ft.Padding.symmetric(
                                                    horizontal=6, vertical=2
                                                ),
                                            ),
                                        ],
                                        spacing=6,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Text(
                                        texto,
                                        size=12,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                        max_lines=2,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_size=18,
                                tooltip="Remover marcador",
                                on_click=lambda ev, mkey=marcador_key: asyncio.create_task(
                                    self._remover_marcador_por_id(mkey)
                                ),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                    ),
                    padding=ft.Padding.symmetric(vertical=8, horizontal=10),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                    border_radius=10,
                    ink=True,
                    on_click=lambda ev, bid=book_id, ch=chapter, v_ver=versao: self._navegar_para_marcador(
                        bid, ch, v_ver
                    ),
                )
                items.append(tile)

        bs = ft.BottomSheet(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(
                                            ft.Icons.BOOKMARKS,
                                            color=accent_color,
                                            size=22,
                                        ),
                                        ft.Text(
                                            f"Textos Salvos ({len(self.marcadores)})",
                                            weight=ft.FontWeight.BOLD,
                                            size=18,
                                        ),
                                    ],
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
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
                        ft.Container(
                            content=ft.ListView(
                                controls=items, spacing=6, expand=True
                            ),
                            expand=True,
                        ),
                    ],
                    spacing=8,
                    expand=True,
                ),
                padding=ft.Padding.only(left=16, top=16, right=16, bottom=24),
                height=min(self.page.height * 0.85, 580)
                if (self.page and isinstance(self.page.height, (int, float)))
                else 520,
            )
        )
        if self.page:
            ensure_page_dialogs(self.page)
            self.page.show_dialog(bs)

    def _get_accent_color(self) -> str:
        if self.theme_service:
            return self.theme_service.get_accent_color("novo")
        return ft.Colors.PRIMARY

    def _get_book_name(self, book_id: int) -> str:
        for b in self.livros:
            if b["id"] == book_id:
                return b["name"]
        return f"Livro {book_id}"

    def _get_current_book_name(self) -> str:
        return self._get_book_name(self.current_book_id)

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
        if self.is_selection_mode:
            self.is_selection_mode = False
            self.selected_verses.clear()
            if self.view and self.normal_appbar:
                self.view.appbar = self.normal_appbar

        if self.active_screen != "leitor":
            self.active_screen = "leitor"
            if self.view:
                self.view.appbar = self.normal_appbar
                self.view.controls = [
                    ft.SafeArea(
                        maintain_bottom_view_padding=True,
                        content=self.verses_list,
                        expand=True,
                    )
                ]

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
        asyncio.create_task(self._save_preferences())

    def _update_appbar_and_nav_states(self) -> None:
        """Atualiza rótulos do AppBar e estados dos botões de anterior/próximo."""
        book_name = self._get_current_book_name()
        title_label = f"{book_name} {self.current_chapter}"

        if self.appbar_title_btn:
            self.appbar_title_btn.content = title_label

        if self.header_info_text:
            self.header_info_text.value = f"{title_label} ({self.selected_version})"

        if self.version_btn and hasattr(self.version_btn, "content"):
            try:
                self.version_btn.content.content.controls[0].value = self.selected_version
            except Exception:
                pass

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
        """Renderiza os versículos na ListView com destaque para marcadores e seleção."""
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

        # Itens de versículo com número destacado e suporte a seleção múltipla
        for v in self.current_passagem.versiculos:
            v_key = f"{self.current_book_id}_{self.current_chapter}_{v.numero}"
            is_marked = v_key in self.marcadores
            is_selected = v.numero in self.selected_verses

            if is_selected:
                row_bgcolor = (
                    ft.Colors.SURFACE_CONTAINER_HIGHEST
                    if (self.theme_service and self.theme_service.is_amoled)
                    else ft.Colors.PRIMARY_CONTAINER
                )
                row_border = ft.Border.all(1.5, accent_color)
            elif is_marked:
                row_bgcolor = ft.Colors.SURFACE_CONTAINER_HIGHEST
                row_border = ft.Border.only(left=ft.BorderSide(3, accent_color))
            else:
                row_bgcolor = None
                row_border = None

            verse_row = ft.Container(
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
                            padding=ft.Padding.only(top=4),
                        ),
                        ft.Text(
                            v.texto,
                            size=self.font_size,
                            font_family=self.font_family,
                            selectable=not self.is_selection_mode,
                            expand=True,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    spacing=8,
                ),
                padding=ft.Padding.symmetric(vertical=6, horizontal=8),
                border_radius=8,
                bgcolor=row_bgcolor,
                border=row_border,
                ink=True,
            )

            gesture_item = ft.GestureDetector(
                content=verse_row,
                on_tap=lambda ev, vn=v.numero: self._on_verse_tap(vn),
                on_long_press_start=lambda ev, vn=v.numero, vt=v.texto: self._on_verse_long_press(
                    vn, vt
                ),
                on_secondary_tap_up=lambda ev, vn=v.numero, vt=v.texto: self._on_verse_long_press(
                    vn, vt
                ),
            )
            controls.append(gesture_item)


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

    def _show_verse_context_menu(self, v_num: int, v_text: str) -> None:
        """Abre o menu de contexto estilo SO ao pressionar longamente ou clicar com botão direito em um versículo."""
        if not self.page:
            return

        book_name = self._get_current_book_name()
        v_key = f"{self.current_book_id}_{self.current_chapter}_{v_num}"
        is_marked = v_key in self.marcadores
        accent_color = self._get_accent_color()

        ref_str = f"{book_name} {self.current_chapter}:{v_num} ({self.selected_version})"
        preview_text = v_text.strip()
        if len(preview_text) > 85:
            preview_text = preview_text[:82] + "..."

        def _handle_toggle_marcador(e):
            self.page.pop_dialog()
            asyncio.create_task(self._toggle_marcador(v_num, v_text))

        def _handle_copiar(e):
            self.page.pop_dialog()
            asyncio.create_task(self._copiar_versiculo(v_num, v_text))

        def _handle_comparar(e):
            self.page.pop_dialog()
            asyncio.create_task(
                self._abrir_comparador_versoes(
                    self.current_book_id, self.current_chapter, v_num
                )
            )

        context_bs = ft.BottomSheet(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(
                                            ft.Icons.AUTO_STORIES,
                                            size=18,
                                            color=accent_color,
                                        ),
                                        ft.Text(
                                            ref_str,
                                            weight=ft.FontWeight.BOLD,
                                            size=15,
                                        ),
                                    ],
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.IconButton(
                                    ft.Icons.CLOSE,
                                    icon_size=18,
                                    tooltip="Fechar menu",
                                    on_click=lambda ev: self.page.pop_dialog(),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Text(
                            f'"{preview_text}"',
                            size=13,
                            italic=True,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Divider(height=1),
                        ft.ListTile(
                            leading=ft.Icon(
                                ft.Icons.BOOKMARK_REMOVE
                                if is_marked
                                else ft.Icons.BOOKMARK_ADD,
                                color=ft.Colors.ERROR
                                if is_marked
                                else accent_color,
                            ),
                            title=ft.Text(
                                "Desmarcar Versículo"
                                if is_marked
                                else "Marcar / Grifar Versículo",
                                weight=ft.FontWeight.W_500,
                            ),
                            subtitle=ft.Text(
                                "Remover destaque deste versículo"
                                if is_marked
                                else "Destacar versículo e salvar na lista"
                            ),
                            on_click=_handle_toggle_marcador,
                        ),
                        ft.ListTile(
                            leading=ft.Icon(
                                ft.Icons.CONTENT_COPY,
                                color=accent_color,
                            ),
                            title=ft.Text(
                                "Copiar Versículo",
                                weight=ft.FontWeight.W_500,
                            ),
                            subtitle=ft.Text(
                                "Copiar texto com referência e versão"
                            ),
                            on_click=_handle_copiar,
                        ),
                        ft.ListTile(
                            leading=ft.Icon(
                                ft.Icons.COMPARE_ARROWS,
                                color=accent_color,
                            ),
                            title=ft.Text(
                                "Comparar Versões",
                                weight=ft.FontWeight.W_500,
                            ),
                            subtitle=ft.Text(
                                "Ver este versículo em diferentes traduções"
                            ),
                            on_click=_handle_comparar,
                        ),
                    ],
                    spacing=6,
                    tight=True,
                ),
                padding=ft.Padding.only(left=16, top=16, right=16, bottom=24),
                border_radius=ft.BorderRadius.only(
                    top_left=16, top_right=16
                ),
            ),
        )
        if self.page:
            ensure_page_dialogs(self.page)
            self.page.show_dialog(context_bs)

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

    def _open_book_selection(self, e=None) -> None:
        """Abre a tela de seleção de livros em tela cheia (Plano B)."""
        self.active_screen = "livros"
        self.selected_testament = "AT" if self.current_book_id <= 39 else "NT"
        self._render_active_screen()

    def _open_chapters_selection(self, book_id: int, book_name: str) -> None:
        """Abre a tela de seleção de capítulos para um livro selecionado."""
        self.selected_modal_book = {"id": book_id, "name": book_name}
        self.active_screen = "capitulos"
        self._render_active_screen()
        asyncio.create_task(self._load_and_render_chapters(book_id))

    def _select_chapter(self, book_id: int, ch: int) -> None:
        """Seleciona um capítulo específico e retorna ao leitor."""
        self.current_book_id = book_id
        self.current_chapter = ch
        self.active_screen = "leitor"
        self._render_active_screen()
        asyncio.create_task(
            self._carregar_capitulo(
                book_id, ch, versao=self.selected_version
            )
        )

    def _back_to_leitor(self, e=None) -> None:
        """Retorna da tela de seleção diretamente para o leitor de versículos."""
        self.active_screen = "leitor"
        self._render_active_screen()

    def _show_selector_dialog(self, e=None) -> None:
        """Abre a seleção de livros em tela cheia (Plano B)."""
        self._open_book_selection(e)

    def _build_livros_appbar(self) -> ft.AppBar:
        return ft.AppBar(
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                tooltip="Voltar ao leitor",
                on_click=self._back_to_leitor,
            ),
            title=ft.Text("Selecionar Livro", weight=ft.FontWeight.BOLD, size=18),
            center_title=True,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            actions=[self.version_btn] if self.version_btn else [],
        )

    def _build_capitulos_appbar(self) -> ft.AppBar:
        bname = self.selected_modal_book.get("name", "Livro")
        return ft.AppBar(
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                tooltip="Voltar aos livros",
                on_click=self._open_book_selection,
            ),
            title=ft.Text(f"{bname} • Capítulos", weight=ft.FontWeight.BOLD, size=18),
            center_title=True,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            actions=[self.version_btn] if self.version_btn else [],
        )

    def _build_books_grid_view(self) -> ft.GridView:
        at_books = [b for b in self.livros if b.get("testament") == "AT" or b["id"] <= 39]
        nt_books = [b for b in self.livros if b.get("testament") == "NT" or b["id"] > 39]
        book_subset = at_books if self.selected_testament == "AT" else nt_books

        accent_color = self._get_accent_color()
        grid_buttons: list[ft.Control] = []

        for b in book_subset:
            book_id = b["id"]
            book_name = b["name"]
            abbrev = CANONICAL_BOOK_ABBREVIATIONS.get(book_id, book_name[:3])
            is_current = book_id == self.current_book_id

            btn = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            abbrev,
                            weight=ft.FontWeight.BOLD,
                            size=14,
                            color=ft.Colors.WHITE if is_current else None,
                        ),
                        ft.Text(
                            book_name,
                            size=9.5,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            color=ft.Colors.WHITE_70 if is_current else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2,
                ),
                bgcolor=(
                    accent_color
                    if is_current
                    else ft.Colors.SURFACE_CONTAINER_HIGHEST
                ),
                border_radius=8,
                alignment=ft.Alignment.CENTER,
                ink=True,
                padding=ft.Padding.symmetric(horizontal=4, vertical=6),
                tooltip=f"{book_name} ({abbrev})",
                on_click=lambda ev, bid=book_id, bname=book_name: self._open_chapters_selection(
                    bid, bname
                ),
            )
            grid_buttons.append(btn)

        return ft.GridView(
            runs_count=5,
            child_aspect_ratio=1.4,
            spacing=8,
            run_spacing=8,
            controls=grid_buttons,
            expand=True,
        )

    def _build_livros_content(self) -> ft.Control:
        at_books = [b for b in self.livros if b.get("testament") == "AT" or b["id"] <= 39]
        nt_books = [b for b in self.livros if b.get("testament") == "NT" or b["id"] > 39]

        if not self.selected_testament:
            self.selected_testament = "AT" if self.current_book_id <= 39 else "NT"

        def _on_testament_change(ev):
            val = list(ev.control.selected)[0]
            self.selected_testament = val
            if self.books_grid_container:
                self.books_grid_container.content = self._build_books_grid_view()
            if self.page:
                self.page.update()

        testament_bar = ft.SegmentedButton(
            selected=[self.selected_testament],
            allow_empty_selection=False,
            show_selected_icon=False,
            segments=[
                ft.Segment(
                    value="AT",
                    label=ft.Text(f"Antigo Testamento ({len(at_books)})", size=12, weight=ft.FontWeight.BOLD),
                ),
                ft.Segment(
                    value="NT",
                    label=ft.Text(f"Novo Testamento ({len(nt_books)})", size=12, weight=ft.FontWeight.BOLD),
                ),
            ],
            on_change=_on_testament_change,
        )

        self.books_grid_container = ft.Container(
            content=self._build_books_grid_view(),
            expand=True,
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=testament_bar,
                        padding=ft.Padding.only(bottom=10),
                        alignment=ft.Alignment.CENTER,
                    ),
                    self.books_grid_container,
                ],
                spacing=4,
                expand=True,
            ),
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            expand=True,
        )

    def _build_capitulos_content(self) -> ft.Control:
        bname = self.selected_modal_book.get("name", "Livro")
        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.MENU_BOOK, size=18, color=self._get_accent_color()),
                    ft.Text(f"{bname} • Escolha o Capítulo", size=14, weight=ft.FontWeight.W_500),
                ],
                spacing=8,
            ),
            padding=ft.Padding.only(bottom=8),
        )

        self.chapters_grid_container = ft.Container(
            content=ft.Container(
                content=ft.ProgressRing(color=self._get_accent_color()),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.symmetric(vertical=40),
            ),
            expand=True,
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    header,
                    self.chapters_grid_container,
                ],
                spacing=4,
                expand=True,
            ),
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            expand=True,
        )

    async def _load_and_render_chapters(self, book_id: int) -> None:
        total = await self.biblia_repository.get_total_capitulos(
            book_id, versao=self.selected_version
        )
        if total <= 0:
            total = 1

        chapter_buttons: list[ft.Control] = []
        accent_color = self._get_accent_color()

        for ch in range(1, total + 1):
            is_current = (
                book_id == self.current_book_id and ch == self.current_chapter
            )
            btn = ft.Container(
                content=ft.Text(
                    str(ch),
                    weight=ft.FontWeight.BOLD if is_current else ft.FontWeight.NORMAL,
                    size=14,
                    color=ft.Colors.WHITE if is_current else None,
                ),
                bgcolor=(
                    accent_color
                    if is_current
                    else ft.Colors.SURFACE_CONTAINER_HIGHEST
                ),
                border_radius=8,
                alignment=ft.Alignment.CENTER,
                ink=True,
                height=46,
                on_click=lambda ev, c=ch: self._select_chapter(book_id, c),
            )
            chapter_buttons.append(btn)

        grid = ft.GridView(
            runs_count=5,
            child_aspect_ratio=1.25,
            spacing=8,
            run_spacing=8,
            controls=chapter_buttons,
            expand=True,
        )
        if self.chapters_grid_container:
            self.chapters_grid_container.content = grid
            if self.page:
                self.page.update()

    def _render_active_screen(self) -> None:
        """Atualiza o AppBar e os controles da View de acordo com self.active_screen."""
        if not self.view:
            return
        if self.active_screen == "livros":
            self.view.appbar = self._build_livros_appbar()
            self.view.controls = [
                ft.SafeArea(
                    maintain_bottom_view_padding=True,
                    content=self._build_livros_content(),
                    expand=True,
                )
            ]
        elif self.active_screen == "capitulos":
            self.view.appbar = self._build_capitulos_appbar()
            self.view.controls = [
                ft.SafeArea(
                    maintain_bottom_view_padding=True,
                    content=self._build_capitulos_content(),
                    expand=True,
                )
            ]
        elif self.active_screen == "pesquisa":
            self.view.appbar = self._build_pesquisa_appbar()
            self.view.controls = [
                ft.SafeArea(
                    maintain_bottom_view_padding=True,
                    content=self._build_pesquisa_content(),
                    expand=True,
                )
            ]
        else:  # "leitor"
            self.active_screen = "leitor"
            if self.is_selection_mode:
                self._render_selection_appbar()
            else:
                self.view.appbar = self.normal_appbar
            self.view.controls = [
                ft.SafeArea(
                    maintain_bottom_view_padding=True,
                    content=self.verses_list,
                    expand=True,
                )
            ]
        if self.page:
            self.page.update()

    def _abrir_pesquisa(self, e=None) -> None:
        """Abre a tela de pesquisa da Bíblia."""
        self.active_screen = "pesquisa"
        self._render_active_screen()

    def _build_pesquisa_appbar(self) -> ft.AppBar:
        """Constrói o AppBar para a tela de pesquisa bíblica."""

        def _on_clear(e):
            if self.search_input:
                self.search_input.value = ""
            self.search_query = ""
            self.search_results = []
            self.is_searching = False
            self._render_active_screen()

        self.search_input = ft.TextField(
            value=self.search_query,
            hint_text="Palavras ou referências (ex: luz, João 3:16)...",
            prefix_icon=ft.Icons.SEARCH,
            suffix=ft.IconButton(ft.Icons.CLEAR, tooltip="Limpar", on_click=_on_clear),
            dense=True,
            border_radius=12,
            expand=True,
            autofocus=True,
            on_submit=lambda e: asyncio.create_task(
                self._executar_pesquisa(e.control.value)
            ),
        )

        return ft.AppBar(
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                tooltip="Voltar ao Leitor",
                on_click=self._back_to_leitor,
            ),
            title=self.search_input,
            center_title=False,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            actions=[
                ft.IconButton(
                    ft.Icons.SEARCH,
                    tooltip="Pesquisar",
                    on_click=lambda e: asyncio.create_task(
                        self._executar_pesquisa(
                            self.search_input.value if self.search_input else ""
                        )
                    ),
                ),
            ],
        )

    def _build_pesquisa_content(self) -> ft.Control:
        """Constrói a interface com os filtros de escopo e lista de resultados da pesquisa."""
        book_name = self._get_current_book_name()

        def _set_scope(sc: str):
            self.search_scope = sc
            if self.search_query.strip():
                asyncio.create_task(self._executar_pesquisa(self.search_query))
            else:
                self._render_active_screen()

        scope_chips = ft.Row(
            controls=[
                ft.Chip(
                    label=ft.Text("Toda a Bíblia", size=12),
                    selected=self.search_scope == "todos",
                    on_select=lambda e: _set_scope("todos"),
                ),
                ft.Chip(
                    label=ft.Text(f"Livro Atual ({book_name})", size=12),
                    selected=self.search_scope == "livro",
                    on_select=lambda e: _set_scope("livro"),
                ),
                ft.Chip(
                    label=ft.Text("Antigo Testamento", size=12),
                    selected=self.search_scope == "at",
                    on_select=lambda e: _set_scope("at"),
                ),
                ft.Chip(
                    label=ft.Text("Novo Testamento", size=12),
                    selected=self.search_scope == "nt",
                    on_select=lambda e: _set_scope("nt"),
                ),
            ],
            wrap=True,
            spacing=8,
            run_spacing=6,
        )

        if self.is_searching:
            results_view = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.ProgressRing(width=32, height=32),
                        ft.Text(
                            "Pesquisando nas Escrituras...",
                            color=ft.Colors.GREY_400,
                            size=13,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=12,
                ),
                alignment=ft.Alignment.CENTER,
                expand=True,
            )
        elif not self.search_query.strip():
            results_view = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.SEARCH, size=48, color=ft.Colors.GREY_500),
                        ft.Text(
                            "Pesquise palavras, expressões ou referências",
                            weight=ft.FontWeight.BOLD,
                            size=15,
                            color=ft.Colors.ON_SURFACE,
                        ),
                        ft.Text(
                            "Exemplos: 'luz do mundo', 'pastor', 'João 3:16', 'Salmos 23'",
                            size=13,
                            color=ft.Colors.GREY_400,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                ),
                alignment=ft.Alignment.CENTER,
                expand=True,
            )
        elif not self.search_results:
            results_view = ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(ft.Icons.SEARCH_OFF, size=48, color=ft.Colors.GREY_500),
                        ft.Text(
                            f"Nenhum versículo encontrado para '{self.search_query}'",
                            weight=ft.FontWeight.BOLD,
                            size=15,
                            color=ft.Colors.ON_SURFACE,
                        ),
                        ft.Text(
                            "Tente outras palavras ou amplie o filtro de escopo.",
                            size=13,
                            color=ft.Colors.GREY_400,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                ),
                alignment=ft.Alignment.CENTER,
                expand=True,
            )
        else:
            result_tiles: list[ft.Control] = []
            for item in self.search_results:
                bid = item["book_id"]
                ch = item["chapter"]
                vn = item["verse"]
                ref = item["referencia"]
                txt = item["text"]

                tile = ft.Container(
                    content=ft.ListTile(
                        leading=ft.Container(
                            content=ft.Text(
                                CANONICAL_BOOK_ABBREVIATIONS.get(bid, str(bid)),
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.PRIMARY,
                            ),
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                            border_radius=8,
                        ),
                        title=ft.Text(
                            ref,
                            weight=ft.FontWeight.BOLD,
                            size=14,
                            color=ft.Colors.ON_SURFACE,
                        ),
                        subtitle=ft.Text(
                            txt,
                            size=13,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        trailing=ft.Icon(
                            ft.Icons.CHEVRON_RIGHT, size=18, color=ft.Colors.GREY_400
                        ),
                        on_click=lambda e, b=bid, c=ch, v=vn: asyncio.create_task(
                            self._navegar_para_resultado_pesquisa(b, c, v)
                        ),
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                    border_radius=12,
                    margin=ft.Margin.only(bottom=6),
                )
                result_tiles.append(tile)

            results_view = ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Text(
                            f"{len(self.search_results)} versículo(s) encontrado(s) na versão {self.selected_version}",
                            size=12,
                            color=ft.Colors.GREY_400,
                        ),
                        padding=ft.Padding.symmetric(horizontal=4, vertical=6),
                    ),
                    ft.ListView(
                        controls=result_tiles,
                        expand=True,
                        spacing=4,
                    ),
                ],
                expand=True,
                spacing=6,
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=scope_chips, padding=ft.Padding.only(bottom=8)
                    ),
                    ft.Divider(height=1),
                    results_view,
                ],
                expand=True,
                spacing=6,
            ),
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            expand=True,
        )

    async def _executar_pesquisa(self, query: str | None = None) -> None:
        """Executa a pesquisa de versículos através do repositório."""
        q = (
            query
            if query is not None
            else (self.search_input.value if self.search_input else self.search_query)
        ).strip()
        self.search_query = q
        if not q:
            self.search_results = []
            self.is_searching = False
            self._render_active_screen()
            return

        self.is_searching = True
        self._render_active_screen()

        book_id = self.current_book_id if self.search_scope == "livro" else None
        testamento = (
            1
            if self.search_scope == "at"
            else (2 if self.search_scope == "nt" else None)
        )

        results = await self.biblia_repository.pesquisar_texto(
            termo=q,
            book_id=book_id,
            testamento=testamento,
            versao=self.selected_version,
            limit=100,
        )
        self.search_results = results
        self.is_searching = False
        self._render_active_screen()

    async def _navegar_para_resultado_pesquisa(
        self, book_id: int, chapter: int, verse_num: int
    ) -> None:
        """Navega para o capítulo e versículo selecionado nos resultados de busca."""
        self.current_book_id = book_id
        self.current_chapter = chapter
        self.active_screen = "leitor"
        self._render_active_screen()
        await self._carregar_capitulo(book_id, chapter, versao=self.selected_version)

    async def _select_version(self, nova_versao: str) -> None:
        """Manipula a troca de versão da Bíblia a partir do seletor popup."""
        if not nova_versao or nova_versao == self.selected_version:
            return
        self.selected_version = nova_versao.strip().upper()
        self.biblia_repository.set_version(self.selected_version)
        if self.version_dropdown:
            self.version_dropdown.value = self.selected_version
        self._update_version_btn()
        self.livros = await self.biblia_repository.listar_livros(
            versao=self.selected_version
        )
        if self.active_screen == "livros":
            self._render_active_screen()
        elif self.active_screen == "capitulos":
            await self._load_and_render_chapters(self.selected_modal_book["id"])
        else:
            await self._carregar_capitulo(
                self.current_book_id, self.current_chapter, versao=self.selected_version
            )

    def _update_version_btn(self) -> None:
        """Atualiza o texto e itens do botão de versão da Bíblia."""
        if not self.version_btn:
            return
        update_bible_version_button(
            self.version_btn,
            self.selected_version,
            self.biblia_repository,
            self._select_version,
        )

    async def _on_version_changed(self, e) -> None:
        """Manipula a troca de versão da Bíblia a partir do Dropdown."""
        nova_versao = e.control.value
        await self._select_version(nova_versao)

    def _show_font_accessibility_modal(self, page: ft.Page | None = None) -> None:
        """Abre um modal (BottomSheet) para ajuste do tamanho e família da fonte do texto bíblico."""
        p = page or self.page
        accent_color = self._get_accent_color()

        self._modal_font_size_text = ft.Text(
            f"{self.font_size}pt",
            weight=ft.FontWeight.BOLD,
            size=16,
        )

        def _update_font_size_ui():
            if hasattr(self, "_modal_font_size_text") and self._modal_font_size_text:
                self._modal_font_size_text.value = f"{self.font_size}pt"
            self._render_verses()
            asyncio.create_task(self._save_preferences())
            if p:
                p.update()

        def _on_increase(e):
            if self.font_size < 32:
                self.font_size += 2
                _update_font_size_ui()

        def _on_decrease(e):
            if self.font_size > 12:
                self.font_size -= 2
                _update_font_size_ui()

        def _on_reset(e):
            self.font_size = 17
            _update_font_size_ui()

        def _on_font_change(font_name: str):
            self.font_family = font_name
            self._render_verses()
            asyncio.create_task(self._save_preferences())
            if p:
                p.update()

        font_options = [
            ("Roboto", "Roboto (Padrão)"),
            ("Merriweather", "Merriweather (Serifada)"),
            ("Times New Roman", "Times New Roman (Clássica)"),
            ("Montserrat", "Montserrat (Moderna)"),
            ("Inter", "Inter (Clean)"),
            ("OpenDyslexic", "OpenDyslexic (Acessível)"),
        ]

        font_radios = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value=val, label=lbl) for val, lbl in font_options
                ],
                spacing=6,
            ),
            value=self.font_family,
            on_change=lambda e: _on_font_change(e.control.value),
        )

        bs = ft.BottomSheet(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Icon(
                                            ft.Icons.FORMAT_SIZE,
                                            color=accent_color,
                                            size=22,
                                        ),
                                        ft.Text(
                                            "Aparência e Fonte do Texto",
                                            weight=ft.FontWeight.BOLD,
                                            size=16,
                                        ),
                                    ],
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.IconButton(
                                    ft.Icons.CLOSE,
                                    tooltip="Fechar",
                                    on_click=lambda ev: p.pop_dialog() if p else None,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Divider(height=1),
                        ft.Text(
                            "Tamanho da Letra:",
                            weight=ft.FontWeight.W_500,
                            size=14,
                        ),
                        ft.Row(
                            controls=[
                                ft.IconButton(
                                    ft.Icons.REMOVE_CIRCLE_OUTLINE,
                                    tooltip="Diminuir",
                                    on_click=_on_decrease,
                                ),
                                self._modal_font_size_text,
                                ft.IconButton(
                                    ft.Icons.ADD_CIRCLE_OUTLINE,
                                    tooltip="Aumentar",
                                    on_click=_on_increase,
                                ),
                                ft.TextButton(
                                    "Resetar",
                                    tooltip="Redefinir para 17pt",
                                    on_click=_on_reset,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Divider(height=1),
                        ft.Text(
                            "Família da Fonte:",
                            weight=ft.FontWeight.W_500,
                            size=14,
                        ),
                        font_radios,
                    ],
                    tight=True,
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=ft.Padding.only(left=20, top=16, right=20, bottom=32),
            ),
            show_drag_handle=True,
        )
        self.font_accessibility_bs = bs
        if p:
            ensure_page_dialogs(p)
            p.show_dialog(bs)

    def _zoom_in(self, e=None) -> None:
        if self.font_size < 32:
            self.font_size += 2
            self._render_verses()
            asyncio.create_task(self._save_preferences())

    def _zoom_out(self, e=None) -> None:
        if self.font_size > 12:
            self.font_size -= 2
            self._render_verses()
            asyncio.create_task(self._save_preferences())

    async def build(
        self,
        page: ft.Page,
        initial_book_id: int | None = None,
        initial_chapter: int | None = None,
        initial_version: str | None = None,
    ) -> ft.View:
        self.page = page

        if self.theme_service:
            self.theme_service.apply_theme(page, edition="novo")

        # Restaura sessão do SQLite caso não seja navegação explícita por rota
        restore_session = initial_book_id is None
        await self._load_preferences_and_bookmarks(restore_session=restore_session)

        if initial_book_id is not None:
            self.current_book_id = initial_book_id
        if initial_chapter is not None:
            self.current_chapter = initial_chapter
        if initial_version:
            self.selected_version = initial_version.strip().upper()
            self.biblia_repository.set_version(self.selected_version)

        # Carrega os livros da Bíblia
        await self._load_books()

        # Botão central com o Livro e Capítulo no AppBar
        self.appbar_title_btn = ft.TextButton(
            f"{self._get_current_book_name()} {self.current_chapter}",
            icon=ft.Icons.KEYBOARD_ARROW_DOWN,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE
                if self.theme_service and self.theme_service.is_amoled
                else None,
                text_style=ft.TextStyle(size=16, weight=ft.FontWeight.BOLD),
            ),
            tooltip="Selecionar Livro e Capítulo",
            on_click=self._show_selector_dialog,
        )

        versoes_disponiveis = self.biblia_repository.get_available_versions()
        self.version_dropdown = ft.Dropdown(
            options=[ft.dropdown.Option(key=v, text=v) for v in versoes_disponiveis],
            value=self.selected_version,
            visible=False,
            on_select=self._on_version_changed,
        )

        self.version_btn = build_bible_version_button(
            biblia_repository=self.biblia_repository,
            current_version=self.selected_version,
            on_version_selected=self._select_version,
            theme_service=self.theme_service,
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

        self.normal_appbar = ft.AppBar(
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
                self.version_btn,
                ft.IconButton(
                    ft.Icons.SEARCH,
                    tooltip="Pesquisar na Bíblia",
                    on_click=self._abrir_pesquisa,
                ),
                ft.IconButton(
                    ft.Icons.BOOKMARKS_OUTLINED,
                    tooltip="Textos Bíblicos Marcados",
                    on_click=self._show_marcadores_dialog,
                ),
                ft.PopupMenuButton(
                    icon=ft.Icons.MORE_VERT,
                    tooltip="Opções de Leitura",
                    items=[
                        ft.PopupMenuItem(
                            "Pesquisar na Bíblia",
                            icon=ft.Icons.SEARCH,
                            on_click=self._abrir_pesquisa,
                        ),
                        ft.PopupMenuItem(
                            "Copiar Capítulo Completo",
                            icon=ft.Icons.CONTENT_COPY,
                            on_click=self._copiar_capitulo,
                        ),
                        ft.PopupMenuItem(
                            "Textos Salvos / Marcadores",
                            icon=ft.Icons.BOOKMARK,
                            on_click=self._show_marcadores_dialog,
                        ),
                        ft.PopupMenuItem(
                            "Aparência e Fonte do Texto",
                            icon=ft.Icons.FORMAT_SIZE,
                            on_click=lambda e: self._show_font_accessibility_modal(page),
                        ),
                        ft.PopupMenuItem(
                            "Selecionar Livro / Capítulo",
                            icon=ft.Icons.MENU_BOOK,
                            on_click=self._show_selector_dialog,
                        ),
                    ],
                ),
            ],
        )

        self.active_screen = "leitor"
        self.view = ft.View(
            route="/biblia",
            bgcolor=ft.Colors.SURFACE,
            appbar=self.normal_appbar,
            controls=[
                ft.SafeArea(
                    maintain_bottom_view_padding=True,
                    content=self.verses_list,
                    expand=True,
                )
            ],
        )
        return self.view
