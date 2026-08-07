import pytest
from unittest.mock import MagicMock
import flet as ft
from src.repositories.hino_repository import HinoRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.views.home_view import HomeView


@pytest.mark.asyncio
async def test_home_view_build(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    fav_repo = FavoritoRepository(in_memory_db)
    hist_repo = HistoricoRepository(in_memory_db)

    home_view_obj = HomeView(hino_repo, fav_repo, hist_repo)
    mock_page = MagicMock(spec=ft.Page)

    view = await home_view_obj.build(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/"
    assert len(view.controls) > 0
