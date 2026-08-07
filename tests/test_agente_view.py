import pytest
from unittest.mock import MagicMock
import flet as ft
from src.repositories.hino_repository import HinoRepository
from src.repositories.culto_repository import CultoRepository
from src.services.agente_service import AgenteService
from src.views.agente_view import AgenteView


@pytest.mark.asyncio
async def test_agente_view_build(in_memory_db):
    hino_repo = HinoRepository(in_memory_db)
    culto_repo = CultoRepository(in_memory_db)
    agente_service = AgenteService(hino_repo)

    agente_view_obj = AgenteView(agente_service, culto_repo)
    mock_page = MagicMock(spec=ft.Page)

    view = await agente_view_obj.build(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/agente"
    assert len(view.controls) > 0
