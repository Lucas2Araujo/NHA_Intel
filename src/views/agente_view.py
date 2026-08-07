import flet as ft
from typing import Optional, Dict, Any, List
from src.services.agente_service import AgenteService
from src.repositories.culto_repository import CultoRepository


class AgenteView:
    """
    View responsável pela interface do Agente Organizador de Cultos.
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

    async def build(self, page: ft.Page) -> ft.View:
        page.title = "Agente Organizador de Cultos"

        # Slider de quantidade de hinos
        num_hinos_value = 6  # valor padrão

        num_hinos_label = ft.Text(f"Hinos: {num_hinos_value}", weight=ft.FontWeight.BOLD, size=13)

        def _on_slider_change(e):
            nonlocal num_hinos_value
            num_hinos_value = int(e.control.value)
            num_hinos_label.value = f"Hinos: {num_hinos_value}"
            page.update()

        num_hinos_slider = ft.Slider(
            min=4,
            max=10,
            divisions=6,
            value=num_hinos_value,
            label="{value} hinos",
            on_change=_on_slider_change,
            expand=True,
        )

        prompt_input = ft.TextField(
            hint_text="Digite o tema pastoral do culto (ex: 'Fé e Perseverança nas Provações')...",
            multiline=True,
            min_lines=2,
            max_lines=3,
            border_radius=12,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            expand=True,
        )

        results_container = ft.Column(
            controls=[],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        save_button = ft.ElevatedButton(
            "Salvar Lista de Culto",
            icon=ft.Icons.SAVE,
            visible=False,
        )

        async def _salvar_lista(e=None):
            if not self.playlist_gerada or not self.playlist_gerada.get("hinos"):
                return

            tema = self.playlist_gerada.get("tema", "Culto")
            hino_ids = [
                h.id for h in self.playlist_gerada.get("hinos", []) if h.id is not None
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

        save_button.on_click = lambda e: page.run_task(_salvar_lista)

        async def _gerar_playlist(e=None):
            tema = prompt_input.value or ""

            results_container.controls = [
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
                tema, num_hinos=num_hinos_value
            )
            blocos = self.playlist_gerada.get("blocos", [])

            cards = []
            for item in blocos:
                hino = item["hino"]
                nome_bloco = item["bloco"]

                card = ft.Card(
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
                                    trailing=ft.IconButton(
                                        ft.Icons.ARROW_FORWARD_IOS,
                                        icon_size=16,
                                        on_click=lambda ev, h_id=hino.id: page.go(
                                            f"/hino/{h_id}"
                                        ),
                                    ),
                                ),
                            ],
                            spacing=4,
                        ),
                        padding=ft.Padding.all(12),
                    )
                )
                cards.append(card)

            results_container.controls = cards
            save_button.visible = True
            page.update()

        generate_button = ft.ElevatedButton(
            "Gerar Sugestão de Culto",
            icon=ft.Icons.AUTO_AWESOME,
            on_click=lambda e: page.run_task(_gerar_playlist),
            bgcolor=ft.Colors.BLUE_700,
            color=ft.Colors.WHITE,
        )

        # Chips de exemplo clicáveis para orientar o usuário
        example_themes = ["Gratidão", "Batismo", "Páscoa", "Fé", "Família", "Esperança", "Louvor", "Natal"]

        def _on_chip_click(e, theme_text: str):
            prompt_input.value = theme_text
            page.update()

        example_chips = ft.Row(
            controls=[
                ft.Chip(
                    label=ft.Text(t, size=12),
                    on_click=lambda e, t=t: _on_chip_click(e, t),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                )
                for t in example_themes
            ],
            wrap=True,
            spacing=6,
            run_spacing=6,
        )

        async def _carregar_cultos_salvos():
            listas = await self.culto_repository.get_listas_culto()
            if not listas:
                results_container.controls = [
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

            cards = []
            for lista in listas:
                l_id = lista["id"]
                tema = lista["tema_gerador"]
                data = lista["data_criacao"]
                total = lista["total_hinos"]

                async def _ver_hinos_culto(ev, lista_id=l_id, tema_culto=tema):
                    hinos = await self.culto_repository.get_hinos_da_lista(lista_id)
                    items = [
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
                        items.append(
                            ft.ListTile(
                                leading=ft.Text(f"{idx}º", weight=ft.FontWeight.BOLD),
                                title=ft.Text(f"Hino {h.numero} - {h.titulo}"),
                                on_click=lambda e, h_id=h.id: page.go(f"/hino/{h_id}"),
                            )
                        )
                    bs = ft.BottomSheet(
                        content=ft.Container(
                            content=ft.Column(controls=items, tight=True, spacing=8),
                            padding=ft.Padding.all(20),
                        )
                    )
                    page.show_dialog(bs)

                card = ft.Card(
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
                            trailing=ft.IconButton(
                                ft.Icons.PLAY_ARROW,
                                tooltip="Ver Hinos deste Culto",
                                on_click=lambda ev, l_id=l_id, t=tema: page.run_task(
                                    _ver_hinos_culto, ev, l_id, t
                                ),
                            ),
                        ),
                        padding=ft.Padding.all(8),
                    )
                )
                cards.append(card)

            results_container.controls = cards

        # Alternância entre abas
        async def _on_tab_change(e):
            selected = e.control.selected
            if "salvos" in selected:
                self.current_tab = "salvos"
                prompt_container.visible = False
                await _carregar_cultos_salvos()
            else:
                self.current_tab = "novo"
                prompt_container.visible = True
                results_container.controls = []
                save_button.visible = False

            page.update()

        tab_bar = ft.SegmentedButton(
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
            on_change=_on_tab_change,
            expand=True,
        )

        prompt_container = ft.Container(
            content=ft.Column(
                controls=[
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
                    example_chips,
                    prompt_input,
                    ft.Row(
                        controls=[
                            num_hinos_label,
                            num_hinos_slider,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        controls=[generate_button, save_button],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=10,
            ),
            padding=ft.Padding.all(16),
        )

        # Botão voltar usa stack de views
        def _go_back(e):
            if len(page.views) > 1:
                page.views.pop()
                top_view = page.views[-1]
                page.go(top_view.route)
            else:
                page.go("/")

        return ft.View(
            route="/agente",
            appbar=ft.AppBar(
                leading=ft.IconButton(
                    ft.Icons.ARROW_BACK,
                    on_click=_go_back,
                ),
                title=ft.Text(
                    "Agente Organizador de Cultos", weight=ft.FontWeight.BOLD
                ),
                center_title=True,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                actions=[
                    ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.AMBER_300),
                ],
            ),
            controls=[
                ft.Container(
                    content=tab_bar,
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                ),
                prompt_container,
                ft.Divider(height=1),
                ft.Container(
                    content=results_container,
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                ),
            ],
        )
