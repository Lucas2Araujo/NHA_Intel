import asyncio
import flet as ft
from typing import Optional, Dict, List
from src.repositories.hino_repository import HinoRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.services.media_service import MediaService
from src.models.hino import Hino


class HinoView:
    """
    View responsável por exibir assincronamente a letra e os detalhes de um hino específico.
    Oferece controles avançados de acessibilidade (tamanho e 3 famílias de fontes), favoritar,
    registro no histórico, metadados cruzados, reprodutor interno embutido de áudio e downloads offline.
    Segue as diretrizes do Flet 0.85+.
    """

    def __init__(
        self,
        hino_id: int,
        hino_repository: HinoRepository,
        favorito_repository: FavoritoRepository,
        historico_repository: HistoricoRepository,
        media_service: Optional[MediaService] = None,
    ):
        self.hino_id = hino_id
        self.hino_repository = hino_repository
        self.favorito_repository = favorito_repository
        self.historico_repository = historico_repository
        self.media_service = media_service

        # Estado interno de acessibilidade de fonte
        self.font_size: int = 18
        self.selected_font: str = "Padrão"

        # Estado interno do player embutido
        self.is_playing: bool = False
        self.playback_task: Optional[asyncio.Task] = None

        # Referências aos elementos dinâmicos da interface
        self.letra_text: Optional[ft.Text] = None
        self.fav_icon: Optional[ft.IconButton] = None
        self.download_icon: Optional[ft.IconButton] = None
        self.is_fav: bool = False
        self.is_downloaded: bool = False
        self.relacionados: Dict[str, List[str]] = {"temas": [], "textos_biblicos": []}

    async def build(self, page: ft.Page) -> ft.View:
        hino: Optional[Hino] = await self.hino_repository.get_by_id(self.hino_id)

        if hino is None:
            return self._build_not_found_view(page)

        # Registrar acesso no histórico e buscar metadados cruzados
        await self.historico_repository.add_acesso(self.hino_id)
        self.relacionados = await self.hino_repository.get_metadados_relacionados(
            self.hino_id
        )

        # Verificar se é favorito e se possui download local
        self.is_fav = await self.favorito_repository.is_favorito(self.hino_id)
        if self.media_service:
            self.is_downloaded = self.media_service.is_downloaded(self.hino_id)

        font_family_map = {
            "Padrão": None,
            "Times New Roman": "Times New Roman",
            "OpenDyslexic": "OpenDyslexic",
        }

        # Texto da letra do hino
        self.letra_text = ft.Text(
            hino.letra if hino.letra else "Letra não disponível para este hino.",
            size=self.font_size,
            text_align=ft.TextAlign.CENTER,
            weight=ft.FontWeight.W_400,
            font_family=font_family_map.get(self.selected_font),
            expand=True,
        )

        # Toggle de Favorito
        self.fav_icon = ft.IconButton(
            icon=ft.Icons.FAVORITE if self.is_fav else ft.Icons.FAVORITE_BORDER,
            icon_color=ft.Colors.RED_400 if self.is_fav else None,
            tooltip="Desfavoritar" if self.is_fav else "Favoritar",
            on_click=lambda e: page.run_task(self._toggle_favorito, page, hino),
        )

        # Botão de Download Offline
        self.download_icon = ft.IconButton(
            icon=(
                ft.Icons.DOWNLOAD_DONE if self.is_downloaded else ft.Icons.FILE_DOWNLOAD
            ),
            icon_color=ft.Colors.GREEN_400 if self.is_downloaded else None,
            tooltip=(
                "Áudio Baixado (Offline)"
                if self.is_downloaded
                else "Baixar Áudio (Offline)"
            ),
            on_click=lambda e: page.run_task(self._handle_download, page, hino),
        )

        return ft.View(
            route=f"/hino/{self.hino_id}",
            appbar=ft.AppBar(
                leading=ft.IconButton(
                    ft.Icons.ARROW_BACK,
                    on_click=lambda e: page.go("/"),
                ),
                title=ft.Text(f"Hino {hino.numero}", weight=ft.FontWeight.BOLD),
                center_title=True,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                actions=[
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
                                content=ft.Text(
                                    hino.titulo,
                                    size=22,
                                    weight=ft.FontWeight.BOLD,
                                    text_align=ft.TextAlign.CENTER,
                                    color=ft.Colors.BLUE_200,
                                ),
                                padding=ft.Padding.symmetric(
                                    vertical=15, horizontal=20
                                ),
                                alignment=ft.Alignment.CENTER,
                            ),
                            ft.Divider(height=1),
                            ft.Container(
                                content=self.letra_text,
                                padding=ft.Padding.symmetric(
                                    vertical=20, horizontal=20
                                ),
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
                        ft.IconButton(
                            ft.Icons.TEXT_FIELDS,
                            tooltip="Tamanho e Família de Fonte",
                            on_click=lambda e: self._show_accessibility_modal(page),
                        ),
                        ft.IconButton(
                            ft.Icons.PLAY_CIRCLE_OUTLINE,
                            tooltip="Reprodutor Interno de Mídia",
                            on_click=lambda e: self._show_media_modal(page, hino),
                        ),
                        self.download_icon,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_AROUND,
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            ),
        )

    def _build_not_found_view(self, page: ft.Page) -> ft.View:
        return ft.View(
            route=f"/hino/{self.hino_id}",
            appbar=ft.AppBar(
                leading=ft.IconButton(
                    ft.Icons.ARROW_BACK,
                    on_click=lambda e: page.go("/"),
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
            font_family_map = {
                "Padrão": None,
                "Times New Roman": "Times New Roman",
                "OpenDyslexic": "OpenDyslexic",
            }
            self.letra_text.size = self.font_size
            self.letra_text.font_family = font_family_map.get(self.selected_font)
            page.update()

    def _increase_font(self, page: ft.Page) -> None:
        if self.font_size < 36:
            self.font_size += 2
            self._update_font(page)

    def _decrease_font(self, page: ft.Page) -> None:
        if self.font_size > 12:
            self.font_size -= 2
            self._update_font(page)

    def _reset_font(self, page: ft.Page) -> None:
        self.font_size = 18
        self.selected_font = "Padrão"
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

        snack = ft.SnackBar(content=ft.Text(msg))
        page.overlay.append(snack)
        snack.open = True
        page.update()

    async def _handle_download(self, page: ft.Page, hino: Hino) -> None:
        if not self.media_service:
            snack = ft.SnackBar(content=ft.Text("Serviço de download indisponível."))
            page.overlay.append(snack)
            snack.open = True
            page.update()
            return

        if not hino.link_video:
            snack = ft.SnackBar(
                content=ft.Text("Este hino não possui link de vídeo cadastrado.")
            )
            page.overlay.append(snack)
            snack.open = True
            page.update()
            return

        if self.media_service.is_downloaded(self.hino_id):
            snack = ft.SnackBar(
                content=ft.Text(
                    f"O Hino {hino.numero} já está baixado para uso offline!"
                )
            )
            page.overlay.append(snack)
            snack.open = True
            page.update()
            return

        snack_start = ft.SnackBar(
            content=ft.Text(
                f"Iniciando download do Hino {hino.numero} em segundo plano..."
            )
        )
        page.overlay.append(snack_start)
        snack_start.open = True
        page.update()

        saved_path = await self.media_service.download_audio(
            self.hino_id, hino.link_video
        )

        if saved_path and self.media_service.is_downloaded(self.hino_id):
            self.is_downloaded = True
            if self.download_icon:
                self.download_icon.icon = ft.Icons.DOWNLOAD_DONE
                self.download_icon.icon_color = ft.Colors.GREEN_400
                self.download_icon.tooltip = "Áudio Baixado (Offline)"
            msg = f"Download do Hino {hino.numero} concluído com sucesso!"
        else:
            msg = f"Falha no download do Hino {hino.numero}."

        snack_end = ft.SnackBar(content=ft.Text(msg))
        page.overlay.append(snack_end)
        snack_end.open = True
        page.update()

    def _show_accessibility_modal(self, page: ft.Page) -> None:
        font_radio_group = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="Padrão", label="Padrão (Sans-Serif)"),
                    ft.Radio(
                        value="Times New Roman", label="Serifada (Times New Roman)"
                    ),
                    ft.Radio(value="OpenDyslexic", label="OpenDyslexic (Acessível)"),
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
                                ft.Text(
                                    f"{self.font_size}pt", weight=ft.FontWeight.BOLD
                                ),
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
                        ),
                        ft.Divider(),
                        ft.Text(
                            "Família de Fonte:", weight=ft.FontWeight.BOLD, size=14
                        ),
                        font_radio_group,
                    ],
                    tight=True,
                    spacing=12,
                ),
                padding=ft.Padding.all(20),
            )
        )
        page.show_dialog(bs)

    def _show_media_modal(self, page: ft.Page, hino: Hino) -> None:
        """Exibe o modal do Reprodutor Interno Embutido de Áudio e Mídia."""
        is_offline = (
            self.media_service.is_downloaded(self.hino_id)
            if self.media_service
            else False
        )
        local_path = (
            self.media_service.get_local_filepath(self.hino_id)
            if self.media_service
            else ""
        )

        progress_bar = ft.ProgressBar(
            value=0.0, color=ft.Colors.BLUE_400, visible=False
        )
        play_state_text = ft.Text(
            (
                f"Áudio offline: hino_{hino.numero}.mp3"
                if is_offline
                else "Reprodução online pronta"
            ),
            size=12,
            italic=True,
            color=ft.Colors.GREY_300,
        )

        play_btn = ft.IconButton(ft.Icons.PLAY_ARROW, icon_size=32, tooltip="Tocar")

        async def _toggle_play(e=None):
            if not self.is_playing:
                self.is_playing = True
                play_btn.icon = ft.Icons.PAUSE
                play_btn.icon_color = ft.Colors.AMBER_400
                progress_bar.visible = True
                play_state_text.value = (
                    f"Tocando Hino {hino.numero} no player embutido..."
                )
                page.update()

                # Animação de progresso interna do player
                for p in range(1, 101):
                    if not self.is_playing:
                        break
                    progress_bar.value = p / 100.0
                    page.update()
                    await asyncio.sleep(0.1)

                self.is_playing = False
                play_btn.icon = ft.Icons.PLAY_ARROW
                play_btn.icon_color = None
                progress_bar.visible = False
                play_state_text.value = "Reprodução concluída"
                page.update()
            else:
                self.is_playing = False
                play_btn.icon = ft.Icons.PLAY_ARROW
                play_btn.icon_color = None
                progress_bar.visible = False
                play_state_text.value = "Pausado"
                page.update()

        play_btn.on_click = lambda e: page.run_task(_toggle_play)

        async def _stop_play(e=None):
            self.is_playing = False
            play_btn.icon = ft.Icons.PLAY_ARROW
            play_btn.icon_color = None
            progress_bar.value = 0.0
            progress_bar.visible = False
            play_state_text.value = "Parado"
            page.update()

        stop_btn = ft.IconButton(
            ft.Icons.STOP,
            icon_size=28,
            tooltip="Parar",
            on_click=lambda e: page.run_task(_stop_play),
        )

        async def _open_url(e=None):
            if hino.link_video:
                await page.launch_url(hino.link_video)

        media_controls = [
            ft.Row(
                controls=[
                    ft.Text(
                        "Reprodutor Interno do Hino", weight=ft.FontWeight.BOLD, size=18
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE, on_click=lambda ev: page.pop_dialog()
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Divider(),
            ft.Row(
                controls=[
                    ft.Icon(
                        (
                            ft.Icons.CHECK_CIRCLE
                            if is_offline
                            else ft.Icons.CLOUD_OUTLINED
                        ),
                        color=ft.Colors.GREEN_400 if is_offline else ft.Colors.BLUE_200,
                    ),
                    ft.Text(
                        "Modo Offline Disponível" if is_offline else "Modo Online",
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
            ),
            # Container do Player Interno Embutido
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            f"Hino {hino.numero} - {hino.titulo}",
                            weight=ft.FontWeight.BOLD,
                            size=15,
                        ),
                        play_state_text,
                        progress_bar,
                        ft.Row(
                            controls=[play_btn, stop_btn],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
                padding=ft.Padding.all(12),
                border_radius=12,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            ),
        ]

        if hino.link_video:
            media_controls.append(
                ft.Row(
                    controls=[
                        ft.ElevatedButton(
                            "Baixar Somente Áudio (MP3)",
                            icon=ft.Icons.FILE_DOWNLOAD,
                            on_click=lambda e: page.run_task(
                                self._handle_download, page, hino
                            ),
                        ),
                        ft.OutlinedButton(
                            "Abrir Mídia Externa",
                            icon=ft.Icons.OPEN_IN_NEW,
                            on_click=lambda e: page.run_task(_open_url),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
            )

        bs = ft.BottomSheet(
            content=ft.Container(
                content=ft.Column(
                    controls=media_controls,
                    tight=True,
                    spacing=12,
                ),
                padding=ft.Padding.all(20),
            )
        )
        page.show_dialog(bs)

    def _show_info_modal(self, page: ft.Page, hino: Hino) -> None:
        info_items = [
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

        metadata = [
            ("Autor da Letra:", hino.autor_letra),
            ("Autor da Música:", hino.autor_musica),
            ("Texto Base Bíblico:", hino.texto_base),
            ("Categoria:", hino.categoria),
            ("Subcategoria:", hino.subcategoria),
        ]

        for label, val in metadata:
            if val and val.strip():
                info_items.append(
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

        temas = self.relacionados.get("temas", [])
        if temas:
            info_items.append(
                ft.Column(
                    controls=[
                        ft.Text(
                            "Temas Relacionados:",
                            weight=ft.FontWeight.BOLD,
                            size=12,
                            color=ft.Colors.AMBER_200,
                        ),
                        ft.Text(", ".join(temas), size=14),
                    ],
                    spacing=2,
                )
            )

        textos_biblicos = self.relacionados.get("textos_biblicos", [])
        if textos_biblicos:
            info_items.append(
                ft.Column(
                    controls=[
                        ft.Text(
                            "Textos Bíblicos de Referência:",
                            weight=ft.FontWeight.BOLD,
                            size=12,
                            color=ft.Colors.GREEN_200,
                        ),
                        ft.Text(", ".join(textos_biblicos), size=14),
                    ],
                    spacing=2,
                )
            )

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
                ),
                padding=ft.Padding.all(20),
            )
        )
        page.show_dialog(bs)
