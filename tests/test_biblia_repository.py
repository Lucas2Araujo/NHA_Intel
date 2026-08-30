import pytest

from src.database.connection import DatabaseConnection
from src.repositories.biblia_repository import BibliaRepository


@pytest.mark.asyncio
async def test_biblia_repository_parse_referencia():
    repo = BibliaRepository()

    # 1. Versículo único
    p1 = repo.parse_referencia("João 3:16")
    assert p1 is not None
    assert p1["book_id"] == 43
    assert p1["chapter"] == 3
    assert p1["verses"] == [16]

    # 2. Intervalo de versículos
    p2 = repo.parse_referencia("Salmos 23:1-6")
    assert p2 is not None
    assert p2["book_id"] == 19
    assert p2["chapter"] == 23
    assert p2["verses"] == [1, 2, 3, 4, 5, 6]

    # 3. Capítulo completo
    p3 = repo.parse_referencia("Gênesis 1")
    assert p3 is not None
    assert p3["book_id"] == 1
    assert p3["chapter"] == 1
    assert p3["verses"] is None

    # 4. Versículos separados por vírgula
    p4 = repo.parse_referencia("Salmo 9:1, 2")
    assert p4 is not None
    assert p4["book_id"] == 19
    assert p4["chapter"] == 9
    assert p4["verses"] == [1, 2]

    # 5. Numeral romano
    p5 = repo.parse_referencia("I Pedro 1:3-5")
    assert p5 is not None
    assert p5["book_id"] == 60
    assert p5["chapter"] == 1
    assert p5["verses"] == [3, 4, 5]

    # 6. Livro de capítulo único
    p6 = repo.parse_referencia("Judas 24, 25")
    assert p6 is not None
    assert p6["book_id"] == 65
    assert p6["chapter"] == 1
    assert p6["verses"] == [24, 25]

    # 7. Prefixo com scraping anomaly
    p7 = repo.parse_referencia("And God SaidGênesis 2:1-3")
    assert p7 is not None
    assert p7["book_id"] == 1
    assert p7["chapter"] == 2
    assert p7["verses"] == [1, 2, 3]

    # 8. Outro livro com prefixo ordinal
    p8 = repo.parse_referencia("1 Coríntios 13:4-7")
    assert p8 is not None
    assert p8["book_id"] == 46
    assert p8["chapter"] == 13
    assert p8["verses"] == [4, 5, 6, 7]

    # 9. Inválidos
    assert repo.parse_referencia("") is None
    assert repo.parse_referencia("TextoInvalido 99:99") is None


@pytest.mark.asyncio
async def test_biblia_repository_buscar_passagem_in_memory():
    db_conn = DatabaseConnection(db_path=":memory:", read_only=True)
    conn = await db_conn.get_connection()

    # Cria tabelas sintéticas
    await conn.execute("""
        CREATE TABLE book (
            id INTEGER PRIMARY KEY,
            book_reference_id INTEGER,
            testament_reference_id INTEGER,
            name VARCHAR(50)
        );
    """)
    await conn.execute("""
        CREATE TABLE verse (
            id INTEGER PRIMARY KEY,
            book_id INTEGER,
            chapter INTEGER,
            verse INTEGER,
            text TEXT
        );
    """)

    await conn.executemany(
        "INSERT INTO book (id, book_reference_id, testament_reference_id, name) VALUES (?, ?, ?, ?);",
        [
            (19, 19, 1, "Salmos"),
            (43, 43, 2, "João"),
        ],
    )

    await conn.executemany(
        "INSERT INTO verse (id, book_id, chapter, verse, text) VALUES (?, ?, ?, ?, ?);",
        [
            (1, 43, 3, 16, "Porque Deus amou ao mundo de tal maneira..."),
            (2, 19, 23, 1, "O SENHOR é o meu pastor; nada me faltará."),
            (3, 19, 23, 2, "Ele me faz repousar em pastos verdejantes."),
        ],
    )
    await conn.commit()

    repo = BibliaRepository(db_conn)

    # Busca versículo único
    passagem = await repo.buscar_passagem("João 3:16")
    assert passagem is not None
    assert passagem.referencia == "João 3:16"
    assert len(passagem.versiculos) == 1
    assert passagem.versiculos[0].texto == "Porque Deus amou ao mundo de tal maneira..."
    assert "16. Porque Deus amou ao mundo" in passagem.texto_formatado

    # Busca múltiplos versículos
    passagem2 = await repo.buscar_passagem("Salmos 23:1-2")
    assert passagem2 is not None
    assert passagem2.referencia == "Salmos 23:1-2"
    assert len(passagem2.versiculos) == 2

    # Busca versículo inexistente
    passagem3 = await repo.buscar_passagem("João 3:99")
    assert passagem3 is None

    # Busca referência com erro de sintaxe
    passagem4 = await repo.buscar_passagem("LivroInexistente 1:1")
    assert passagem4 is None

    await db_conn.close()


@pytest.mark.asyncio
async def test_biblia_repository_real_database():
    """Testa a leitura direta do arquivo ARA.sqlite se existente."""
    db_conn = DatabaseConnection(db_path="ARA.sqlite", read_only=True)
    repo = BibliaRepository(db_conn)

    passagem = await repo.buscar_passagem("João 3:16")
    if passagem is not None:
        assert passagem.livro == "João"
        assert passagem.capitulo == 3
        assert len(passagem.versiculos) == 1
        assert "Deus amou ao mundo" in passagem.versiculos[0].texto

    await db_conn.close()


@pytest.mark.asyncio
async def test_biblia_cache_lifecycle():
    db_conn = DatabaseConnection(db_path=":memory:", read_only=True)
    conn = await db_conn.get_connection()
    await conn.execute("CREATE TABLE book (id INTEGER PRIMARY KEY, name VARCHAR(50));")
    await conn.execute(
        "CREATE TABLE verse (id INTEGER PRIMARY KEY, book_id INTEGER, chapter INTEGER, verse INTEGER, text TEXT);"
    )
    await conn.execute("INSERT INTO book VALUES (43, 'João');")
    await conn.execute(
        "INSERT INTO verse VALUES (1, 43, 3, 16, 'Porque Deus amou o mundo');"
    )
    await conn.commit()

    repo = BibliaRepository(db_conn)
    p1 = await repo.buscar_passagem("João 3:16")
    assert p1 is not None
    assert "ARA:João 3:16" in repo._passagem_cache
    assert await repo.buscar_passagem("João 3:16") is p1

    repo.clear_cache()
    assert len(repo._passagem_cache) == 0
    assert len(repo._book_names) == 0
    await repo.close()


@pytest.mark.asyncio
async def test_biblia_multi_version_discovery_and_query():
    versions = BibliaRepository.get_available_versions()
    assert isinstance(versions, list)
    assert len(versions) >= 1
    assert "ARA" in versions
    assert versions[0] == "ARA"

    # Testa chaveamento e fallback
    db_conn_ara = DatabaseConnection(db_path=":memory:", read_only=True)
    conn_ara = await db_conn_ara.get_connection()
    await conn_ara.execute(
        "CREATE TABLE book (id INTEGER PRIMARY KEY, name VARCHAR(50));"
    )
    await conn_ara.execute(
        "CREATE TABLE verse (id INTEGER PRIMARY KEY, book_id INTEGER, chapter INTEGER, verse INTEGER, text TEXT);"
    )
    await conn_ara.execute("INSERT INTO book VALUES (43, 'João');")
    await conn_ara.execute(
        "INSERT INTO verse VALUES (1, 43, 3, 16, 'Texto ARA: Porque Deus amou o mundo');"
    )
    await conn_ara.commit()

    db_conn_nvi = DatabaseConnection(db_path=":memory:", read_only=True)
    conn_nvi = await db_conn_nvi.get_connection()
    await conn_nvi.execute(
        "CREATE TABLE book (id INTEGER PRIMARY KEY, name VARCHAR(50));"
    )
    await conn_nvi.execute(
        "CREATE TABLE verse (id INTEGER PRIMARY KEY, book_id INTEGER, chapter INTEGER, verse INTEGER, text TEXT);"
    )
    await conn_nvi.execute("INSERT INTO book VALUES (43, 'João');")
    await conn_nvi.execute(
        "INSERT INTO verse VALUES (1, 43, 3, 16, 'Texto NVI: Porque Deus tanto amou o mundo');"
    )
    await conn_nvi.commit()

    repo = BibliaRepository(db_conn_ara, default_version="ARA")
    repo._connections["NVI"] = db_conn_nvi

    # Busca padrão ARA
    p_ara = await repo.buscar_passagem("João 3:16")
    assert p_ara is not None
    assert "Texto ARA" in p_ara.versiculos[0].texto

    # Busca específica NVI
    p_nvi = await repo.buscar_passagem("João 3:16", versao="NVI")
    assert p_nvi is not None
    assert "Texto NVI" in p_nvi.versiculos[0].texto

    # Chaveamento de versão padrão
    repo.set_version("NVI")
    assert repo.active_version == "NVI"
    p_nvi_active = await repo.buscar_passagem("João 3:16")
    assert p_nvi_active is not None
    assert "Texto NVI" in p_nvi_active.versiculos[0].texto

    await repo.close()


@pytest.mark.asyncio
async def test_biblia_version_names_and_descriptions():
    assert BibliaRepository.get_version_name("ARA") == "Almeida Revista e Atualizada"
    assert BibliaRepository.get_version_name("NVI") == "Nova Versão Internacional"
    assert (
        BibliaRepository.get_version_name("NTLH")
        == "Nova Tradução na Linguagem de Hoje"
    )
    assert BibliaRepository.get_version_name("KJA") == "King James Atualizada"
    assert BibliaRepository.get_version_name("AS21") == "Almeida Século 21"
    assert BibliaRepository.get_version_name("DESCONHECIDA") == "DESCONHECIDA"

    version_tuples = BibliaRepository.get_available_versions_with_names()
    assert isinstance(version_tuples, list)
    assert len(version_tuples) >= 1
    assert version_tuples[0][0] == "ARA"
    assert version_tuples[0][1] == "Almeida Revista e Atualizada"


@pytest.mark.asyncio
async def test_biblia_buscar_capitulo_completo():
    db_conn = DatabaseConnection(db_path=":memory:", read_only=True)
    conn = await db_conn.get_connection()
    await conn.execute("CREATE TABLE book (id INTEGER PRIMARY KEY, name VARCHAR(50));")
    await conn.execute(
        "CREATE TABLE verse (id INTEGER PRIMARY KEY, book_id INTEGER, chapter INTEGER, verse INTEGER, text TEXT);"
    )
    await conn.execute("INSERT INTO book VALUES (19, 'Salmos');")
    await conn.executemany(
        "INSERT INTO verse VALUES (?, 19, 23, ?, ?);",
        [
            (1, 1, "O SENHOR é o meu pastor; nada me faltará."),
            (2, 2, "Ele me faz repousar em pastos verdejantes."),
            (3, 3, "Refrigera a minha alma."),
            (4, 4, "Ainda que eu ande pelo vale da sombra da morte..."),
            (5, 5, "Preparas uma mesa perante mim..."),
            (6, 6, "Certamente que a bondade e a misericórdia me seguirão..."),
        ],
    )
    await conn.commit()

    repo = BibliaRepository(db_conn)

    # Busca a partir de um versículo ou intervalo, mas solicita o capítulo completo
    passagem = await repo.buscar_capitulo_completo("Salmos 23:1-2")
    assert passagem is not None
    assert passagem.referencia == "Salmos 23"
    assert len(passagem.versiculos) == 6
    assert passagem.versiculos[0].numero == 1
    assert passagem.versiculos[-1].numero == 6
    assert "bondade e a misericórdia" in passagem.versiculos[-1].texto

    # Referência vazia ou inválida
    assert await repo.buscar_capitulo_completo("") is None
    assert await repo.buscar_capitulo_completo("Invalido 99:99") is None

    await repo.close()
