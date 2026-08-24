"""
Testes unitários e assíncronos para o serviço de atualização UpdaterService e componentes de interface.
"""

import json
import asyncio
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from src.services.updater_service import UpdaterService
from src.views.update_dialog import show_update_dialog, trigger_apk_installation
import flet as ft


def test_updater_version_parsing():
    """Testa a conversão de strings de versão em tuplas numéricas."""
    assert UpdaterService.parse_version_tuple("0.5.0") == (0, 5, 0)
    assert UpdaterService.parse_version_tuple("v0.6.1") == (0, 6, 1)
    assert UpdaterService.parse_version_tuple("V1.0.0") == (1, 0, 0)
    assert UpdaterService.parse_version_tuple("1.2") == (1, 2, 0)
    assert UpdaterService.parse_version_tuple("v0.5.0-beta") == (0, 5, 0)
    assert UpdaterService.parse_version_tuple("") == (0, 0, 0)


def test_updater_is_newer_version():
    """Testa a comparação de precedência de versão."""
    assert UpdaterService.is_newer_version("0.6.0", "0.5.0") is True
    assert UpdaterService.is_newer_version("v1.0.0", "0.9.9") is True
    assert UpdaterService.is_newer_version("0.5.1", "0.5.0") is True
    assert UpdaterService.is_newer_version("0.5.0", "0.5.0") is False
    assert UpdaterService.is_newer_version("0.4.9", "0.5.0") is False
    assert UpdaterService.is_newer_version("v0.5.0", "0.5.0") is False


@pytest.mark.asyncio
async def test_check_for_updates_available():
    """Testa detecção bem-sucedida de atualização disponível com asset .apk."""
    service = UpdaterService(repo_owner="Lucas2Araujo", repo_name="NHA_Intel")

    mock_release_payload = {
        "tag_name": "v0.6.0",
        "body": "## Novidades da Versão 0.6.0\n- Modo escuro aprimorado\n- Download automático",
        "published_at": "2026-08-23T20:00:00Z",
        "html_url": "https://github.com/Lucas2Araujo/NHA_Intel/releases/tag/v0.6.0",
        "assets": [
            {
                "name": "hinario_v0.6.0.apk",
                "browser_download_url": "https://github.com/Lucas2Araujo/NHA_Intel/releases/download/v0.6.0/hinario_v0.6.0.apk",
                "size": 15728640,
            },
            {
                "name": "checksums.txt",
                "browser_download_url": "https://github.com/Lucas2Araujo/NHA_Intel/releases/download/v0.6.0/checksums.txt",
                "size": 128,
            },
        ],
    }

    with patch.object(service, "_fetch_latest_release_sync", return_value=mock_release_payload):
        result = await service.check_for_updates(current_version="0.5.0")

        assert result["update_available"] is True
        assert result["latest_version"] == "0.6.0"
        assert result["current_version"] == "0.5.0"
        assert result["download_url"] == "https://github.com/Lucas2Araujo/NHA_Intel/releases/download/v0.6.0/hinario_v0.6.0.apk"
        assert "Novidades da Versão 0.6.0" in result["release_notes"]
        assert result["asset_name"] == "hinario_v0.6.0.apk"
        assert result["asset_size"] == 15728640
        assert result["error"] is None


@pytest.mark.asyncio
async def test_check_for_updates_no_update_needed():
    """Testa quando o aplicativo já está na versão mais recente."""
    service = UpdaterService(repo_owner="Lucas2Araujo", repo_name="NHA_Intel")

    mock_release_payload = {
        "tag_name": "v0.5.0",
        "body": "Versão estável",
        "published_at": "2026-08-20T00:00:00Z",
        "html_url": "https://github.com/Lucas2Araujo/NHA_Intel/releases/tag/v0.5.0",
        "assets": [],
    }

    with patch.object(service, "_fetch_latest_release_sync", return_value=mock_release_payload):
        result = await service.check_for_updates(current_version="0.5.0")

        assert result["update_available"] is False
        assert result["latest_version"] == "0.5.0"
        assert result["download_url"] == "https://github.com/Lucas2Araujo/NHA_Intel/releases/tag/v0.5.0"
        assert result["error"] is None


@pytest.mark.asyncio
async def test_check_for_updates_network_error():
    """Testa tratamento gracioso de falhas de rede ou ausência de release."""
    import urllib.error
    service = UpdaterService()

    with patch.object(
        service,
        "_fetch_latest_release_sync",
        side_effect=urllib.error.HTTPError(
            "url", 404, "Not Found", {}, None
        ),
    ):
        result = await service.check_for_updates(current_version="0.5.0")
        assert result["update_available"] is False
        assert result["error"] is not None
        assert "HTTP 404" in result["error"]


@pytest.mark.asyncio
async def test_download_apk_with_progress(tmp_path: Path):
    """Testa download simulado de APK com registro de progresso."""
    service = UpdaterService()
    fake_apk_content = b"PK\x03\x04" + b"A" * 1024

    progress_records = []

    def on_progress(p, current, total):
        progress_records.append((p, current, total))

    mock_response = MagicMock()
    mock_response.headers = {"Content-Length": str(len(fake_apk_content))}
    mock_response.read.side_effect = [fake_apk_content, b""]
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        target_dir = str(tmp_path)
        saved_file = await service.download_apk(
            download_url="https://example.com/test.apk",
            on_progress=on_progress,
            target_dir=target_dir,
            filename="app_test.apk",
        )

        assert Path(saved_file).exists()
        assert Path(saved_file).read_bytes() == fake_apk_content
        await asyncio.sleep(0.05)
        assert len(progress_records) > 0
        assert progress_records[-1][0] == 1.0


@pytest.mark.asyncio
async def test_show_update_dialog_and_launch(tmp_path: Path):
    """Testa renderização do diálogo de atualização e gatilho de instalação."""
    page = MagicMock(spec=ft.Page)
    service = UpdaterService()

    update_info = {
        "update_available": True,
        "latest_version": "0.6.0",
        "current_version": "0.5.0",
        "download_url": "https://example.com/update.apk",
        "release_notes": "Correções e melhorias",
    }

    show_update_dialog(page, update_info, service)
    page.show_dialog.assert_called_once()
    dialog = page.show_dialog.call_args[0][0]
    assert isinstance(dialog, ft.AlertDialog)

    # Teste de disparo de instalação
    test_apk = tmp_path / "test.apk"
    test_apk.write_bytes(b"dummy apk")

    with patch("flet.UrlLauncher.launch_url", new_callable=AsyncMock) as mock_launch:
        await trigger_apk_installation(page, str(test_apk), "https://example.com/update.apk")
        mock_launch.assert_called_once_with(f"file://{test_apk.resolve()}")

