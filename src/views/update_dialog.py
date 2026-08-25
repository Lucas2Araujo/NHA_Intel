"""
Diálogo de Atualização Automática para Flet.
Exibe informações da nova versão, notas da release, barra de progresso em tempo real
e executa o disparo da instalação do pacote .apk.
"""

import os
import asyncio
import flet as ft
from typing import Dict, Any, Optional
from src.services.updater_service import UpdaterService


async def trigger_apk_installation(page: ft.Page, apk_path: str, fallback_url: Optional[str] = None):
    """
    Dispara a instalação do arquivo .apk no Android / Desktop.
    Utiliza page.launch_url para acionar a Intent nativa do PackageInstaller no Android.
    """
    launched = False
    
    # 1. Tenta disparar o instalador via URI local
    if apk_path and os.path.exists(apk_path):
        local_uri = f"file://{os.path.abspath(apk_path)}"
        try:
            if hasattr(ft, "UrlLauncher"):
                await ft.UrlLauncher().launch_url(local_uri)
                launched = True
            elif hasattr(page, "launch_url"):
                await page.launch_url(local_uri)
                launched = True
        except Exception:
            launched = False

    # 2. Fallback: se não conseguiu abrir via file:// ou se não existe, abre URL web/direta
    if not launched and fallback_url:
        try:
            if hasattr(ft, "UrlLauncher"):
                await ft.UrlLauncher().launch_url(fallback_url)
            elif hasattr(page, "launch_url"):
                await page.launch_url(fallback_url)
        except Exception:
            pass


class UpdateDialog:
    """Controlador do diálogo modal de atualização do aplicativo."""

    def __init__(
        self,
        page: ft.Page,
        update_info: Dict[str, Any],
        updater_service: UpdaterService,
        on_dismiss: Optional[Any] = None,
    ):
        self.page = page
        self.update_info = update_info
        self.updater_service = updater_service
        self.on_dismiss = on_dismiss

        self.latest_version: str = update_info.get("latest_version", "Nova Versão")
        self.current_version: str = update_info.get("current_version", "")
        self.release_notes: str = update_info.get("release_notes", "").strip()
        self.download_url: Optional[str] = update_info.get("download_url") or update_info.get("html_url")

        self.download_task: Optional[asyncio.Task] = None
        self._dialog_task: Optional[asyncio.Task] = None

        self.progress_bar = ft.ProgressBar(value=0, visible=False, expand=True)
        self.status_text = ft.Text("", size=12, italic=True, visible=False)
        self.actions_row = ft.Row(controls=[], alignment=ft.MainAxisAlignment.END, spacing=8)
        self.btn_cancel = ft.TextButton("Agora não", on_click=self._close_dialog)
        self.btn_update = ft.FilledButton(
            "Atualizar Agora",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_click_iniciar_download,
        )
        self.actions_row.controls = [self.btn_cancel, self.btn_update]

    def _close_dialog(self, _e=None) -> None:
        if self.page:
            try:
                self.page.pop_dialog()
            except Exception:
                pass
        if self.on_dismiss and callable(self.on_dismiss):
            self.on_dismiss()

    def _cancelar_download(self, _e=None) -> None:
        if self.download_task and not self.download_task.done():
            self.download_task.cancel()

    def _on_click_iniciar_download(self, _e=None) -> None:
        if self._dialog_task and not self._dialog_task.done():
            self._dialog_task.cancel()
        self._dialog_task = asyncio.create_task(self._iniciar_download())

    def _on_progress(self, progress_ratio: float, downloaded: int, total: int) -> None:
        self.progress_bar.value = progress_ratio
        if total > 0:
            mb_down = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            pct = int(progress_ratio * 100)
            self.status_text.value = f"Baixando: {pct}% ({mb_down:.1f} MB / {mb_total:.1f} MB)"
        else:
            mb_down = downloaded / (1024 * 1024)
            self.status_text.value = f"Baixando: {mb_down:.1f} MB"
        self.page.update()

    def _handle_download_success(self, saved_apk_path: str) -> None:
        self.progress_bar.value = 1.0
        self.status_text.value = "Download concluído! Iniciando instalador..."
        self.status_text.color = ft.Colors.GREEN_400
        self.actions_row.controls = [
            ft.TextButton("Fechar", on_click=self._close_dialog),
            ft.FilledButton(
                "Instalar Agora",
                icon=ft.Icons.INSTALL_MOBILE,
                on_click=lambda ev: asyncio.create_task(
                    trigger_apk_installation(self.page, saved_apk_path, self.download_url)
                ),
            ),
        ]
        self.page.update()

    def _handle_download_cancelled(self) -> None:
        self.status_text.value = "Download cancelado."
        self.status_text.color = ft.Colors.AMBER_400
        self.actions_row.controls = [self.btn_cancel, self.btn_update]
        self.page.update()

    def _handle_download_error(self, err: Exception) -> None:
        self.status_text.value = f"Falha no download: {err}"
        self.status_text.color = ft.Colors.RED_400
        self.actions_row.controls = [
            ft.TextButton("Fechar", on_click=self._close_dialog),
            ft.FilledButton(
                "Baixar pelo Navegador",
                icon=ft.Icons.OPEN_IN_BROWSER,
                on_click=lambda ev: asyncio.create_task(
                    trigger_apk_installation(self.page, "", self.download_url)
                ),
            ),
        ]
        self.page.update()

    async def _iniciar_download(self) -> None:
        if not self.download_url:
            self.status_text.value = "URL de download indisponível."
            self.status_text.color = ft.Colors.RED_400
            self.status_text.visible = True
            self.page.update()
            return

        self.progress_bar.visible = True
        self.progress_bar.value = None
        self.status_text.visible = True
        self.status_text.value = "Iniciando download da atualização..."
        self.status_text.color = ft.Colors.BLUE_200

        self.actions_row.controls = [
            ft.TextButton("Cancelar", on_click=self._cancelar_download)
        ]
        self.page.update()

        try:
            self.download_task = asyncio.create_task(
                self.updater_service.download_apk(
                    download_url=self.download_url,
                    on_progress=self._on_progress,
                )
            )
            saved_apk_path = await self.download_task
            self._handle_download_success(saved_apk_path)
            await trigger_apk_installation(self.page, saved_apk_path, self.download_url)
        except asyncio.CancelledError:
            self._handle_download_cancelled()
            raise
        except Exception as err:
            self._handle_download_error(err)

    def _build_version_card(self) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text("Versão Atual", size=11, color=ft.Colors.GREY_400),
                            ft.Text(f"v{self.current_version}", weight=ft.FontWeight.BOLD, size=14),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Icon(ft.Icons.ARROW_FORWARD, size=18, color=ft.Colors.BLUE_400),
                    ft.Column(
                        controls=[
                            ft.Text("Nova Versão", size=11, color=ft.Colors.GREEN_400),
                            ft.Text(
                                f"v{self.latest_version}",
                                weight=ft.FontWeight.BOLD,
                                size=14,
                                color=ft.Colors.GREEN_400,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=8,
            padding=ft.Padding.all(12),
        )

    def _build_notes_container(self) -> ft.Container:
        notes_content = (
            self.release_notes
            if self.release_notes
            else "Esta atualização inclui correções de bugs, melhorias de desempenho e novas funcionalidades."
        )
        return ft.Container(
            content=ft.Column(
                controls=[ft.Text(notes_content, size=12, selectable=True)],
                scroll=ft.ScrollMode.AUTO,
            ),
            height=160,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border_radius=8,
            padding=ft.Padding.all(10),
        )

    def build_dialog(self) -> ft.AlertDialog:
        return ft.AlertDialog(
            modal=True,
            title=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SYSTEM_UPDATE, color=ft.Colors.BLUE_400, size=28),
                    ft.Text("Atualização Disponível", weight=ft.FontWeight.BOLD, size=18),
                ],
                spacing=10,
            ),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        self._build_version_card(),
                        ft.Text("Novidades:", weight=ft.FontWeight.BOLD, size=13),
                        self._build_notes_container(),
                        self.progress_bar,
                        self.status_text,
                    ],
                    tight=True,
                    spacing=10,
                ),
                width=360,
            ),
            actions=[self.actions_row],
        )

    def show(self) -> None:
        dialog = self.build_dialog()
        try:
            self.page.show_dialog(dialog)
        except Exception:
            if hasattr(self.page, "open"):
                self.page.open(dialog)


def show_update_dialog(
    page: ft.Page,
    update_info: Dict[str, Any],
    updater_service: UpdaterService,
    on_dismiss: Optional[Any] = None,
) -> None:
    """
    Renderiza e abre o ft.AlertDialog informando a nova versão e permitindo
    o download com barra de progresso.
    """
    dialog_controller = UpdateDialog(page, update_info, updater_service, on_dismiss)
    dialog_controller.show()
