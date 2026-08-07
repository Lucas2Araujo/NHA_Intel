import pytest
from src.repositories.hino_repository import HinoRepository


@pytest.mark.asyncio
async def test_get_all_returns_all_hymns(in_memory_db):
    repository = HinoRepository(in_memory_db)
    hinos = await repository.get_all()
    assert len(hinos) == 3
    assert hinos[0].numero == "1"
    assert hinos[0].titulo == "Santo, Santo, Santo!"


@pytest.mark.asyncio
async def test_get_all_empty_database(in_memory_db):
    conn = await in_memory_db.get_connection()
    await conn.execute("DELETE FROM hino;")
    await conn.commit()

    repository = HinoRepository(in_memory_db)
    hinos = await repository.get_all()
    assert len(hinos) == 0


@pytest.mark.asyncio
async def test_get_by_id_parameterized_query(in_memory_db):
    repository = HinoRepository(in_memory_db)
    hino = await repository.get_by_id(1)
    assert hino is not None
    assert hino.id == 1
    assert hino.numero == "1"
    assert hino.titulo == "Santo, Santo, Santo!"


@pytest.mark.asyncio
async def test_search_hymns_by_title_and_number(in_memory_db):
    repository = HinoRepository(in_memory_db)

    # Busca por número
    results_num = await repository.search("2")
    assert len(results_num) == 1
    assert results_num[0].titulo == "Ó Adorai o Senhor"

    # Busca por palavra do título
    results_title = await repository.search("Santo")
    assert len(results_title) == 1
    assert results_title[0].numero == "1"


@pytest.mark.asyncio
async def test_get_metadados_relacionados(in_memory_db):
    repository = HinoRepository(in_memory_db)
    relacionados = await repository.get_metadados_relacionados(1)
    assert isinstance(relacionados, dict)
    assert "temas" in relacionados
    assert "textos_biblicos" in relacionados


@pytest.mark.asyncio
async def test_get_categorias_e_temas(in_memory_db):
    repository = HinoRepository(in_memory_db)

    categorias = await repository.get_categorias()
    assert "Adoração" in categorias

    temas = await repository.get_temas()
    assert "Adoração" in temas
    assert "Santidade" in temas


@pytest.mark.asyncio
async def test_search_by_categoria_e_tema(in_memory_db):
    repository = HinoRepository(in_memory_db)

    # Busca por categoria
    hinos_cat = await repository.search_by_categoria("Adoração")
    assert len(hinos_cat) == 3

    # Busca por tema
    hinos_tema = await repository.search_by_tema("Santidade")
    assert len(hinos_tema) == 1
    assert hinos_tema[0].id == 1

