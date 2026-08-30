"""
Diálogo de Atualização Automática para Flet.
Exibe informações da nova versão, notas da release formatadas em Markdown,
identificação de arquitetura de CPU, barra de progresso em tempo real,
validação de integridade e disparo da instalação do pacote .apk ou fallback no navegador.
"""

import asyncio
import os
from typing import Any

import flet as ft

from src.services.updater_service import UpdaterService


async def open_in_browser(url: str) -> None:
    """Abre a URL especificada no navegador padrão do dispositivo."""
    if not url:
        return
    try:
        await ft.UrlLauncher().launch_url(url)
    except Exception:
        pass


async def trigger_apk_installation(apk_path: str, fallback_url: str | None = None):
    """
    Dispara a instalação do arquivo .apk no Android via Intent nativa do PackageInstaller.
    Se não for possível abrir localmente, aciona o fallback para o navegador.
    """
    launched = False

    # 1. Tenta disparar o instalador via URI local (Intent do Android)
    if apk_path and os.path.exists(apk_path):
        local_uri = f"file://{os.path.abspath(apk_path)}"
        try:
            await ft.UrlLauncher().launch_url(local_uri)
            launched = True
        except Exception:
            launched = False

    # 2. Fallback: se não conseguiu abrir via file:// ou se falhou, abre no navegador
    if not launched and fallback_url:
        await open_in_browser(fallback_url)


class UpdateDialog:
    """Controlador do diálogo modal de atualização do aplicativo."""

    def __init__(
        self,
        page: ft.Page,
        update_info: dict[str, Any],
        updater_service: UpdaterService,
        on_dismiss: Any | None = None,
    ):
        self.page = page
        self.update_info = update_info
        self.updater_service = updater_service
        self.on_dismiss = on_dismiss

        self.latest_version: str = update_info.get("latest_version", "Nova Versão")
        self.current_version: str = update_info.get("current_version", "")
        self.release_notes: str = update_info.get("release_notes", "").strip()
        self.download_url: str | None = update_info.get(
            "download_url"
        ) or update_info.get("html_url")
        self.html_url: str | None = update_info.get("html_url") or self.download_url
        self.asset_name: str | None = update_info.get("asset_name")
        self.asset_size: int | None = update_info.get("asset_size")
        self.expected_sha256: str | None = update_info.get("expected_sha256")
        self.detected_arch: str = update_info.get(
            "detected_arch", UpdaterService.get_device_architecture()
        )

        self.download_task: asyncio.Task | None = None
        self._dialog_task: asyncio.Task | None = None

        self.progress_bar = ft.ProgressBar(value=0, visible=False, expand=True)
        self.status_text = ft.Text("", size=12, italic=True, visible=False)
        self.actions_row = ft.Row(
            controls=[], alignment=ft.MainAxisAlignment.END, spacing=8
        )
        self.btn_cancel = ft.TextButton("Agora não", on_click=self._close_dialog)
        self.btn_update = ft.FilledButton(
            "Atualizar Agora",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_click_iniciar_download,
        )
        self.actions_row.controls = [self.btn_cancel, self.btn_update]

    def _close_dialog(self, _e=None) -> None:
        if self.download_task and not self.download_task.done():
            self.download_task.cancel()
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
            self.status_text.value = (
                f"Baixando: {pct}% ({mb_down:.1f} MB / {mb_total:.1f} MB)"
            )
        else:
            mb_down = downloaded / (1024 * 1024)
            self.status_text.value = f"Baixando: {mb_down:.1f} MB"
        self.page.update()

    def _handle_download_success(self, saved_apk_path: str) -> None:
        self.progress_bar.value = 1.0
        self.status_text.value = (
            "Download concluído e validado! Iniciando instalador..."
        )
        self.status_text.color = ft.Colors.GREEN_400
        self.actions_row.controls = [
            ft.TextButton("Fechar", on_click=self._close_dialog),
            ft.FilledButton(
                "Instalar Agora",
                icon=ft.Icons.INSTALL_MOBILE,
                on_click=lambda ev: asyncio.create_task(
                    trigger_apk_installation(saved_apk_path, self.download_url)
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
            ft.OutlinedButton(
                "Tentar Novamente",
                icon=ft.Icons.REFRESH,
                on_click=self._on_click_iniciar_download,
            ),
            ft.FilledButton(
                "Baixar no Navegador",
                icon=ft.Icons.OPEN_IN_BROWSER,
                on_click=lambda ev: asyncio.create_task(
                    open_in_browser(self.download_url or self.html_url or "")
                ),
            ),
        ]
        self.page.update()

    async def _iniciar_download(self) -> None:
        if not self.download_url:
            self.status_text.value = "URL de download indisponível."
            self.status_text.color = ft.Colors.RED_400
            self.status_text.visible = True
            self.actions_row.controls = [
                ft.TextButton("Fechar", on_click=self._close_dialog),
                ft.FilledButton(
                    "Abrir GitHub",
                    icon=ft.Icons.OPEN_IN_BROWSER,
                    on_click=lambda ev: asyncio.create_task(
                        open_in_browser(self.html_url or "")
                    ),
                ),
            ]
            self.page.update()
            return

        self.progress_bar.visible = True
        self.progress_bar.value = None
        self.status_text.visible = True
        self.status_text.value = "Iniciando download do APK compatível..."
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
                    filename=self.asset_name,
                    expected_size=self.asset_size,
                    expected_sha256=self.expected_sha256,
                )
            )
            saved_apk_path = await self.download_task
            self._handle_download_success(saved_apk_path)
            await trigger_apk_installation(saved_apk_path, self.download_url)
        except asyncio.CancelledError:
            self._handle_download_cancelled()
            raise
        except Exception as err:
            self._handle_download_error(err)

    def _build_version_card(self) -> ft.Container:
        arch_label = UpdaterService.format_architecture_label(self.detected_arch)

        info_items: list[ft.Control] = [
            ft.Container(
                content=ft.Text(
                    f"CPU: {arch_label}",
                    size=11,
                    weight=ft.FontWeight.W_500,
                    color=ft.Colors.BLUE_300,
                ),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border_radius=6,
            )
        ]

        if self.asset_size and self.asset_size > 0:
            size_mb = self.asset_size / (1024 * 1024)
            info_items.append(
                ft.Container(
                    content=ft.Text(
                        f"{size_mb:.1f} MB",
                        size=11,
                        weight=ft.FontWeight.W_500,
                        color=ft.Colors.GREY_300,
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                )
            )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        "Versão Atual",
                                        size=11,
                                        color=ft.Colors.GREY_400,
                                    ),
                                    ft.Text(
                                        f"v{self.current_version}",
                                        weight=ft.FontWeight.BOLD,
                                        size=14,
                                    ),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Icon(
                                ft.Icons.ARROW_FORWARD,
                                size=18,
                                color=ft.Colors.BLUE_400,
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        "Nova Versão",
                                        size=11,
                                        color=ft.Colors.GREEN_400,
                                    ),
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
                    ft.Row(
                        controls=info_items,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=8,
                    ),
                ],
                spacing=8,
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
                controls=[
                    ft.Markdown(
                        notes_content,
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                    )
                ],
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
                    ft.Text(
                        "Atualização Disponível", weight=ft.FontWeight.BOLD, size=18
                    ),
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
    update_info: dict[str, Any],
    updater_service: UpdaterService,
    on_dismiss: Any | None = None,
) -> None:
    """
    Renderiza e abre o ft.AlertDialog informando a nova versão e permitindo
    o download com barra de progresso.
    """
    dialog_controller = UpdateDialog(page, update_info, updater_service, on_dismiss)
    dialog_controller.show()
