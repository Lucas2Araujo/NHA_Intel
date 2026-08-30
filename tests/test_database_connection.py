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
