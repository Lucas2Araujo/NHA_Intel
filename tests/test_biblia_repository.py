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
    assert "João 3:16" in repo._passagem_cache
    assert await repo.buscar_passagem("João 3:16") is p1

    repo.clear_cache()
    assert len(repo._passagem_cache) == 0
    assert len(repo._book_names) == 0
    await db_conn.close()
