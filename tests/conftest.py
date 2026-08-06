import pytest_asyncio
import aiosqlite
from src.database.connection import DatabaseConnection


@pytest_asyncio.fixture
async def in_memory_db():
    """
    Fixture assíncrona que cria um banco de dados SQLite em memória usando aiosqlite
    com as tabelas 'hino', 'favorito', 'historico', 'lista_culto' e 'item_lista_culto' com dados sintéticos.
    """
    db_conn = DatabaseConnection(db_path=":memory:")
    conn = await db_conn.get_connection()

    # Criação das tabelas
    await conn.execute("""
        CREATE TABLE hino (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT,
            titulo TEXT,
            letra TEXT,
            autor_letra TEXT,
            autor_musica TEXT,
            texto_base TEXT,
            categoria TEXT,
            subcategoria TEXT,
            link_video TEXT
        );
    """)

    await conn.execute("""
        CREATE TABLE favorito (
            hino_id INTEGER PRIMARY KEY,
            data_favoritado DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(hino_id) REFERENCES hino(id)
        );
    """)

    await conn.execute("""
        CREATE TABLE historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hino_id INTEGER,
            data_acesso DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(hino_id) REFERENCES hino(id)
        );
    """)

    await conn.execute("""
        CREATE TABLE lista_culto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tema_gerador TEXT,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    await conn.execute("""
        CREATE TABLE item_lista_culto (
            lista_id INTEGER,
            hino_id INTEGER,
            ordem_execucao INTEGER,
            PRIMARY KEY(lista_id, hino_id),
            FOREIGN KEY(lista_id) REFERENCES lista_culto(id),
            FOREIGN KEY(hino_id) REFERENCES hino(id)
        );
    """)

    # Inserção de dados sintéticos para teste
    await conn.executemany(
        """
        INSERT INTO hino (id, numero, titulo, letra) VALUES (?, ?, ?, ?);
    """,
        [
            (1, "1", "Santo, Santo, Santo!", "Santo, Santo, Santo! Deus Omnipotente!"),
            (
                2,
                "2",
                "Ó Adorai o Senhor",
                "Ó adorai o Senhor na beleza da sua santidade.",
            ),
            (
                3,
                "3",
                "O Deus Eterno Reina",
                "O Deus eterno reina, revestiu-se de majestade.",
            ),
        ],
    )

    await conn.commit()

    yield db_conn

    await db_conn.close()
