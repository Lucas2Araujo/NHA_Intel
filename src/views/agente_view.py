import flet as ft
from typing import Optional, Dict, Any, List
from src.services.agente_service import AgenteService
from src.repositories.culto_repository import CultoRepository


class AgenteView:
    """
    View responsável pela interface do Agente Organizador de Cultos.
    Totalmente responsiva em retrato e paisagem (landscape).
    Oferece duas abas:
    1. 'Novo Culto': Sugestão semântica inteligente e montagem de playlist por blocos litúrgicos.
    2. 'Cultos Salvos': Consulta e navegação em listas de cultos salvas anteriormente no banco.
    """

    def __init__(
        self, agente_service: AgenteService, culto_repository: CultoRepository
    ):
        self.agente_service = agente_service
        self.culto_repository = culto_repository
        self.playlist_gerada: Optional[Dict[str, Any]] = None
        self.current_tab: str = "novo"  # "novo" ou "salvos"
        self.num_hinos_value: int = 6  # valor padrão

        # Componentes visuais e de controle
        self.results_container: Optional[ft.Column] = None
        self.prompt_input: Optional[ft.TextField] = None
        self.save_button: Optional[ft.FilledButton] = None
        self.generate_button: Optional[ft.FilledButton] = None
        self.prompt_card: Optional[ft.Card] = None
        self.num_hinos_label: Optional[ft.Text] = None
        self.num_hinos_slider: Optional[ft.Slider] = None
        self.example_chips: Optional[ft.Row] = None
        self.tab_bar: Optional[ft.SegmentedButton] = None

    def build(self, page: ft.Page) -> ft.View:
        page.title = "Agente Organizador de Cultos - v0.2"

        self._init_controls(page)

        scrollable_controls: List[ft.Control] = [
            ctrl
            for ctrl in (self.prompt_card, ft.Divider(height=1), self.results_container)
            if ctrl is not None
        ]

        scrollable_content = ft.Column(
            controls=scrollable_controls,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=10,
        )

        view_controls: List[ft.Control] = []
        if self.tab_bar:
            view_controls.append(
                ft.Container(
                    content=self.tab_bar,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                )
            )
        view_controls.append(
            ft.Container(
                content=scrollable_content,
                expand=True,
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            )
        )

        return ft.View(
            route="/agente",
            appbar=self._build_app_bar(page),
            controls=view_controls,
        )

    def _init_controls(self, page: ft.Page) -> None:
        self.num_hinos_label = ft.Text(
            f"Hinos: {self.num_hinos_value}",
            weight=ft.FontWeight.BOLD,
            size=13,
        )

        self.num_hinos_slider = ft.Slider(
            min=4,
            max=10,
            divisions=6,
            value=self.num_hinos_value,
            label="{value} hinos",
            on_change=lambda e: self._on_slider_change(e, page),
            expand=True,
        )

        self.prompt_input = ft.TextField(
            hint_text="Digite o tema pastoral do culto (ex: 'Fé e Perseverança nas Provações')...",
            multiline=True,
            min_lines=1,
            max_lines=3,
            border_radius=12,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            expand=True,
        )

        self.results_container = ft.Column(
            controls=[],
            spacing=12,
        )

        self.save_button = ft.FilledButton(
            "Salvar Lista de Culto",
            icon=ft.Icons.SAVE,
            visible=False,
            on_click=lambda e: page.run_task(self._salvar_lista, page),
        )

        self.generate_button = ft.FilledButton(
            "Gerar Sugestão de Culto",
            icon=ft.Icons.AUTO_AWESOME,
            on_click=lambda e: page.run_task(self._gerar_playlist, page),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE_700,
                color=ft.Colors.WHITE,
            ),
        )

        example_themes = [
            "Gratidão",
            "Batismo",
            "Páscoa",
            "Fé",
            "Família",
            "Esperança",
            "Louvor",
            "Natal",
        ]
        self.example_chips = ft.Row(
            controls=[
                ft.Chip(
                    label=ft.Text(t, size=12),
                    on_click=lambda e, theme=t: self._on_chip_click(
                        page, theme
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                )
                for t in example_themes
            ],
            wrap=True,
            spacing=6,
            run_spacing=6,
        )

        self.tab_bar = ft.SegmentedButton(
            selected=[self.current_tab],
            segments=[
                ft.Segment(
                    value="novo",
                    label=ft.Text("Novo Culto"),
                    icon=ft.Icons.AUTO_AWESOME,
                ),
                ft.Segment(
                    value="salvos",
                    label=ft.Text("Cultos Salvos"),
                    icon=ft.Icons.BOOKMARK_ADDED,
                ),
            ],
            on_change=lambda e: page.run_task(
                self._on_tab_change, page, e.control.selected
            ),
            expand=True,
        )

        prompt_controls: List[ft.Control] = [
            ft.Text(
                "Defina o Tema Pastoral do Culto:",
                weight=ft.FontWeight.BOLD,
                size=15,
            ),
            ft.Text(
                "Clique em um tema de exemplo ou escreva o seu:",
                size=12,
                italic=True,
                color=ft.Colors.GREY_400,
            ),
        ]
        if self.example_chips:
            prompt_controls.append(self.example_chips)
        if self.prompt_input:
            prompt_controls.append(self.prompt_input)

        slider_controls: List[ft.Control] = [
            c for c in (self.num_hinos_label, self.num_hinos_slider) if c is not None
        ]
        prompt_controls.append(
            ft.Row(
                controls=slider_controls,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )

        button_controls: List[ft.Control] = [
            c for c in (self.generate_button, self.save_button) if c is not None
        ]
        prompt_controls.append(
            ft.Row(
                controls=button_controls,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                wrap=True,
            )
        )

        self.prompt_card = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=prompt_controls,
                    spacing=10,
                ),
                padding=ft.Padding.all(14),
            )
        )

    def _build_app_bar(self, page: ft.Page) -> ft.AppBar:
        return ft.AppBar(
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                on_click=lambda e: page.run_task(self._go_back, page),
            ),
            title=ft.Row(
                controls=[
                    ft.Text("Agente de Cultos", weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=ft.Text(
                            "v0.2",
                            size=11,
                            color=ft.Colors.AMBER_200,
                            weight=ft.FontWeight.BOLD,
                        ),
                        padding=ft.Padding.only(left=4),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
            ),
            center_title=True,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            actions=[
                ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.AMBER_300),
            ],
        )

    def _on_slider_change(self, e: ft.ControlEvent, page: ft.Page) -> None:
        if isinstance(e.control, ft.Slider) and e.control.value is not None:
            self.num_hinos_value = int(e.control.value)
        if self.num_hinos_label:
            self.num_hinos_label.value = f"Hinos: {self.num_hinos_value}"
        page.update()

    def _on_chip_click(self, page: ft.Page, theme_text: str) -> None:
        if self.prompt_input:
            self.prompt_input.value = theme_text
        page.update()

    async def _salvar_lista(self, page: ft.Page) -> None:
        if not self.playlist_gerada or not self.playlist_gerada.get("hinos"):
            return

        tema = self.playlist_gerada.get("tema", "Culto")
        hino_ids = [
            h.id
            for h in self.playlist_gerada.get("hinos", [])
            if h.id is not None
        ]

        lista_id = await self.culto_repository.create_lista_culto(tema, hino_ids)
        if lista_id:
            msg = f"Lista de Culto '{tema}' salva com sucesso no banco!"
        else:
            msg = "Falha ao salvar a lista de culto."

        snack = ft.SnackBar(content=ft.Text(msg))
        page.overlay.append(snack)
        snack.open = True
        page.update()

    async def _gerar_playlist(self, page: ft.Page) -> None:
        tema = self.prompt_input.value if self.prompt_input and self.prompt_input.value else ""

        if self.results_container:
            self.results_container.controls = [
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.ProgressRing(),
                            ft.Text(
                                "O Agente está selecionando os hinos mais adequados...",
                                italic=True,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=15,
                    ),
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.all(30),
                )
            ]
        page.update()

        self.playlist_gerada = await self.agente_service.sugerir_playlist_culto(
            tema, num_hinos=self.num_hinos_value
        )
        
        self._refresh_novo_culto(page)
        if self.save_button:
            self.save_button.visible = True
        page.update()

    def _refresh_novo_culto(self, page: ft.Page):
        blocos = self.playlist_gerada.get("blocos", []) if self.playlist_gerada else []
        controls: List[ft.Control] = [self._build_bloco_card(item, page) for item in blocos]
        
        btn_add = ft.TextButton(
            "+ Adicionar Hino",
            icon=ft.Icons.ADD,
            on_click=lambda e: self._abrir_dialogo_busca_hino(
                page, lambda h: self._adicionar_em_memoria(page, h)
            )
        )
        controls.append(ft.Container(content=btn_add, alignment=ft.Alignment.CENTER))
        
        if self.results_container:
            self.results_container.controls = controls
        page.update()

    def _adicionar_em_memoria(self, page: ft.Page, hino):
        if not self.playlist_gerada:
            tema_default = self.prompt_input.value if self.prompt_input and self.prompt_input.value else "Culto Ad Hoc"
            self.playlist_gerada = {"hinos": [], "blocos": [], "tema": tema_default}
        novo_item = {"bloco": "Hino Adicional", "hino": hino, "justificativa": ""}
        self.playlist_gerada.setdefault("blocos", []).append(novo_item)
        self.playlist_gerada.setdefault("hinos", []).append(hino)
        self._refresh_novo_culto(page)
        
    def _substituir_em_memoria(self, page: ft.Page, item: Dict[str, Any], novo_hino):
        if not self.playlist_gerada:
            return
        item["hino"] = novo_hino
        blocos = self.playlist_gerada.get("blocos", [])
        self.playlist_gerada["hinos"] = [i["hino"] for i in blocos if "hino" in i]
        self._refresh_novo_culto(page)

    def _remover_em_memoria(self, page: ft.Page, item: Dict[str, Any]):
        if not self.playlist_gerada:
            return
        blocos = self.playlist_gerada.get("blocos", [])
        if item in blocos:
            blocos.remove(item)
        self.playlist_gerada["hinos"] = [i["hino"] for i in blocos if "hino" in i]
        self._refresh_novo_culto(page)

    def _build_bloco_card(
        self, item: Dict[str, Any], page: ft.Page
    ) -> ft.Card:
        hino = item["hino"]
        nome_bloco = item["bloco"]

        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            nome_bloco,
                            weight=ft.FontWeight.BOLD,
                            size=13,
                            color=ft.Colors.BLUE_200,
                        ),
                        ft.ListTile(
                            leading=ft.Text(
                                hino.numero, weight=ft.FontWeight.BOLD, size=16
                            ),
                            title=ft.Text(
                                hino.titulo, weight=ft.FontWeight.W_500, size=16
                            ),
                            on_click=lambda ev, h_id=hino.id: page.run_task(
                                page.push_route, f"/hino/{h_id}"
                            ),
                            trailing=ft.PopupMenuButton(
                                icon=ft.Icons.MORE_VERT,
                                items=[
                                    ft.PopupMenuItem(
                                        content=ft.Text("Substituir"),
                                        icon=ft.Icons.SWAP_HORIZ,
                                        on_click=lambda e: self._abrir_dialogo_busca_hino(
                                            page, lambda novo_hino: self._substituir_em_memoria(page, item, novo_hino)
                                        )
                                    ),
                                    ft.PopupMenuItem(
                                        content=ft.Text("Remover"),
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        on_click=lambda e: self._remover_em_memoria(page, item)
                                    ),
                                ]
                            ),
                        ),
                    ],
                    spacing=4,
                ),
                padding=ft.Padding.all(12),
            )
        )

    async def _carregar_cultos_salvos(self, page: ft.Page) -> None:
        listas = await self.culto_repository.get_listas_culto()
        if not self.results_container:
            return

        if not listas:
            self.results_container.controls = [
                ft.Container(
                    content=ft.Text(
                        "Nenhuma lista de culto salva anteriormente.",
                        italic=True,
                        size=14,
                    ),
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.all(30),
                )
            ]
            return

        self.results_container.controls = [
            self._build_salvos_card(lista, page) for lista in listas
        ]

    def _build_salvos_card(
        self, lista: Dict[str, Any], page: ft.Page
    ) -> ft.Card:
        l_id = lista["id"]
        tema = lista["tema_gerador"]
        data = lista["data_criacao"]
        total = lista["total_hinos"]

        return ft.Card(
            content=ft.Container(
                content=ft.ListTile(
                    leading=ft.Icon(
                        ft.Icons.BOOKMARK, color=ft.Colors.AMBER_300
                    ),
                    title=ft.Text(tema, weight=ft.FontWeight.BOLD, size=15),
                    subtitle=ft.Text(
                        f"Criado em: {data} • {total} hinos",
                        size=12,
                        color=ft.Colors.GREY_400,
                    ),
                    on_click=lambda ev, l_id=l_id, t=tema: page.run_task(
                        self._ver_hinos_culto, page, l_id, t
                    ),
                    trailing=ft.PopupMenuButton(
                        icon=ft.Icons.MORE_VERT,
                        items=[
                            ft.PopupMenuItem(
                                content=ft.Text("Copiar Lista"),
                                icon=ft.Icons.CONTENT_COPY,
                                on_click=lambda ev, l_id=l_id, t=tema: page.run_task(self._copiar_culto, page, l_id, t)
                            ),
                            ft.PopupMenuItem(
                                content=ft.Text("Renomear"),
                                icon=ft.Icons.EDIT,
                                on_click=lambda ev, l_id=l_id, t=tema: self._abrir_dialogo_renomear(page, l_id, t)
                            ),
                            ft.PopupMenuItem(
                                content=ft.Text("Excluir"),
                                icon=ft.Icons.DELETE,
                                on_click=lambda ev, l_id=l_id, t=tema: self._abrir_dialogo_excluir(page, l_id, t)
                            ),
                        ]
                    ),
                ),
                padding=ft.Padding.all(8),

            )
        )

    async def _ver_hinos_culto(
        self, page: ft.Page, lista_id: int, tema_culto: str
    ) -> None:
        hinos = await self.culto_repository.get_hinos_da_lista(lista_id)
        items: list[ft.Control] = [
            ft.Row(
                controls=[
                    ft.Text(
                        f"Hinos do Culto: {tema_culto}",
                        weight=ft.FontWeight.BOLD,
                        size=16,
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE, on_click=lambda e: page.pop_dialog()
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Divider(),
        ]
        for idx, h in enumerate(hinos, start=1):
            if h.id is None:
                continue
            items.append(
                ft.ListTile(
                    leading=ft.Text(f"{idx}º", weight=ft.FontWeight.BOLD),
                    title=ft.Text(f"Hino {h.numero} - {h.titulo}"),
                    on_click=lambda e, h_id=h.id: page.run_task(
                        page.push_route, f"/hino/{h_id}"
                    ),
                    trailing=ft.PopupMenuButton(
                        icon=ft.Icons.MORE_VERT,
                        items=[
                            ft.PopupMenuItem(
                                content=ft.Text("Substituir"),
                                icon=ft.Icons.SWAP_HORIZ,
                                on_click=lambda e, old_h_id=h.id: self._abrir_dialogo_busca_hino(
                                    page, lambda novo_hino: page.run_task(self._substituir_no_banco, page, lista_id, old_h_id, novo_hino, tema_culto)
                                )
                            ),
                            ft.PopupMenuItem(
                                content=ft.Text("Remover"),
                                icon=ft.Icons.DELETE_OUTLINE,
                                on_click=lambda e, l_id=lista_id, h_id=h.id, t=tema_culto: page.run_task(self._remover_hino_culto, page, l_id, h_id, t)
                            ),
                        ]
                    ),
                )
            )
        
        btn_add = ft.TextButton(
            "+ Adicionar Hino",
            icon=ft.Icons.ADD,
            on_click=lambda e: self._abrir_dialogo_busca_hino(
                page, lambda novo_hino: page.run_task(self._adicionar_no_banco, page, lista_id, novo_hino, tema_culto)
            )
        )
        items.append(ft.Container(content=btn_add, alignment=ft.Alignment.CENTER))

        bs = ft.BottomSheet(
            content=ft.Container(
                content=ft.Column(controls=items, tight=True, spacing=8),
                padding=ft.Padding.all(20),
            )
        )
        page.show_dialog(bs)

    async def _remover_hino_culto(self, page: ft.Page, lista_id: int, hino_id: int, tema_culto: str) -> None:
        sucesso = await self.culto_repository.remove_hino_da_lista(lista_id, hino_id)
        if sucesso:
            page.pop_dialog()
            await self._carregar_cultos_salvos(page)
            await self._ver_hinos_culto(page, lista_id, tema_culto)
            snack = ft.SnackBar(content=ft.Text("Hino removido do culto!"))
            page.overlay.append(snack)
            snack.open = True
            page.update()

    async def _substituir_no_banco(self, page: ft.Page, lista_id: int, old_hino_id: int, novo_hino, tema_culto: str):
        if await self.culto_repository.update_hino_da_lista(lista_id, old_hino_id, novo_hino.id):
            page.pop_dialog()
            await self._carregar_cultos_salvos(page)
            await self._ver_hinos_culto(page, lista_id, tema_culto)
            snack = ft.SnackBar(content=ft.Text(f"Hino substituído por '{novo_hino.titulo}'!"))
            page.overlay.append(snack)
            snack.open = True
            page.update()

    async def _adicionar_no_banco(self, page: ft.Page, lista_id: int, novo_hino, tema_culto: str):
        if await self.culto_repository.add_hino_a_lista(lista_id, novo_hino.id):
            page.pop_dialog()
            await self._carregar_cultos_salvos(page)
            await self._ver_hinos_culto(page, lista_id, tema_culto)
            snack = ft.SnackBar(content=ft.Text(f"Hino '{novo_hino.titulo}' adicionado!"))
            page.overlay.append(snack)
            snack.open = True
            page.update()

    def _abrir_dialogo_busca_hino(self, page: ft.Page, on_selected):
        txt_busca = ft.TextField(
            label="Buscar por número ou nome", 
            on_change=lambda e: page.run_task(buscar_hinos, e.control.value),
            autofocus=True,
            expand=True
        )
        lista_resultados = ft.ListView(expand=True, spacing=10, height=300)

        async def buscar_hinos(termo: str):
            resultados = await self.agente_service.hino_repository.search(termo)
            lista_resultados.controls.clear()
            for h in resultados[:20]:
                lista_resultados.controls.append(
                    ft.ListTile(
                        leading=ft.Text(h.numero, weight=ft.FontWeight.BOLD),
                        title=ft.Text(h.titulo),
                        on_click=lambda e, hino=h: selecionar(hino)
                    )
                )
            page.update()

        def selecionar(hino):
            page.pop_dialog()
            on_selected(hino)

        def fechar(e):
            page.pop_dialog()

        dlg = ft.AlertDialog(
            title=ft.Text("Buscar Hino"),
            content=ft.Container(
                content=ft.Column([txt_busca, lista_resultados], tight=True),
                width=400,
                padding=10
            ),
            actions=[ft.TextButton("Cancelar", on_click=fechar)]
        )
        page.show_dialog(dlg)

    async def _copiar_culto(self, page: ft.Page, lista_id: int, tema_culto: str):
        hinos = await self.culto_repository.get_hinos_da_lista(lista_id)
        text = f"Culto: {tema_culto}\n\n"
        for i, h in enumerate(hinos, 1):
            text += f"{i}. Hino {h.numero} - {h.titulo}\n"
        
        await ft.Clipboard().set(text)
        snack = ft.SnackBar(content=ft.Text("Lista copiada para a área de transferência!"))
        page.overlay.append(snack)
        snack.open = True
        page.update()

    def _abrir_dialogo_renomear(self, page: ft.Page, lista_id: int, tema_atual: str):
        txt_nome = ft.TextField(value=tema_atual, label="Nome do Culto", expand=True)
        
        def fechar(e):
            page.pop_dialog()
            
        def salvar(e):
            page.pop_dialog()
            page.run_task(self._confirmar_renomear, page, lista_id, txt_nome.value)

        dlg = ft.AlertDialog(
            title=ft.Text("Renomear Culto"),
            content=ft.Container(content=txt_nome, padding=10),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.TextButton("Salvar", on_click=salvar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dlg)

    async def _confirmar_renomear(self, page: ft.Page, lista_id: int, novo_nome: str):
        if await self.culto_repository.rename_lista_culto(lista_id, novo_nome):
            await self._carregar_cultos_salvos(page)
            snack = ft.SnackBar(content=ft.Text("Culto renomeado com sucesso!"))
        else:
            snack = ft.SnackBar(content=ft.Text("Erro ao renomear culto."))
        page.overlay.append(snack)
        snack.open = True
        page.update()

    def _abrir_dialogo_excluir(self, page: ft.Page, lista_id: int, tema_culto: str):
        def fechar(e):
            page.pop_dialog()
            
        def deletar(e):
            page.pop_dialog()
            page.run_task(self._confirmar_excluir, page, lista_id)

        dlg = ft.AlertDialog(
            title=ft.Text("Excluir Culto"),
            content=ft.Text(f"Tem certeza que deseja excluir permanentemente a lista '{tema_culto}'?"),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.TextButton("Excluir", on_click=deletar, style=ft.ButtonStyle(color=ft.Colors.RED_400)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dlg)

    async def _confirmar_excluir(self, page: ft.Page, lista_id: int):
        if await self.culto_repository.delete_lista_culto(lista_id):
            await self._carregar_cultos_salvos(page)
            snack = ft.SnackBar(content=ft.Text("Culto excluído com sucesso!"))
        else:
            snack = ft.SnackBar(content=ft.Text("Erro ao excluir culto."))
        page.overlay.append(snack)
        snack.open = True
        page.update()


    async def _on_tab_change(
        self, page: ft.Page, selected: List[str]
    ) -> None:
        if "salvos" in selected:
            self.current_tab = "salvos"
            if self.prompt_card:
                self.prompt_card.visible = False
            await self._carregar_cultos_salvos(page)
        else:
            self.current_tab = "novo"
            if self.prompt_card:
                self.prompt_card.visible = True
            if self.results_container:
                self.results_container.controls = []
            if self.save_button:
                self.save_button.visible = False

        page.update()

    async def _go_back(self, page: ft.Page) -> None:
        if len(page.views) > 1:
            page.views.pop()
            top_view = page.views[-1]
            await page.push_route(top_view.route)
        else:
            await page.push_route("/")
