"""
Diálogo de Atualização Automática para Flet.
Exibe informações da nova versão, notas da release, barra de progresso em tempo real
e executa o disparo da instalação do pacote .apk.
"""

import os
import sys
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


def show_update_dialog(
    page: ft.Page,
    update_info: Dict[str, Any],
    updater_service: UpdaterService,
    on_dismiss: Optional[Any] = None,
):
    """
    Renderiza e abre o ft.AlertDialog informando a nova versão e permitindo
    o download com barra de progresso.
    """
    latest_version = update_info.get("latest_version", "Nova Versão")
    current_version = update_info.get("current_version", "")
    release_notes = update_info.get("release_notes", "").strip()
    download_url = update_info.get("download_url") or update_info.get("html_url")

    # Controles dinâmicos de progresso
    progress_bar = ft.ProgressBar(value=0, visible=False, expand=True)
    status_text = ft.Text("", size=12, italic=True, visible=False)
    download_task: Optional[asyncio.Task] = None

    def _close_dialog(e=None):
        if page:
            try:
                page.pop_dialog()
            except Exception:
                pass
        if on_dismiss and callable(on_dismiss):
            on_dismiss()

    btn_cancel = ft.TextButton("Agora não", on_click=_close_dialog)
    
    # Container dinâmico para ações do rodapé
    actions_row = ft.Row(
        controls=[],
        alignment=ft.MainAxisAlignment.END,
        spacing=8,
    )

    async def _iniciar_download(e=None):
        nonlocal download_task
        if not download_url:
            status_text.value = "URL de download indisponível."
            status_text.color = ft.Colors.RED_400
            status_text.visible = True
            page.update()
            return

        # Atualiza a interface para estado de download
        progress_bar.visible = True
        progress_bar.value = None  # Indeterminado até os primeiros bytes
        status_text.visible = True
        status_text.value = "Iniciando download da atualização..."
        status_text.color = ft.Colors.BLUE_200

        actions_row.controls = [
            ft.TextButton(
                "Cancelar",
                on_click=lambda ev: _cancelar_download(),
            )
        ]
        page.update()

        def _on_progress(progress_ratio: float, downloaded: int, total: int):
            progress_bar.value = progress_ratio
            if total > 0:
                mb_down = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                pct = int(progress_ratio * 100)
                status_text.value = f"Baixando: {pct}% ({mb_down:.1f} MB / {mb_total:.1f} MB)"
            else:
                mb_down = downloaded / (1024 * 1024)
                status_text.value = f"Baixando: {mb_down:.1f} MB"
            page.update()

        try:
            download_task = asyncio.create_task(
                updater_service.download_apk(
                    download_url=download_url,
                    on_progress=_on_progress,
                )
            )
            saved_apk_path = await download_task

            # Download concluído com sucesso
            progress_bar.value = 1.0
            status_text.value = "Download concluído! Iniciando instalador..."
            status_text.color = ft.Colors.GREEN_400

            actions_row.controls = [
                ft.TextButton("Fechar", on_click=_close_dialog),
                ft.FilledButton(
                    "Instalar Agora",
                    icon=ft.Icons.INSTALL_MOBILE,
                    on_click=lambda ev: asyncio.create_task(
                        trigger_apk_installation(page, saved_apk_path, download_url)
                    ),
                ),
            ]
            page.update()

            # Dispara automaticamente a instalação nativa
            await trigger_apk_installation(page, saved_apk_path, download_url)

        except asyncio.CancelledError:
            status_text.value = "Download cancelado."
            status_text.color = ft.Colors.AMBER_400
            actions_row.controls = [
                btn_cancel,
                btn_update,
            ]
            page.update()
        except Exception as err:
            status_text.value = f"Falha no download: {err}"
            status_text.color = ft.Colors.RED_400
            actions_row.controls = [
                ft.TextButton("Fechar", on_click=_close_dialog),
                ft.FilledButton(
                    "Baixar pelo Navegador",
                    icon=ft.Icons.OPEN_IN_BROWSER,
                    on_click=lambda ev: asyncio.create_task(
                        trigger_apk_installation(page, "", download_url)
                    ),
                ),
            ]
            page.update()

    def _cancelar_download():
        nonlocal download_task
        if download_task and not download_task.done():
            download_task.cancel()

    btn_update = ft.FilledButton(
        "Atualizar Agora",
        icon=ft.Icons.DOWNLOAD,
        on_click=lambda e: asyncio.create_task(_iniciar_download(e)),
    )

    actions_row.controls = [btn_cancel, btn_update]

    # Notas da release com rolagem
    notes_content = (
        release_notes
        if release_notes
        else "Esta atualização inclui correções de bugs, melhorias de desempenho e novas funcionalidades."
    )

    dialog = ft.AlertDialog(
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
                    # Bloco comparativo de versão
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Column(
                                    controls=[
                                        ft.Text("Versão Atual", size=11, color=ft.Colors.GREY_400),
                                        ft.Text(f"v{current_version}", weight=ft.FontWeight.BOLD, size=14),
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Icon(ft.Icons.ARROW_FORWARD, size=18, color=ft.Colors.BLUE_400),
                                ft.Column(
                                    controls=[
                                        ft.Text("Nova Versão", size=11, color=ft.Colors.GREEN_400),
                                        ft.Text(
                                            f"v{latest_version}",
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
                    ),
                    # Seção com notas da versão
                    ft.Text("Novidades:", weight=ft.FontWeight.BOLD, size=13),
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Text(notes_content, size=12, selectable=True),
                            ],
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        height=160,
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                        border_radius=8,
                        padding=ft.Padding.all(10),
                    ),
                    # Indicador de progresso
                    progress_bar,
                    status_text,
                ],
                tight=True,
                spacing=10,
            ),
            width=360,
        ),
        actions=[actions_row],
    )

    try:
        page.show_dialog(dialog)
    except Exception:
        if hasattr(page, "open"):
            page.open(dialog)
