import asyncio
import json
import flet as ft
from typing import Optional, Dict, List
from src.repositories.hino_repository import HinoRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.services.media_service import MediaService, QUALITY_SD, QUALITY_HD, path_to_file_uri
from src.models.hino import Hino

# Reprodutores de Mídia Globais (flet 0.23+)
try:
    import flet_audio as ftaudio  # type: ignore
    _Audio = ftaudio.Audio
except ImportError:
    try:
        import flet.audio as ftaudio  # type: ignore
        _Audio = ftaudio.Audio
    except ImportError:
        _Audio = getattr(ft, "Audio", None)

try:
    import flet_video as ftvideo  # type: ignore
    _Video = ftvideo.Video
    _VideoMedia = ftvideo.VideoMedia
except ImportError:
    try:
        import flet.video as ftvideo  # type: ignore
        _Video = ftvideo.Video
        _VideoMedia = ftvideo.VideoMedia
    except ImportError:
        _Video = getattr(ft, "Video", None)
        _VideoMedia = getattr(ft, "VideoMedia", None)

try:
    import flet_webview as ftwebview  # type: ignore
    _WebView = getattr(ftwebview, "WebView", None)
except ImportError:
    try:
        import flet.webview as ftwebview  # type: ignore
        _WebView = getattr(ftwebview, "WebView", None)
    except ImportError:
        _WebView = getattr(ft, "WebView", None)

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
    registro no histórico, metadados cruzados, reprodutor interno de áudio real e downloads offline.
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
    ):
        self.hino_id = hino_id
        self.hino_repository = hino_repository
        self.favorito_repository = favorito_repository
        self.historico_repository = historico_repository
        self.media_service = media_service
        self.hino_ids_list = hino_ids_list or []

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
        self.download_icon: Optional[ft.IconButton] = None
        self.is_fav: bool = False
        self.is_downloaded: bool = False
        self.download_status: Dict[str, bool] = {"audio": False, "video_sd": False, "video_hd": False}
        self.relacionados: Dict[str, List[str]] = {"temas": [], "textos_biblicos": []}

        # SnackBar singleton reutilizável (evita acúmulo no overlay)
        self._snackbar: Optional[ft.SnackBar] = None
        
        # Reprodutores nativos
        self.audio_player = None
        self.video_player = None
        self.audio_progress: int = 0
        self.audio_duration: int = 1
        self.is_playing: bool = False
        self.is_dragging_slider: bool = False
        
        self.Audio = _Audio
        self.Video = _Video
        self.VideoMedia = _VideoMedia

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
        
        # Remove reprodutores de áudio antigos do overlay para evitar "Unknown Control" e artefatos
        if self.Audio:
            for ctrl in page.overlay[:]:
                if isinstance(ctrl, self.Audio):
                    try:
                        page.overlay.remove(ctrl)
                    except Exception:
                        pass
        self.audio_player = None

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

        if self.media_service:
            self.is_downloaded = self.media_service.is_downloaded(self.hino_id)
            self.download_status = self.media_service.get_download_status(self.hino_id)

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

        # Botão de Download Offline (abre modal com opções SD/HD/Áudio)
        has_any_download = any(self.download_status.values())
        self.download_icon = ft.IconButton(
            icon=ft.Icons.DOWNLOAD_DONE if has_any_download else ft.Icons.FILE_DOWNLOAD,
            icon_color=ft.Colors.GREEN_400 if has_any_download else None,
            tooltip="Downloads Disponíveis" if has_any_download else "Baixar Mídia (Offline)",
            on_click=lambda e: self._show_download_modal(page, hino),
        )

        # Navegação anterior/próximo
        prev_btn, next_btn = self._build_nav_buttons(page)

        # Botão voltar usa stack de views em vez de hardcoded "/"
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
                                content=ft.Text(
                                    hino.titulo,
                                    size=22,
                                    weight=ft.FontWeight.BOLD,
                                    text_align=ft.TextAlign.CENTER,
                                    color=ft.Colors.BLUE_200,
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
                                ft.IconButton(
                                    ft.Icons.PLAY_CIRCLE_OUTLINE,
                                    tooltip="Reprodutor Interno de Mídia",
                                    on_click=lambda e: self._show_media_modal(page, hino),
                                ),
                                ft.Text("Mídia", size=10, text_align=ft.TextAlign.CENTER),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=0,
                        ),
                        ft.Column(
                            controls=[
                                self.download_icon,
                                ft.Text("Download", size=10, text_align=ft.TextAlign.CENTER),
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

    async def _handle_download_item(
        self, page: ft.Page, hino: Hino, media_type: str, quality: str = QUALITY_SD
    ) -> None:
        """Executa download de áudio ou vídeo com feedback ao usuário."""
        if not self.media_service:
            self._show_snackbar(page, "Serviço de download indisponível.")
            return
        if not hino.link_video:
            self._show_snackbar(page, "Este hino não possui link de mídia cadastrado.")
            return

        label = "Áudio" if media_type == "audio" else f"Vídeo {'HD' if quality == QUALITY_HD else 'SD'}"

        # Verifica se já baixado
        if media_type == "audio" and self.media_service.is_audio_downloaded(self.hino_id):
            self._show_snackbar(page, f"{label} do Hino {hino.numero} já está baixado!")
            return
        if media_type == "video" and self.media_service.is_video_downloaded(self.hino_id, quality):
            self._show_snackbar(page, f"{label} do Hino {hino.numero} já está baixado!")
            return

        self._show_snackbar(page, f"Baixando {label} do Hino {hino.numero}...")

        try:
            if media_type == "audio":
                result = await self.media_service.download_audio(self.hino_id, hino.link_video)
            else:
                result = await self.media_service.download_video(self.hino_id, hino.link_video, quality)

            if result:
                self.download_status = self.media_service.get_download_status(self.hino_id)
                self.is_downloaded = self.download_status.get("audio", False)
                self._update_download_icon_state()
                self._show_snackbar(page, f"{label} do Hino {hino.numero} concluído!")
            else:
                self._show_snackbar(page, f"Falha no download de {label} do Hino {hino.numero}.")
        except Exception:
            self._show_snackbar(page, f"Erro no download de {label} do Hino {hino.numero}.")

    def _update_download_icon_state(self) -> None:
        """Atualiza o ícone de download na BottomAppBar."""
        if self.download_icon:
            has_any = any(self.download_status.values())
            self.download_icon.icon = ft.Icons.DOWNLOAD_DONE if has_any else ft.Icons.FILE_DOWNLOAD
            self.download_icon.icon_color = ft.Colors.GREEN_400 if has_any else None
            self.download_icon.tooltip = "Downloads Disponíveis" if has_any else "Baixar Mídia (Offline)"

    def _show_download_modal(self, page: ft.Page, hino: Hino) -> None:
        """Exibe modal com opções de download: Áudio, Vídeo SD e Vídeo HD."""
        if not self.media_service:
            self._show_snackbar(page, "Serviço de download indisponível.")
            return
        if not hino.link_video:
            self._show_snackbar(page, "Este hino não possui link de mídia cadastrado.")
            return

        status = self.media_service.get_download_status(self.hino_id)

        def _make_download_tile(label, icon, media_type, quality, is_done):
            return ft.ListTile(
                leading=ft.Icon(
                    ft.Icons.CHECK_CIRCLE if is_done else icon,
                    color=ft.Colors.GREEN_400 if is_done else ft.Colors.BLUE_200,
                ),
                title=ft.Text(label),
                subtitle=ft.Text("Baixado ✓" if is_done else "Toque para baixar", size=11),
                on_click=lambda e: page.run_task(
                    self._handle_download_item, page, hino, media_type, quality
                ) if not is_done else None,
            )

        tiles = [
            _make_download_tile(
                "🎵 Áudio (MP3/M4A)", ft.Icons.MUSIC_NOTE, "audio", QUALITY_SD, status["audio"]
            ),
            _make_download_tile(
                "📹 Vídeo SD (480p)", ft.Icons.SD, "video", QUALITY_SD, status["video_sd"]
            ),
            _make_download_tile(
                "🎬 Vídeo HD (720p)", ft.Icons.HD, "video", QUALITY_HD, status["video_hd"]
            ),
        ]

        bs = ft.BottomSheet(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(f"Downloads — Hino {hino.numero}", weight=ft.FontWeight.BOLD, size=18),
                                ft.IconButton(ft.Icons.CLOSE, on_click=lambda ev: page.pop_dialog()),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Divider(),
                        *tiles,
                    ],
                    tight=True,
                    spacing=4,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=ft.Padding.all(16),
            )
        )
        page.show_dialog(bs)

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

    def _get_media_source_info(self, hino: Hino) -> tuple[bool, str, str]:
        """Retorna (is_offline, source_uri, initial_state_text)."""
        if not self.media_service:
            text = "Link disponível" if hino.link_video else "Nenhuma mídia"
            return False, hino.link_video or "", text

        is_offline = self.media_service.is_audio_downloaded(self.hino_id)

        if is_offline:
            # Converte caminho local para URI file:// compatível com Flutter
            source_uri = self.media_service.get_audio_file_uri(self.hino_id) or ""
            text = f"Áudio offline: hino_{hino.numero}"
        elif hino.link_video:
            source_uri = hino.link_video
            text = "Streaming online disponível"
        else:
            source_uri = ""
            text = "Nenhuma mídia"

        return is_offline, source_uri, text

    def _ensure_audio_player(self, page: ft.Page):
        """Instancia o player de áudio nativo sob demanda ao invés de pré-carregar no overlay."""
        if self.audio_player is None and self.Audio:
            try:
                self.audio_player = self.Audio(
                    autoplay=False,
                    on_position_change=self._on_audio_pos,
                    on_duration_change=self._on_audio_dur,
                    on_state_change=self._on_audio_state,
                )
                if self.audio_player not in page.overlay:
                    page.overlay.append(self.audio_player)
                    page.update()
            except Exception:
                self.audio_player = None
        return self.audio_player

    async def _safe_seek(self, position_ms: int) -> None:
        """Realiza busca (seek) de forma segura capturando eventuais erros ou timeouts."""
        if self.audio_player:
            try:
                res = self.audio_player.seek(int(position_ms))
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass

    def _on_audio_pos(self, e):
        try:
            self.audio_progress = int(e.data)
            if hasattr(self, 'slider_progress') and self.slider_progress and not self.is_dragging_slider:
                self.slider_progress.value = self.audio_progress
                self.slider_progress.update()
        except Exception:
            pass

    def _on_audio_dur(self, e):
        try:
            self.audio_duration = int(e.data)
            if hasattr(self, 'slider_progress') and self.slider_progress:
                self.slider_progress.max = self.audio_duration
                self.slider_progress.update()
        except: pass

    def _on_audio_state(self, e):
        if e.data == "playing":
            self.is_playing = True
        else:
            self.is_playing = False

    async def _close_media_modal(self, page: ft.Page) -> None:
        if self.audio_player:
            try:
                res = self.audio_player.pause()
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass
            try:
                if self.audio_player in page.overlay:
                    page.overlay.remove(self.audio_player)
            except Exception:
                pass
            self.audio_player = None
        if self.media_service:
            self.media_service.stop_audio()
        page.pop_dialog()

    async def _handle_toggle_play_native(
        self,
        page: ft.Page,
        hino: Hino,
        is_offline: bool,
        local_path: str,
        play_btn: ft.IconButton,
        play_state_text: ft.Text,
    ) -> None:
        player = self._ensure_audio_player(page)
        if not player:
            play_state_text.value = "Player nativo indisponível. Use o reprodutor do sistema."
            page.update()
            return

        if self.is_playing:
            try:
                res = player.pause()
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass
            play_btn.icon = ft.Icons.PLAY_ARROW
            play_btn.icon_color = None
            play_state_text.value = "Áudio pausado"
            page.update()
            return

        play_btn.icon = ft.Icons.PAUSE
        play_btn.icon_color = ft.Colors.AMBER_400
        play_state_text.value = "Carregando áudio..."
        page.update()

        try:
            if is_offline and local_path:
                player.src = local_path
            else:
                stream_url = None
                if self.media_service and hino.link_video:
                    stream_url = await self.media_service.get_stream_url(hino.link_video, is_video=False)
                if not stream_url:
                    play_state_text.value = "Falha ao obter streaming. Tente baixar o áudio."
                    play_btn.icon = ft.Icons.PLAY_ARROW
                    page.update()
                    return
                player.src = stream_url

            player.update()
            res = player.play()
            if asyncio.iscoroutine(res):
                await res
            play_state_text.value = "Reproduzindo áudio..."
        except Exception:
            play_state_text.value = "Erro ao reproduzir. Tente baixar o áudio."
            play_btn.icon = ft.Icons.PLAY_ARROW
        page.update()

    async def _handle_stop_play_native(self, page: ft.Page, play_btn: ft.IconButton, play_state_text: ft.Text):
        if self.audio_player:
            try:
                await self.audio_player.pause()
                await self._safe_seek(0)
            except Exception:
                pass
        play_btn.icon = ft.Icons.PLAY_ARROW
        play_btn.icon_color = None
        play_state_text.value = "Áudio parado"
        page.update()

    async def _handle_show_video_online(self, page: ft.Page, hino: Hino):
        """Reproduz vídeo online via YouTube Embed em WebView ou UrlLauncher."""
        page.pop_dialog()

        if not self.media_service:
            self._show_snackbar(page, "Serviço de mídia indisponível.")
            return

        embed_url = self.media_service.get_embed_url(hino.link_video)
        if not embed_url:
            self._show_snackbar(page, "Link de vídeo inválido ou não suportado.")
            return

        if _WebView is not None:
            try:
                webview = _WebView(
                    url=embed_url,
                    expand=True,
                    javascript_enabled=True,
                )
                video_view = ft.View(
                    route=f"/hino/{hino.id}/video",
                    appbar=ft.AppBar(
                        leading=ft.IconButton(
                            ft.Icons.ARROW_BACK,
                            on_click=lambda e: page.run_task(self._close_video_view, page)
                        ),
                        title=ft.Text(f"Vídeo: {hino.titulo}"),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    ),
                    bgcolor=ft.Colors.BLACK,
                    controls=[
                        ft.Container(
                            content=webview,
                            expand=True,
                            alignment=ft.Alignment.CENTER,
                            bgcolor=ft.Colors.BLACK,
                        )
                    ]
                )
                page.views.append(video_view)
                page.update()
                return
            except Exception:
                pass

        # Fallback gracioso se WebView não for suportado/disponível
        self._show_snackbar(page, "Abrindo vídeo no navegador...")
        await ft.UrlLauncher().launch_url(embed_url)

    async def _handle_show_video_offline(self, page: ft.Page, hino: Hino, quality: str):
        """Reproduz vídeo offline local via flet_video com URI file://."""
        page.pop_dialog()

        video_cls = self.Video
        video_media_cls = self.VideoMedia

        if not video_cls or not video_media_cls:
            self._show_snackbar(page, "O plugin 'flet-video' não está instalado.")
            return

        if not self.media_service:
            self._show_snackbar(page, "Serviço de mídia indisponível.")
            return

        video_uri = self.media_service.get_video_file_uri(self.hino_id, quality)
        if not video_uri:
            self._show_snackbar(page, f"Vídeo {'HD' if quality == QUALITY_HD else 'SD'} não encontrado. Baixe primeiro.")
            return

        self.video_player = video_cls(
            expand=True,
            playlist=[video_media_cls(video_uri)],
            autoplay=True,
        )

        video_view = ft.View(
            route=f"/hino/{hino.id}/video",
            appbar=ft.AppBar(
                leading=ft.IconButton(
                    ft.Icons.ARROW_BACK,
                    on_click=lambda e: page.run_task(self._close_video_view, page)
                ),
                title=ft.Text(f"Vídeo: {hino.titulo}"),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            ),
            bgcolor=ft.Colors.BLACK,
            controls=[
                ft.Container(
                    content=self.video_player,
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=ft.Colors.BLACK,
                )
            ]
        )
        page.views.append(video_view)
        page.update()

    async def _close_video_view(self, page: ft.Page):
        if hasattr(self, 'video_player') and self.video_player:
            try:
                res = self.video_player.pause()
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass
        if len(page.views) > 1:
            page.views.pop()
        page.update()

    def _build_media_status_row(self, is_offline: bool) -> ft.Column:
        """Constrói indicadores de status de mídia disponível."""
        status_items = []

        # Status principal
        icon = ft.Icons.CHECK_CIRCLE if is_offline else ft.Icons.CLOUD_OUTLINED
        color = ft.Colors.GREEN_400 if is_offline else ft.Colors.BLUE_200
        text = "Áudio Offline Disponível" if is_offline else "Modo Online"
        status_items.append(
            ft.Row(
                controls=[
                    ft.Icon(icon, color=color, size=18),
                    ft.Text(text, weight=ft.FontWeight.BOLD, size=13),
                ],
                spacing=6,
            )
        )

        # Chips de vídeo offline disponível
        if self.media_service:
            video_chips = []
            if self.download_status.get("video_sd"):
                video_chips.append(
                    ft.Chip(
                        label=ft.Text("Vídeo SD", size=10),
                        leading=ft.Icon(ft.Icons.SD, size=14, color=ft.Colors.GREEN_400),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    )
                )
            if self.download_status.get("video_hd"):
                video_chips.append(
                    ft.Chip(
                        label=ft.Text("Vídeo HD", size=10),
                        leading=ft.Icon(ft.Icons.HD, size=14, color=ft.Colors.GREEN_400),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    )
                )
            if video_chips:
                status_items.append(
                    ft.Row(controls=video_chips, spacing=6, wrap=True, run_spacing=4)
                )

        return ft.Column(controls=status_items, spacing=4, tight=True)

    def _show_media_modal(self, page: ft.Page, hino: Hino) -> None:
        """Exibe o modal do Reprodutor Interno com reprodução nativa Flet e Seek bar."""
        is_offline, source_file, state_text = self._get_media_source_info(hino)

        play_state_text = ft.Text(
            state_text,
            size=12,
            italic=True,
            color=ft.Colors.GREY_300,
            text_align=ft.TextAlign.CENTER,
        )

        def _on_slider_change(e):
            self.is_dragging_slider = True

        def _on_slider_change_end(e):
            self.is_dragging_slider = False
            if self.audio_player:
                page.run_task(self._safe_seek, int(e.control.value))

        self.slider_progress = ft.Slider(
            min=0,
            max=self.audio_duration or 1,
            value=self.audio_progress or 0,
            on_change=_on_slider_change,
            on_change_end=_on_slider_change_end,
            expand=True,
            active_color=ft.Colors.GREEN_400,
        )

        play_btn = ft.IconButton(
            ft.Icons.PAUSE if self.is_playing else ft.Icons.PLAY_ARROW,
            icon_color=ft.Colors.AMBER_400 if self.is_playing else None,
            icon_size=32,
            tooltip="Tocar/Pausar Áudio",
            on_click=lambda e: page.run_task(
                self._handle_toggle_play_native, page, hino, is_offline, source_file, play_btn, play_state_text
            ),
        )

        stop_btn = ft.IconButton(
            ft.Icons.STOP,
            icon_size=28,
            tooltip="Parar Áudio",
            on_click=lambda e: page.run_task(self._handle_stop_play_native, page, play_btn, play_state_text),
        )

        media_controls: list[ft.Control] = [
            ft.Row(
                controls=[
                    ft.Text("Reprodutor Interno do Hino", weight=ft.FontWeight.BOLD, size=18),
                    ft.IconButton(ft.Icons.CLOSE, on_click=lambda ev: page.run_task(self._close_media_modal, page)),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Divider(),
            self._build_media_status_row(is_offline),
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(f"Hino {hino.numero} - {hino.titulo}", weight=ft.FontWeight.BOLD, size=15, text_align=ft.TextAlign.CENTER),
                        play_state_text,
                        ft.Row([self.slider_progress], alignment=ft.MainAxisAlignment.CENTER),
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

        # Botões de vídeo
        video_buttons: list[ft.Control] = []

        if hino.link_video:
            link_video = hino.link_video
            # Vídeo Online (YouTube Embed)
            video_buttons.append(
                ft.Button(
                    "Assistir Online (YouTube)",
                    icon=ft.Icons.PLAY_CIRCLE_FILL,
                    on_click=lambda e: page.run_task(self._handle_show_video_online, page, hino),
                )
            )

        # Vídeo Offline SD
        if self.download_status.get("video_sd"):
            video_buttons.append(
                ft.OutlinedButton(
                    "Vídeo SD (Offline)",
                    icon=ft.Icons.SD,
                    on_click=lambda e: page.run_task(
                        self._handle_show_video_offline, page, hino, QUALITY_SD
                    ),
                )
            )

        # Vídeo Offline HD
        if self.download_status.get("video_hd"):
            video_buttons.append(
                ft.OutlinedButton(
                    "Vídeo HD (Offline)",
                    icon=ft.Icons.HD,
                    on_click=lambda e: page.run_task(
                        self._handle_show_video_offline, page, hino, QUALITY_HD
                    ),
                )
            )

        if hino.link_video:
            video_buttons.append(
                ft.OutlinedButton(
                    "Abrir Mídia Externa",
                    icon=ft.Icons.OPEN_IN_NEW,
                    on_click=lambda e: page.run_task(lambda: ft.UrlLauncher().launch_url(link_video)),
                )
            )

        if video_buttons:
            media_controls.append(
                ft.Row(
                    controls=video_buttons,
                    alignment=ft.MainAxisAlignment.CENTER,
                    wrap=True,
                    spacing=10,
                    run_spacing=10,
                )
            )

        bs = ft.BottomSheet(
            content=ft.Container(
                content=ft.Column(
                    controls=media_controls,
                    tight=True,
                    spacing=12,
                    scroll=ft.ScrollMode.AUTO,
                ),
                padding=ft.Padding.all(20),
            )
        )
        page.show_dialog(bs)

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

        metadata = [
            ("Autor da Letra:", hino.autor_letra),
            ("Autor da Música:", hino.autor_musica),
            ("Texto Base Bíblico:", hino.texto_base),
        ]

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

        # Textos Bíblicos como chips clicáveis
        textos_biblicos = self.relacionados.get("textos_biblicos", [])
        if textos_biblicos:
            texto_chips: list[ft.Control] = [
                ft.Chip(
                    label=ft.Text(tb, size=11),
                    leading=ft.Icon(ft.Icons.MENU_BOOK_OUTLINED, size=15, color=ft.Colors.GREEN_400),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    on_click=lambda e, ref=tb: asyncio.create_task(_navigate_search(ref)),
                )
                for tb in textos_biblicos
            ]
            info_items.append(
                ft.Column(
                    controls=[
                        ft.Text("Textos Bíblicos:", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.GREEN_200),
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
