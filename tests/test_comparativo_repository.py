import json
import pytest
import pytest_asyncio
from src.database.connection import DatabaseConnection
from src.repositories.comparativo_repository import ComparativoRepository
from src.models.comparativo import HinoComparativo, BlocoDiff, EstatisticasDiff


@pytest_asyncio.fixture
async def in_memory_comparativo_db():
    db_conn = DatabaseConnection(db_path=":memory:")
    conn = await db_conn.get_connection()

    await conn.execute("""
        CREATE TABLE comparativo_hinos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_novo TEXT,
            numero_antigo TEXT,
            titulo_novo TEXT,
            titulo_antigo TEXT,
            categoria_nova TEXT,
            categoria_antiga TEXT,
            status_comparacao TEXT,
            modificado INTEGER,
            similaridade_pct REAL,
            diff_texto TEXT,
            diff_json TEXT,
            resumo_alteracoes TEXT,
            metodo_cruzamento TEXT
        );
    """)

    sample_diff = {
        "similaridade_pct": 95.0,
        "estatisticas": {
            "linhas_adicionadas": 1,
            "linhas_removidas": 1,
            "linhas_alteradas": 2,
            "linhas_iguais": 5,
        },
        "blocos": [
            {"tipo": "igual", "texto": "Linha inalterada"},
            {"tipo": "modificado", "antigo": ["Linha Antiga"], "novo": ["Linha Nova"]},
            {"tipo": "adicionado", "texto": "Nova estrofe"},
            {"tipo": "removido", "texto": "Estrofe antiga"},
        ],
    }

    await conn.executemany(
        """
        INSERT INTO comparativo_hinos (
            id, numero_novo, numero_antigo, titulo_novo, titulo_antigo,
            status_comparacao, modificado, similaridade_pct, diff_texto,
            diff_json, resumo_alteracoes, metodo_cruzamento
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        [
            (1, "1", "18", "Santo, Santo, Santo!", "Santo! Santo! Santo!", "IDENTICO", 0, 100.0, "Letra idêntica", json.dumps({"similaridade_pct": 100.0, "estatisticas": {"linhas_adicionadas": 0, "linhas_removidas": 0, "linhas_alteradas": 0, "linhas_iguais": 12}, "blocos": [{"tipo": "igual", "texto": "Santo, Santo, Santo!"}]}), "Letra idêntica", "TITULO_EXATO"),
            (2, "3", "3", "O Deus Eterno Reina", "O Deus Eterno Reina", "MODIFICADO", 1, 95.0, "Diff texto aqui", json.dumps(sample_diff), "2 linha(s) modificada(s)", "NUMERO_E_TITULO"),
            (3, "11", None, "Maior Que Tudo", None, "NOVO_INEDITO", 1, 0.0, None, None, "Inédito", "INEDITO"),
            (4, None, "5", None, "Supremo Criador", "ANTIGO_DESCONTINUADO", 1, 0.0, None, None, "Descontinuado", "DESCONTINUADO"),
        ],
    )

    await conn.commit()
    yield db_conn
    await db_conn.close()


@pytest.mark.asyncio
async def test_get_by_numero_novo(in_memory_comparativo_db):
    repo = ComparativoRepository(in_memory_comparativo_db)

    # Teste encontrado
    comp = await repo.get_by_numero_novo("1")
    assert comp is not None
    assert comp.numero_novo == "1"
    assert comp.numero_antigo == "18"
    assert comp.status_comparacao == "IDENTICO"
    assert comp.similaridade_pct == 100.0

    # Teste modificado
    comp_mod = await repo.get_by_numero_novo("3")
    assert comp_mod is not None
    assert comp_mod.status_comparacao == "MODIFICADO"
    assert comp_mod.modificado == 1

    # Teste inexistente
    comp_none = await repo.get_by_numero_novo("9999")
    assert comp_none is None

    # Teste vazio
    assert await repo.get_by_numero_novo("") is None


@pytest.mark.asyncio
async def test_get_by_numero_antigo(in_memory_comparativo_db):
    repo = ComparativoRepository(in_memory_comparativo_db)

    comp = await repo.get_by_numero_antigo("5")
    assert comp is not None
    assert comp.numero_antigo == "5"
    assert comp.status_comparacao == "ANTIGO_DESCONTINUADO"
    assert comp.titulo_antigo == "Supremo Criador"

    assert await repo.get_by_numero_antigo("9999") is None
    assert await repo.get_by_numero_antigo("") is None


@pytest.mark.asyncio
async def test_get_all(in_memory_comparativo_db):
    repo = ComparativoRepository(in_memory_comparativo_db)
    all_items = await repo.get_all()
    assert len(all_items) == 4
    # Ordenação coloca itens com numero_novo primeiro
    assert all_items[0].numero_novo == "1"


@pytest.mark.asyncio
async def test_search_comparativo(in_memory_comparativo_db):
    repo = ComparativoRepository(in_memory_comparativo_db)

    # Busca por número exato
    res_num = await repo.search_comparativo("18")
    assert len(res_num) > 0
    assert res_num[0].numero_antigo == "18"

    # Busca por texto
    res_text = await repo.search_comparativo("Eterno")
    assert len(res_text) > 0
    assert res_text[0].titulo_novo == "O Deus Eterno Reina"

    # Busca vazia retorna todos
    res_empty = await repo.search_comparativo("")
    assert len(res_empty) == 4


def test_hino_comparativo_get_parsed_diff():
    sample_diff = {
        "similaridade_pct": 88.5,
        "estatisticas": {
            "linhas_adicionadas": 2,
            "linhas_removidas": 1,
            "linhas_alteradas": 3,
            "linhas_iguais": 10,
        },
        "blocos": [
            {"tipo": "igual", "texto": "Linha inalterada"},
            {"tipo": "modificado", "antigo": ["Linha Antiga 1", "Linha Antiga 2"], "novo": ["Linha Nova 1"]},
            {"tipo": "adicionado", "texto": "Linha Adicionada"},
            {"tipo": "removido", "texto": "Linha Removida"},
        ],
    }

    comp = HinoComparativo(
        id=1,
        numero_novo="10",
        numero_antigo="20",
        titulo_novo="Hino Teste",
        titulo_antigo="Hino Teste Antigo",
        status_comparacao="MODIFICADO",
        modificado=1,
        similaridade_pct=88.5,
        diff_json=json.dumps(sample_diff),
    )

    stats, blocos = comp.get_parsed_diff()
    assert stats is not None
    assert isinstance(stats, EstatisticasDiff)
    assert stats.linhas_adicionadas == 2
    assert stats.linhas_removidas == 1
    assert stats.linhas_alteradas == 3
    assert stats.linhas_iguais == 10

    assert len(blocos) == 4
    assert blocos[0].tipo == "igual"
    assert blocos[0].texto == "Linha inalterada"

    assert blocos[1].tipo == "modificado"
    assert blocos[1].antigo == ["Linha Antiga 1", "Linha Antiga 2"]
    assert blocos[1].novo == ["Linha Nova 1"]

    assert blocos[2].tipo == "adicionado"
    assert blocos[2].texto == "Linha Adicionada"

    assert blocos[3].tipo == "removido"
    assert blocos[3].texto == "Linha Removida"


def test_hino_comparativo_get_parsed_diff_empty():
    comp = HinoComparativo(
        id=2,
        numero_novo="11",
        numero_antigo=None,
        titulo_novo="Inedito",
        titulo_antigo=None,
        status_comparacao="NOVO_INEDITO",
        diff_json=None,
    )
    stats, blocos = comp.get_parsed_diff()
    assert stats is None
    assert blocos == []

