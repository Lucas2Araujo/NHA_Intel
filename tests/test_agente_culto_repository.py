import pytest
from src.repositories.culto_repository import CultoRepository
from src.repositories.hino_repository import HinoRepository
from src.services.agente_service import AgenteService
from src.database.connection import DatabaseConnection


@pytest.mark.asyncio
async def test_culto_repository_create_and_get(in_memory_db: DatabaseConnection):
    """
    Testa a criação e recuperação de listas de culto no CultoRepository.
    """
    repo = CultoRepository(in_memory_db)

    # Cria uma lista de culto
    lista_id = await repo.create_lista_culto("Culto de Ação de Graças", [1, 2, 3])
    assert lista_id is not None

    # Busca as listas de culto
    listas = await repo.get_listas_culto()
    assert len(listas) == 1
    assert listas[0]["tema_gerador"] == "Culto de Ação de Graças"
    assert listas[0]["total_hinos"] == 3

    # Busca os hinos pertencentes à lista
    hinos = await repo.get_hinos_da_lista(lista_id)
    assert len(hinos) == 3
    assert hinos[0].id == 1
    assert hinos[1].id == 2


@pytest.mark.asyncio
async def test_agente_service_sugestao_culto(in_memory_db: DatabaseConnection):
    """
    Testa o algoritmo de sugestão semântica e blocos litúrgicos do AgenteService.
    """
    hino_repo = HinoRepository(in_memory_db)
    agente_service = AgenteService(hino_repo)

    resultado = await agente_service.sugerir_playlist_culto("Santo e Adoração")
    assert resultado is not None
    assert resultado["tema"] == "Santo e Adoração"
    assert len(resultado["blocos"]) > 0
    assert "Abertura" in resultado["blocos"][0]["bloco"]


@pytest.mark.asyncio
async def test_culto_repository_add_hino_a_lista(in_memory_db: DatabaseConnection):
    """
    Testa a adição de hino a uma lista de culto em CultoRepository.
    """
    repo = CultoRepository(in_memory_db)
    lista_id = await repo.create_lista_culto("Culto Jovem", [1])
    assert lista_id is not None

    sucesso = await repo.add_hino_a_lista(lista_id, 2)
    assert sucesso is True

    hinos = await repo.get_hinos_da_lista(lista_id)
    assert len(hinos) == 2
    assert hinos[1].id == 2

