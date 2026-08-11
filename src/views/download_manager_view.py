import asyncio
import flet as ft
from typing import Optional, List, Dict, Any
from src.repositories.hino_repository import HinoRepository
from src.services.media_service import MediaService, QUALITY_SD, QUALITY_HD


class DownloadManagerView:
    """
    View do Gerenciador de Downloads em Lote.
    Permite baixar toda a biblioteca de 601 hinos em Áudio, Vídeo SD ou Vídeo HD.
    Exibe progresso em tempo real, estatísticas de armazenamento e suporte a cancelamento.
    """

    def __init__(
        self,
        hino_repository: HinoRepository,
        media_service: MediaService,
    ):
        self.hino_repository = hino_repository
        self.media_service = media_service
        self._cancel_event: Optional[asyncio.Event] = None
        self._is_downloading: bool = False

    def build(self, page: ft.Page) -> ft.View:
        """Constrói a view do gerenciador de downloads em lote."""

        # ── Elementos de UI ──────────────────────────────────────────
        self.progress_bar = ft.ProgressBar(value=0, width=400, color=ft.Colors.GREEN_400)
        self.progress_text = ft.Text("Pronto para baixar", size=14)
        self.counter_text = ft.Text("0 / 0", size=18, weight=ft.FontWeight.BOLD)
        self.current_hino_text = ft.Text("", size=12, italic=True, color=ft.Colors.GREY_300)
        self.storage_text = ft.Text("", size=12, color=ft.Colors.GREY_400)
        self.result_text = ft.Text("", size=12, visible=False)

        # Botão de cancelar
        self.cancel_btn = ft.OutlinedButton(
            "Cancelar",
            icon=ft.Icons.CANCEL,
            visible=False,
            on_click=lambda e: self._cancel_download(),
        )

        # Atualiza informações de armazenamento
        self._refresh_storage_info()

        # ── Cartões de Download ──────────────────────────────────────

        audio_card = self._build_download_card(
            page,
            title="🎵 Áudios (MP3/M4A)",
            subtitle="Baixar todos os áudios de 601 hinos",
            icon=ft.Icons.MUSIC_NOTE,
            color=ft.Colors.BLUE_400,
            media_type="audio",
            quality=QUALITY_SD,
        )

        video_sd_card = self._build_download_card(
            page,
            title="📹 Vídeos SD (480p)",
            subtitle="Baixar todos os vídeos em qualidade padrão",
            icon=ft.Icons.SD,
            color=ft.Colors.AMBER_400,
            media_type="video",
            quality=QUALITY_SD,
        )

        video_hd_card = self._build_download_card(
            page,
            title="🎬 Vídeos HD (720p)",
            subtitle="Baixar todos os vídeos na melhor qualidade",
            icon=ft.Icons.HD,
            color=ft.Colors.GREEN_400,
            media_type="video",
            quality=QUALITY_HD,
        )

        # ── Painel de Progresso ──────────────────────────────────────

        progress_panel = ft.Container(
            content=ft.Column(
                controls=[
                    self.counter_text,
                    self.progress_bar,
                    self.progress_text,
                    self.current_hino_text,
                    self.cancel_btn,
                    self.result_text,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            padding=ft.Padding.all(16),
            border_radius=12,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            visible=True,
        )

        # ── Botão de Limpeza ─────────────────────────────────────────

        clear_section = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Gerenciamento de Armazenamento", weight=ft.FontWeight.BOLD, size=14),
                    self.storage_text,
                    ft.Row(
                        controls=[
                            ft.OutlinedButton(
                                "Limpar Áudios",
                                icon=ft.Icons.DELETE_OUTLINE,
                                on_click=lambda e: self._clear_downloads(page, "audio"),
                            ),
                            ft.OutlinedButton(
                                "Limpar Vídeos SD",
                                icon=ft.Icons.DELETE_OUTLINE,
                                on_click=lambda e: self._clear_downloads(page, "video_sd"),
                            ),
                            ft.OutlinedButton(
                                "Limpar Vídeos HD",
                                icon=ft.Icons.DELETE_OUTLINE,
                                on_click=lambda e: self._clear_downloads(page, "video_hd"),
                            ),
                        ],
                        wrap=True,
                        spacing=8,
                        run_spacing=8,
                    ),
                ],
                spacing=8,
            ),
            padding=ft.Padding.all(16),
            border_radius=12,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        )

        # ── View Principal ───────────────────────────────────────────

        async def _go_back(e):
            if len(page.views) > 1:
                page.views.pop()
                top_view = page.views[-1]
                await page.push_route(top_view.route)
            else:
                await page.push_route("/")

        return ft.View(
            route="/downloads",
            appbar=ft.AppBar(
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=_go_back),
                title=ft.Text("Gerenciador de Downloads", weight=ft.FontWeight.BOLD),
                center_title=True,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            ),
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=[
                            progress_panel,
                            ft.Divider(height=1),
                            audio_card,
                            video_sd_card,
                            video_hd_card,
                            ft.Divider(height=1),
                            clear_section,
                        ],
                        spacing=12,
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                    expand=True,
                ),
            ],
        )

    def _build_download_card(
        self,
        page: ft.Page,
        title: str,
        subtitle: str,
        icon: str,
        color: str,
        media_type: str,
        quality: str,
    ) -> ft.Container:
        """Constrói um card de download em lote."""
        return ft.Container(
            content=ft.ListTile(
                leading=ft.Icon(icon, color=color, size=32),
                title=ft.Text(title, weight=ft.FontWeight.BOLD),
                subtitle=ft.Text(subtitle, size=12),
                trailing=ft.IconButton(
                    ft.Icons.DOWNLOAD,
                    icon_color=color,
                    tooltip=f"Iniciar download: {title}",
                    on_click=lambda e: page.run_task(
                        self._start_batch_download, page, media_type, quality, title
                    ),
                ),
            ),
            border_radius=12,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        )

    def _refresh_storage_info(self) -> None:
        """Atualiza texto de uso de armazenamento."""
        usage = self.media_service.get_storage_usage()
        total_mb = sum(usage.values()) / (1024 * 1024)
        audio_mb = usage["audio"] / (1024 * 1024)
        video_sd_mb = usage["video_sd"] / (1024 * 1024)
        video_hd_mb = usage["video_hd"] / (1024 * 1024)
        self.storage_text.value = (
            f"Áudios: {audio_mb:.1f} MB  •  "
            f"Vídeos SD: {video_sd_mb:.1f} MB  •  "
            f"Vídeos HD: {video_hd_mb:.1f} MB  •  "
            f"Total: {total_mb:.1f} MB"
        )

    def _cancel_download(self) -> None:
        """Cancela o download em lote em andamento."""
        if self._cancel_event:
            self._cancel_event.set()

    def _clear_downloads(self, page: ft.Page, media_type: str) -> None:
        """Remove downloads de uma categoria."""
        count = self.media_service.clear_downloads(media_type)
        self._refresh_storage_info()
        self.storage_text.update()
        label = {"audio": "Áudios", "video_sd": "Vídeos SD", "video_hd": "Vídeos HD"}.get(
            media_type, media_type
        )
        # Mostra feedback via snackbar simples
        snackbar = ft.SnackBar(content=ft.Text(f"{count} arquivo(s) de {label} removidos."))
        page.overlay.append(snackbar)
        snackbar.open = True
        page.update()

    async def _start_batch_download(
        self, page: ft.Page, media_type: str, quality: str, label: str
    ) -> None:
        """Inicia o download em lote de todos os hinos."""
        if self._is_downloading:
            snackbar = ft.SnackBar(
                content=ft.Text("Já existe um download em andamento. Aguarde ou cancele.")
            )
            page.overlay.append(snackbar)
            snackbar.open = True
            page.update()
            return

        self._is_downloading = True
        self._cancel_event = asyncio.Event()

        # Carrega lista completa de hinos
        all_hinos = await self.hino_repository.get_all()
        hino_list: List[Dict[str, Any]] = [
            {"id": h.id, "link_video": h.link_video, "titulo": h.titulo}
            for h in all_hinos
            if h.id is not None
        ]
        total = len(hino_list)

        # Configura UI de progresso
        self.progress_bar.value = 0
        self.counter_text.value = f"0 / {total}"
        self.progress_text.value = f"Baixando {label}..."
        self.current_hino_text.value = "Preparando..."
        self.cancel_btn.visible = True
        self.result_text.visible = False
        page.update()

        def _progress_callback(done: int, total_count: int, current_title: Optional[str]):
            """Callback chamado pelo MediaService a cada item processado."""
            self.progress_bar.value = done / total_count if total_count > 0 else 0
            self.counter_text.value = f"{done} / {total_count}"
            self.current_hino_text.value = f"Processando: {current_title or '...'}"
            try:
                self.progress_bar.update()
                self.counter_text.update()
                self.current_hino_text.update()
            except Exception:
                pass

        # Executa download em lote
        result = await self.media_service.download_library_batch(
            hino_list=hino_list,
            media_type=media_type,
            quality=quality,
            progress_callback=_progress_callback,
            cancel_event=self._cancel_event,
        )

        # Exibe resultado
        self._is_downloading = False
        self.cancel_btn.visible = False

        if result.get("cancelled"):
            self.progress_text.value = "Download cancelado pelo usuário."
            self.result_text.value = (
                f"✅ {result['completed']} concluídos  •  "
                f"⏭️ {result['skipped']} pulados  •  "
                f"❌ {result['failed']} falhados"
            )
        else:
            self.progress_bar.value = 1.0
            self.progress_text.value = f"Download de {label} concluído!"
            self.result_text.value = (
                f"✅ {result['completed']} baixados  •  "
                f"⏭️ {result['skipped']} já existiam  •  "
                f"❌ {result['failed']} falhados"
            )

        self.result_text.visible = True
        self.current_hino_text.value = ""
        self._refresh_storage_info()
        page.update()
