import asyncio
import os
from pathlib import Path
from typing import Any

import flet as ft

from src.repositories.biblia_repository import BIBLE_VERSION_NAMES
from src.services.content_manager import ContentManager
from src.services.media_service import QUALITY_HD, QUALITY_SD, MediaService
from src.services.theme_service import ThemeService


class DownloadsView:
    """
    Tela moderna e completa para gerenciamento de downloads no Hinário Inteligente.
    Organizada em seções:
    - Seção Hinários: Hinário Antigo (1996) e Hinário Comparativo
    - Seção Bíblias: Todas as versões listadas no manifesto (ARA, NVI, NTLH, KJA, etc.)
    - Aba Secundária: Gerenciamento e download em lote de mídias de vídeo (SD/HD)
    """

    def __init__(
        self,
        content_manager: ContentManager | None = None,
        media_service: MediaService | None = None,
        theme_service: ThemeService | None = None,
    ):
        self.content_manager = content_manager or ContentManager()
        self.media_service = media_service
        self.theme_service = theme_service

        self.page: ft.Page | None = None
        self.manifest_data: dict[str, Any] = {"version": 1, "modules": []}
        self.download_progress: dict[str, float] = {}
        self.downloading_ids: set[str] = set()

        # Elementos de UI reativos
        self.storage_summary_text = ft.Text("", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        self.hinarios_column = ft.Column(spacing=10)
        self.biblias_column = ft.Column(spacing=10)
        self.loading_indicator = ft.ProgressRing(visible=False, width=24, height=24)

    def _get_accent_color(self) -> str:
        if self.theme_service:
            return self.theme_service.get_accent_color("novo")
        return ft.Colors.PRIMARY

    @staticmethod
    def _format_size(size_bytes: int | float | None) -> str:
        """Formata tamanho em bytes para MB com 2 casas decimais."""
        if not size_bytes or size_bytes <= 0:
            return "Tamanho desconhecido"
        mb = size_bytes / (1024 * 1024)
        return f"{mb:.2f} MB"

    def _calculate_total_installed_storage(self) -> str:
        """Calcula o espaço total em disco utilizado pelos módulos instalados."""
        modules_dir = self.content_manager.modules_dir
        if not modules_dir.exists():
            return "0 MB utilizados"

        total_bytes = 0
        try:
            for item in modules_dir.rglob("*"):
                if item.is_file():
                    total_bytes += item.stat().st_size
        except Exception:
            pass

        return f"{total_bytes / (1024 * 1024):.1f} MB utilizados em módulos"

    def _refresh_storage_text(self) -> None:
        self.storage_summary_text.value = self._calculate_total_installed_storage()

    def _show_snackbar(
        self, page: ft.Page, message: str, is_error: bool = False
    ) -> None:
        """Exibe feedback visual via SnackBar."""
        sb = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
            bgcolor=ft.Colors.RED_700 if is_error else ft.Colors.GREEN_700,
            duration=4000,
            behavior=ft.SnackBarBehavior.FLOATING,
        )
        if hasattr(page, "overlay"):
            page.overlay.append(sb)
            sb.open = True
            page.update()

    def _get_module_title_and_subtitle(
        self, mod_id: str, mod_info: dict[str, Any]
    ) -> tuple[str, str]:
        """Retorna nome amigável e descrição formatada para o item do módulo."""
        size_str = self._format_size(mod_info.get("size_bytes"))

        if mod_id == "hinario_antigo":
            return "Hinário Tradicional (1996)", f"613 Hinos clássicos • {size_str}"
        elif mod_id == "hinario_comparativo":
            return (
                "Hinário Comparativo (1996 ↔ 2022)",
                f"Comparador estrofe a estrofe e diffs • {size_str}",
            )
        elif mod_id == "hinario":
            return "Hinário Novo (2022)", f"Embutido de fábrica (Padrão) • {size_str}"

        # É uma Bíblia
        version_full_name = BIBLE_VERSION_NAMES.get(mod_id, mod_id)
        return (
            f"{version_full_name} ({mod_id})",
            f"Tradução Completa (66 Livros) • {size_str}",
        )

    def _build_module_card(
        self, page: ft.Page, mod_info: dict[str, Any]
    ) -> ft.Container:
        """Constrói o card individual de um módulo com botões de ação e barra de progresso."""
        mod_id = str(mod_info.get("id", ""))
        is_installed = self.content_manager.is_module_installed(mod_id)
        is_downloading = mod_id in self.downloading_ids
        progress_val = self.download_progress.get(mod_id, 0.0)

        title, subtitle = self._get_module_title_and_subtitle(mod_id, mod_info)

        # Ícone do módulo
        if mod_id in ("hinario_antigo", "hinario_comparativo", "hinario"):
            icon_data = ft.Icons.MENU_BOOK if mod_id != "hinario_comparativo" else ft.Icons.COMPARE_ARROWS
            icon_color = ft.Colors.AMBER_400
        else:
            icon_data = ft.Icons.AUTO_STORIES
            icon_color = ft.Colors.GREEN_400

        # Controles de Ação à direita
        action_controls: list[ft.Control] = []

        if is_downloading:
            action_controls.extend(
                [
                    ft.Column(
                        controls=[
                            ft.Text(
                                f"{int(progress_val * 100)}%",
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=self._get_accent_color(),
                            ),
                            ft.ProgressBar(
                                value=progress_val,
                                width=90,
                                color=self._get_accent_color(),
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                    )
                ]
            )
        elif is_installed:
            action_controls.extend(
                [
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE,
                                    size=16,
                                    color=ft.Colors.GREEN_400,
                                ),
                                ft.Text(
                                    "Instalado",
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.GREEN_400,
                                ),
                            ],
                            spacing=4,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        border_radius=8,
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=ft.Colors.RED_400,
                        tooltip=f"Excluir {mod_id}",
                        on_click=lambda e, m_id=mod_id: asyncio.create_task(
                            self._delete_module_action(page, m_id)
                        ),
                    ),
                ]
            )
        else:
            action_controls.append(
                ft.FilledButton(
                    "Baixar",
                    icon=ft.Icons.DOWNLOAD,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    on_click=lambda e, m_info=mod_info: asyncio.create_task(
                        self._start_download_action(page, m_info)
                    ),
                )
            )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(icon_data, size=24, color=icon_color),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                        border_radius=10,
                        padding=ft.Padding.all(10),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(title, size=15, weight=ft.FontWeight.W_600),
                            ft.Text(subtitle, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Row(
                        controls=action_controls,
                        spacing=6,
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border_radius=12,
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )

    async def _start_download_action(
        self, page: ft.Page, mod_info: dict[str, Any]
    ) -> None:
        """Inicia o download e descompactação de um módulo."""
        mod_id = str(mod_info.get("id", ""))
        if mod_id in self.downloading_ids:
            return

        self.downloading_ids.add(mod_id)
        self.download_progress[mod_id] = 0.0
        self._rebuild_module_lists(page)

        def _progress_callback(val: float) -> None:
            self.download_progress[mod_id] = val
            self._rebuild_module_lists(page)

        try:
            await self.content_manager.download_module(
                module_info=mod_info,
                on_progress=_progress_callback,
                page=page,
            )
            title, _ = self._get_module_title_and_subtitle(mod_id, mod_info)
            self._show_snackbar(page, f"Módulo '{title}' instalado com sucesso!")
        except asyncio.CancelledError:
            self._show_snackbar(page, f"Download de '{mod_id}' cancelado.", is_error=True)
            raise
        except Exception:
            self._show_snackbar(
                page,
                f"Erro ao baixar módulo '{mod_id}': verifique sua conexão.",
                is_error=True,
            )
        finally:
            self.downloading_ids.discard(mod_id)
            self.download_progress.pop(mod_id, None)
            self._refresh_storage_text()
            self._rebuild_module_lists(page)

    async def _delete_module_action(self, page: ft.Page, mod_id: str) -> None:
        """Exclui um módulo instalado."""
        try:
            success = await self.content_manager.delete_module(mod_id, page=page)
            if success:
                self._show_snackbar(page, f"Módulo '{mod_id}' excluído com sucesso.")
            else:
                self._show_snackbar(page, f"Módulo '{mod_id}' não encontrado.", is_error=True)
        except Exception as exc:
            self._show_snackbar(
                page, f"Erro ao excluir '{mod_id}': {exc}", is_error=True
            )
        finally:
            self._refresh_storage_text()
            self._rebuild_module_lists(page)

    def _rebuild_module_lists(self, page: ft.Page) -> None:
        """Atualiza os controles das listas de hinários e bíblias na interface."""
        modules = self.manifest_data.get("modules", [])

        hinarios_controls: list[ft.Control] = []
        biblias_controls: list[ft.Control] = []

        for m in modules:
            m_id = str(m.get("id", ""))
            # Oculta o hinário novo da lista de downloads pois ele é o padrão embutido
            if m_id == "hinario":
                continue

            card = self._build_module_card(page, m)
            if m_id in ("hinario_antigo", "hinario_comparativo"):
                hinarios_controls.append(card)
            else:
                biblias_controls.append(card)

        if not hinarios_controls:
            hinarios_controls.append(
                ft.Text("Nenhum hinário secundário disponível.", italic=True, size=13)
            )
        if not biblias_controls:
            biblias_controls.append(
                ft.Text("Nenhuma tradução bíblica disponível.", italic=True, size=13)
            )

        self.hinarios_column.controls = hinarios_controls
        self.biblias_column.controls = biblias_controls
        try:
            page.update()
        except Exception:
            pass

    async def _load_manifest_and_render(self, page: ft.Page, force_refresh: bool = False) -> None:
        """Busca o manifesto e recarrega a UI."""
        self.loading_indicator.visible = True
        try:
            page.update()
        except Exception:
            pass

        try:
            self.manifest_data = await self.content_manager.get_manifest(
                force_refresh=force_refresh
            )
        except Exception:
            pass
        finally:
            self.loading_indicator.visible = False
            self._refresh_storage_text()
            self._rebuild_module_lists(page)

    def build(self, page: ft.Page) -> ft.View:
        """Constrói a View do Gerenciador de Downloads."""
        self.page = page

        if self.theme_service:
            self.theme_service.apply_theme(page)

        self._refresh_storage_text()

        # Dispara carregamento assíncrono do manifesto se houver event loop ativo
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._load_manifest_and_render(page))
        except RuntimeError:
            pass

        async def _go_back(e):
            if len(page.views) > 1:
                page.views.pop()
                top_view = page.views[-1]
                await page.push_route(top_view.route)
            else:
                await page.push_route("/")

        # Cabeçalho com estatísticas de armazenamento
        header_card = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.STORAGE, size=24, color=self._get_accent_color()),
                    ft.Column(
                        controls=[
                            ft.Text(
                                "Armazenamento de Módulos",
                                weight=ft.FontWeight.BOLD,
                                size=14,
                            ),
                            self.storage_summary_text,
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    self.loading_indicator,
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        tooltip="Atualizar Manifesto da Nuvem",
                        on_click=lambda e: asyncio.create_task(
                            self._load_manifest_and_render(page, force_refresh=True)
                        ),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=12,
            padding=ft.Padding.all(14),
        )

        content_column = ft.Column(
            controls=[
                header_card,
                ft.Container(height=8),
                # Seção Hinários
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.LIBRARY_MUSIC, size=20, color=ft.Colors.AMBER_400),
                        ft.Text(
                            "Hinários Secundários",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(
                    "Baixe o Hinário Tradicional e o Comparativo histórico.",
                    size=12,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Container(height=4),
                self.hinarios_column,
                ft.Container(height=16),
                # Seção Bíblias
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.MENU_BOOK, size=20, color=ft.Colors.GREEN_400),
                        ft.Text(
                            "Traduções da Bíblia Sagrada",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(
                    "Baixe traduções completas para leitura integral e pesquisa off-line.",
                    size=12,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Container(height=4),
                self.biblias_column,
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=6,
            expand=True,
        )

        return ft.View(
            route="/downloads",
            bgcolor=ft.Colors.SURFACE,
            appbar=ft.AppBar(
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=_go_back),
                title=ft.Text("Módulos & Downloads", weight=ft.FontWeight.BOLD),
                center_title=True,
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            ),
            controls=[
                ft.SafeArea(
                    maintain_bottom_view_padding=True,
                    content=ft.Container(
                        content=content_column,
                        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                        expand=True,
                    ),
                    expand=True,
                )
            ],
        )
