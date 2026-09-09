import asyncio
import gzip
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.content_manager import ContentManager


@pytest.fixture
def temp_modules_dir(tmp_path):
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()
    return modules_dir


@pytest.mark.asyncio
async def test_content_manager_modules_dir(temp_modules_dir):
    manager = ContentManager(modules_dir=temp_modules_dir)
    assert manager.modules_dir == temp_modules_dir
    assert manager.modules_dir.exists()


@pytest.mark.asyncio
async def test_content_manager_manifest_fallback(temp_modules_dir):
    # Cria manifest.json no diretório de módulos
    sample_manifest = {
        "version": 1,
        "modules": [
            {
                "id": "ARA",
                "file": "ARA.sqlite.gz",
                "size_bytes": 1736290,
                "url": "https://example.com/ARA.sqlite.gz",
            }
        ],
    }
    with open(temp_modules_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(sample_manifest, f)

    manager = ContentManager(
        modules_dir=temp_modules_dir,
        manifest_url="https://invalid-non-existent-url.local/manifest.json",
    )
    manifest = await manager.get_manifest()
    assert manifest["version"] == 1
    assert len(manifest["modules"]) == 1
    assert manifest["modules"][0]["id"] == "ARA"


@pytest.mark.asyncio
async def test_content_manager_manifest_remote_fetch(temp_modules_dir):
    remote_manifest = {
        "version": 2,
        "modules": [
            {
                "id": "NVI",
                "file": "NVI.sqlite.gz",
                "size_bytes": 1757483,
                "url": "https://example.com/NVI.sqlite.gz",
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = remote_manifest

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get = AsyncMock(return_value=mock_resp)

    manager = ContentManager(modules_dir=temp_modules_dir)

    with patch("httpx.AsyncClient", return_value=mock_client):
        manifest = await manager.get_manifest(force_refresh=True)
        assert manifest["version"] == 2
        assert manifest["modules"][0]["id"] == "NVI"

        # Verifica se o cache em disco foi salvo
        cache_file = temp_modules_dir / "manifest.json"
        assert cache_file.exists()
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["version"] == 2


def test_content_manager_target_filename(temp_modules_dir):
    manager = ContentManager(modules_dir=temp_modules_dir)
    assert manager.get_module_target_filename({"id": "ARA", "file": "ARA.sqlite.gz"}) == "ARA.sqlite"
    assert manager.get_module_target_filename({"id": "hinario_antigo", "file": "hinario_antigo.db.gz"}) == "hinario_antigo.db"
    assert manager.get_module_target_filename("NVI") == "NVI.sqlite"
    assert manager.get_module_target_filename("hinario_comparativo") == "hinario_comparativo.db"


def test_content_manager_is_installed(temp_modules_dir):
    manager = ContentManager(modules_dir=temp_modules_dir)

    assert manager.is_module_installed("ARA") is False
    assert manager.has_any_bible_installed() is False

    # Cria arquivo simulado
    test_db = temp_modules_dir / "ARA.sqlite"
    test_db.write_text("dummy database content")

    assert manager.is_module_installed("ARA") is True
    assert manager.has_any_bible_installed() is True
    assert "ARA" in manager.get_installed_bible_ids()


@pytest.mark.asyncio
async def test_content_manager_download_and_decompress(temp_modules_dir):
    # Cria conteúdo gzip em memória para simular o download
    raw_content = b"SQLITE_DATABASE_TEST_PAYLOAD"
    gz_content = gzip.compress(raw_content)

    async def fake_aiter_bytes(chunk_size=65536):
        yield gz_content

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {"content-length": str(len(gz_content))}
    mock_response.aiter_bytes = fake_aiter_bytes

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client

    class StreamContext:
        async def __aenter__(self):
            return mock_response

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    mock_client.stream = MagicMock(return_value=StreamContext())

    manager = ContentManager(modules_dir=temp_modules_dir)

    progress_reports = []

    def on_progress(val):
        progress_reports.append(val)

    mock_page = MagicMock()
    mock_page.client_storage = MagicMock()
    mock_page.client_storage.set_async = AsyncMock()

    module_info = {
        "id": "ACF",
        "file": "ACF.sqlite.gz",
        "size_bytes": len(gz_content),
        "url": "https://example.com/ACF.sqlite.gz",
    }

    with patch("httpx.AsyncClient", return_value=mock_client):
        dest_path = await manager.download_module(
            module_info=module_info,
            on_progress=on_progress,
            page=mock_page,
        )

    assert dest_path.exists()
    assert dest_path.name == "ACF.sqlite"
    assert dest_path.read_bytes() == raw_content
    assert len(progress_reports) > 0
    assert progress_reports[-1] == 1.0

    # Verifica se client_storage foi atualizado
    mock_page.client_storage.set_async.assert_called_with("module_ACF_installed", True)

    # Verifica exclusão do módulo
    deleted = await manager.delete_module("ACF", page=mock_page)
    assert deleted is True
    assert not dest_path.exists()
    mock_page.client_storage.set_async.assert_called_with("module_ACF_installed", False)

