import pytest
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.historico_repository import HistoricoRepository
from src.database.connection import DatabaseConnection


@pytest.mark.asyncio
async def test_add_and_remove_favorito(in_memory_db: DatabaseConnection):
    """
    Testa adicionar e remover um hino dos favoritos.
    """
    repo = FavoritoRepository(in_memory_db)

    # Inicialmente não é favorito
    assert await repo.is_favorito(1) is False

    # Adiciona aos favoritos
    added = await repo.add_favorito(1)
    assert added is True
    assert await repo.is_favorito(1) is True

    # Lista de favoritos deve conter 1 hino
    favoritos = await repo.get_favoritos()
    assert len(favoritos) == 1
    assert favoritos[0].id == 1
    assert favoritos[0].titulo == "Santo, Santo, Santo!"

    # Remove dos favoritos
    removed = await repo.remove_favorito(1)
    assert removed is True
    assert await repo.is_favorito(1) is False
    assert len(await repo.get_favoritos()) == 0


@pytest.mark.asyncio
async def test_add_and_get_historico(in_memory_db: DatabaseConnection):
    """
    Testa registrar acessos no histórico e buscar os recentes.
    """
    repo = HistoricoRepository(in_memory_db)

    # Adiciona acessos aos hinos 1 e 2
    await repo.add_acesso(1)
    await repo.add_acesso(2)

    recentes = await repo.get_recentes()
    assert len(recentes) == 2
    # Hino 2 foi o último a ser acessado
    assert recentes[0].id == 2
    assert recentes[1].id == 1
