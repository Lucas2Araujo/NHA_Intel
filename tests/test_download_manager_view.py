import pytest
from unittest.mock import MagicMock
import flet as ft
from src.repositories.hino_repository import HinoRepository
from src.services.media_service import MediaService
from src.views.download_manager_view import DownloadManagerView


def test_download_manager_view_build(in_memory_db, tmp_path):
    hino_repo = HinoRepository(in_memory_db)
    media_service = MediaService(download_dir=str(tmp_path))

    download_view_obj = DownloadManagerView(hino_repo, media_service)
    mock_page = MagicMock(spec=ft.Page)

    view = download_view_obj.build(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/downloads"
    assert view.bgcolor == ft.Colors.SURFACE
    assert len(view.controls) > 0
    assert isinstance(view.controls[0], ft.SafeArea)
