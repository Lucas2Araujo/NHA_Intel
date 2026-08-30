import pytest_asyncio

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
        CREATE TABLE tema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT
        );
    """)

    await conn.execute("""
        CREATE TABLE hino_tema (
            hino_id INTEGER,
            tema_id INTEGER,
            PRIMARY KEY(hino_id, tema_id),
            FOREIGN KEY(hino_id) REFERENCES hino(id),
            FOREIGN KEY(tema_id) REFERENCES tema(id)
        );
    """)

    await conn.execute("""
        CREATE TABLE texto_biblico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referencia TEXT
        );
    """)

    await conn.execute("""
        CREATE TABLE hino_texto (
            hino_id INTEGER,
            texto_id INTEGER,
            PRIMARY KEY(hino_id, texto_id),
            FOREIGN KEY(hino_id) REFERENCES hino(id),
            FOREIGN KEY(texto_id) REFERENCES texto_biblico(id)
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
        INSERT INTO hino (id, numero, titulo, letra, categoria, subcategoria, texto_base) VALUES (?, ?, ?, ?, ?, ?, ?);
    """,
        [
            (
                1,
                "1",
                "Santo, Santo, Santo!",
                "Santo, Santo, Santo! Deus Omnipotente!",
                "Adoração",
                "Louvor",
                "Apocalipse 4:8",
            ),
            (
                2,
                "2",
                "Ó Adorai o Senhor",
                "Ó adorai o Senhor na beleza da sua santidade.",
                "Adoração",
                "Louvor",
                "Salmo 29:2",
            ),
            (
                3,
                "3",
                "O Deus Eterno Reina",
                "O Deus eterno reina, revestiu-se de majestade.",
                "Adoração",
                "Majestade",
                "Salmo 93:1",
            ),
        ],
    )

    # Inserção de temas sintéticos
    await conn.executemany(
        "INSERT INTO tema (id, nome) VALUES (?, ?);",
        [
            (1, "Adoração"),
            (2, "Santidade"),
            (3, "Majestade"),
        ],
    )

    # Associação hino-tema
    await conn.executemany(
        "INSERT INTO hino_tema (hino_id, tema_id) VALUES (?, ?);",
        [
            (1, 1),
            (1, 2),  # Hino 1 -> Adoração, Santidade
            (2, 1),  # Hino 2 -> Adoração
            (3, 1),
            (3, 3),  # Hino 3 -> Adoração, Majestade
        ],
    )

    # Inserção de textos bíblicos sintéticos
    await conn.executemany(
        "INSERT INTO texto_biblico (id, referencia) VALUES (?, ?);",
        [
            (1, "Apocalipse 4:8"),
            (2, "Salmo 29:2"),
        ],
    )

    # Associação hino-texto
    await conn.executemany(
        "INSERT INTO hino_texto (hino_id, texto_id) VALUES (?, ?);",
        [
            (1, 1),  # Hino 1 -> Apocalipse 4:8
            (2, 2),  # Hino 2 -> Salmo 29:2
        ],
    )

    await conn.commit()

    yield db_conn

    await db_conn.close()
