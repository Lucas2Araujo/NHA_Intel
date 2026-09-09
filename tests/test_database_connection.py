import os

import pytest

from src.database.connection import DatabaseConnection
from src.repositories.hino_repository import HinoRepository


def test_resolve_db_path_memory():
    """Valida que :memory: é mantido inalterado."""
    db_conn = DatabaseConnection(db_path=":memory:")
    assert db_conn.db_path == ":memory:"


def test_resolve_db_path_default():
    """Valida que o caminho padrão resolve para o arquivo em disco existente."""
    db_conn = DatabaseConnection()
    assert db_conn.db_path.endswith("hinario.db")
    assert os.path.isabs(db_conn.db_path)
    assert os.path.exists(db_conn.db_path)


def test_resolve_db_path_env_variable(monkeypatch, tmp_path):
    """Valida que variável de ambiente de banco tem prioridade se o arquivo existir."""
    dummy_db = tmp_path / "env_hinario.db"
    dummy_db.write_text("dummy content")

    monkeypatch.setenv("HINARIO_DB_PATH", str(dummy_db))
    resolved = DatabaseConnection._resolve_db_path("hinario.db")
    assert resolved == str(dummy_db)


def test_resolve_db_path_android_copy(monkeypatch, tmp_path):
    """Valida a cópia para o diretório gravável do usuário quando em ambiente Android."""
    files_dir = tmp_path / "android_files"
    files_dir.mkdir()

    monkeypatch.setenv("FILES_DIR", str(files_dir))
    monkeypatch.setenv("ANDROID_ARGUMENT", "1")

    resolved = DatabaseConnection._resolve_db_path("hinario.db")

    expected_file = files_dir / "hinario.db"
    assert resolved == str(expected_file)
    assert expected_file.exists()


@pytest.mark.asyncio
async def test_real_db_connection_and_hino_table():
    """Valida que a conexão com o banco real resolvida pelo DatabaseConnection encontra a tabela hino."""
    db_conn = DatabaseConnection()
    try:
        repo = HinoRepository(db_conn)
        hinos = await repo.get_all()
        assert isinstance(hinos, list)
        assert len(hinos) > 0
    finally:
        await db_conn.close()


@pytest.mark.asyncio
async def test_read_only_connection_does_not_initialize_tables():
    """Valida que bancos abertos com read_only=True não tentam criar tabelas nem FTS."""
    db_conn = DatabaseConnection(db_path=":memory:", read_only=True)
    try:
        conn = await db_conn.get_connection()
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ) as cursor:
            tables = [row[0] for row in await cursor.fetchall()]
        assert "hino_fts" not in tables
        assert "preferencias" not in tables
    finally:
        await db_conn.close()


@pytest.mark.asyncio
async def test_non_hymnal_db_does_not_create_hino_fts():
    """Valida que um banco sem tabela hino não cria hino_fts mesmo com read_only=False."""
    db_conn = DatabaseConnection(db_path=":memory:", read_only=False)
    try:
        conn = await db_conn.get_connection()
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ) as cursor:
            tables = [row[0] for row in await cursor.fetchall()]
        assert "hino_fts" not in tables
        assert "preferencias" in tables
    finally:
        await db_conn.close()


@pytest.mark.asyncio
async def test_busy_timeout_pragma_applied():
    """Valida que PRAGMA busy_timeout = 30000 foi aplicado com sucesso na conexão."""
    db_conn = DatabaseConnection(db_path=":memory:")
    try:
        conn = await db_conn.get_connection()
        async with conn.execute("PRAGMA busy_timeout;") as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == 30000
    finally:
        await db_conn.close()


@pytest.mark.asyncio
async def test_concurrent_get_connection():
    """Valida que múltiplas chamadas simultâneas a get_connection retornam com segurança a mesma conexão."""
    import asyncio

    db_conn = DatabaseConnection(db_path=":memory:")
    try:
        conns = await asyncio.gather(*[db_conn.get_connection() for _ in range(10)])
        assert len(conns) == 10
        # Todas as referências devem ser idênticas à mesma conexão
        for c in conns:
            assert c is conns[0]
    finally:
        await db_conn.close()
