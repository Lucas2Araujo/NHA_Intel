import asyncio
from unittest.mock import AsyncMock, MagicMock

import flet as ft
import pytest

from src.services.content_manager import ContentManager
from src.views.downloads_view import DownloadsView


@pytest.fixture
def mock_content_manager(tmp_path):
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()
    cm = ContentManager(modules_dir=modules_dir)
    cm.get_manifest = AsyncMock(
        return_value={
            "version": 1,
            "modules": [
                {
                    "id": "hinario_antigo",
                    "file": "hinario_antigo.db.gz",
                    "size_bytes": 623236,
                    "url": "https://example.com/hinario_antigo.db.gz",
                },
                {
                    "id": "ARA",
                    "file": "ARA.sqlite.gz",
                    "size_bytes": 1736290,
                    "url": "https://example.com/ARA.sqlite.gz",
                },
            ],
        }
    )
    return cm


def test_downloads_view_build(mock_content_manager):
    view_obj = DownloadsView(content_manager=mock_content_manager)
    mock_page = MagicMock(spec=ft.Page)
    mock_page.views = []
    mock_page.update = MagicMock()

    view = view_obj.build(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/downloads"
    assert view.appbar is not None
    assert len(view.controls) > 0


@pytest.mark.asyncio
async def test_downloads_view_rebuild_and_actions(mock_content_manager):
    view_obj = DownloadsView(content_manager=mock_content_manager)
    mock_page = MagicMock(spec=ft.Page)
    mock_page.views = []
    mock_page.update = MagicMock()
    mock_page.overlay = []

    view_obj.build(mock_page)

    # Aguarda o carregamento do manifesto
    await view_obj._load_manifest_and_render(mock_page)

    # Verifica se os cards foram inseridos
    assert len(view_obj.hinarios_column.controls) >= 1
    assert len(view_obj.biblias_column.controls) >= 1

    # Simula download
    mock_content_manager.download_module = AsyncMock()
    ara_info = {
        "id": "ARA",
        "file": "ARA.sqlite.gz",
        "size_bytes": 1736290,
        "url": "https://example.com/ARA.sqlite.gz",
    }
    await view_obj._start_download_action(mock_page, ara_info)
    mock_content_manager.download_module.assert_called_once()

    # Simula exclusão
    mock_content_manager.delete_module = AsyncMock(return_value=True)
    await view_obj._delete_module_action(mock_page, "ARA")
    mock_content_manager.delete_module.assert_called_once_with("ARA", page=mock_page)


def test_downloads_view_formatting():
    assert DownloadsView._format_size(1736290) == "1.66 MB"
    assert DownloadsView._format_size(0) == "Tamanho desconhecido"
    assert DownloadsView._format_size(None) == "Tamanho desconhecido"

