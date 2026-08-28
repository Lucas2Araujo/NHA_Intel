"""
Testes unitários e assíncronos para o serviço de atualização UpdaterService e componentes de interface.
Cobertura completa: detecção de ABI, seleção de APK, integridade SHA-256, download atômico, cache e UI.
"""

import json
import asyncio
import hashlib
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from src.services.updater_service import (
    UpdaterService,
    ABI_ARM64,
    ABI_ARMV7,
    ABI_X86_64,
    ABI_X86,
    ABI_UNIVERSAL,
)
from src.views.update_dialog import show_update_dialog, trigger_apk_installation, open_in_browser
import flet as ft


def test_updater_version_parsing():
    """Testa a conversão de strings de versão em tuplas numéricas."""
    assert UpdaterService.parse_version_tuple("0.5.0") == (0, 5, 0)
    assert UpdaterService.parse_version_tuple("v0.6.1") == (0, 6, 1)
    assert UpdaterService.parse_version_tuple("V1.0.0") == (1, 0, 0)
    assert UpdaterService.parse_version_tuple("1.2") == (1, 2, 0)
    assert UpdaterService.parse_version_tuple("v0.5.0-beta") == (0, 5, 0)
    assert UpdaterService.parse_version_tuple("v0.6.0-rc1") == (0, 6, 0)
    assert UpdaterService.parse_version_tuple("") == (0, 0, 0)


def test_updater_is_newer_version():
    """Testa a comparação de precedência de versão."""
    assert UpdaterService.is_newer_version("0.6.0", "0.5.0") is True
    assert UpdaterService.is_newer_version("v1.0.0", "0.9.9") is True
    assert UpdaterService.is_newer_version("0.5.1", "0.5.0") is True
    assert UpdaterService.is_newer_version("0.5.0", "0.5.0") is False
    assert UpdaterService.is_newer_version("0.4.9", "0.5.0") is False
    assert UpdaterService.is_newer_version("v0.5.0", "0.5.0") is False


def test_device_architecture_detection():
    """Testa a normalização e detecção de arquiteturas de CPU Android."""
    assert UpdaterService._normalize_abi("aarch64") == ABI_ARM64
    assert UpdaterService._normalize_abi("arm64-v8a") == ABI_ARM64
    assert UpdaterService._normalize_abi("armv8") == ABI_ARM64
    assert UpdaterService._normalize_abi("armv7l") == ABI_ARMV7
    assert UpdaterService._normalize_abi("armeabi-v7a") == ABI_ARMV7
    assert UpdaterService._normalize_abi("x86_64") == ABI_X86_64
    assert UpdaterService._normalize_abi("amd64") == ABI_X86_64
    assert UpdaterService._normalize_abi("i686") == ABI_X86

    # Teste de rótulo formatado
    assert "ARM64" in UpdaterService.format_architecture_label(ABI_ARM64)
    assert "ARMv7" in UpdaterService.format_architecture_label(ABI_ARMV7)
    assert "x86_64" in UpdaterService.format_architecture_label(ABI_X86_64)


def test_select_best_apk_asset_multi_arch():
    """Testa seleção de APK ideal com base na arquitetura do dispositivo."""
    assets = [
        {"name": "hinario-v0.6.0-armeabi-v7a.apk", "browser_download_url": "https://example.com/armv7.apk", "size": 15000000},
        {"name": "hinario-v0.6.0-arm64-v8a.apk", "browser_download_url": "https://example.com/arm64.apk", "size": 16000000},
        {"name": "hinario-v0.6.0-x86_64.apk", "browser_download_url": "https://example.com/x86_64.apk", "size": 17000000},
        {"name": "checksums.txt", "browser_download_url": "https://example.com/checksums.txt", "size": 256},
    ]

    # Para dispositivo ARM64
    best_arm64 = UpdaterService.select_best_apk_asset(assets, current_arch=ABI_ARM64)
    assert best_arm64 is not None
    assert best_arm64["name"] == "hinario-v0.6.0-arm64-v8a.apk"

    # Para dispositivo ARMv7
    best_armv7 = UpdaterService.select_best_apk_asset(assets, current_arch=ABI_ARMV7)
    assert best_armv7 is not None
    assert best_armv7["name"] == "hinario-v0.6.0-armeabi-v7a.apk"

    # Para dispositivo x86_64
    best_x86 = UpdaterService.select_best_apk_asset(assets, current_arch=ABI_X86_64)
    assert best_x86 is not None
    assert best_x86["name"] == "hinario-v0.6.0-x86_64.apk"


def test_select_best_apk_asset_universal_fallback():
    """Testa fallback para APK universal quando não há binário específico."""
    assets = [
        {"name": "hinario-v0.6.0-universal.apk", "browser_download_url": "https://example.com/universal.apk", "size": 25000000},
        {"name": "notes.txt", "browser_download_url": "https://example.com/notes.txt", "size": 100},
    ]

    best = UpdaterService.select_best_apk_asset(assets, current_arch=ABI_ARM64)
    assert best is not None
    assert best["name"] == "hinario-v0.6.0-universal.apk"


def test_sha256_calculation_and_extraction(tmp_path: Path):
    """Testa cálculo de SHA-256 e extração a partir de arquivo de checksums / notas."""
    content = b"Conteudo de teste para hash SHA256"
    expected_hash = hashlib.sha256(content).hexdigest()

    test_file = tmp_path / "app.apk"
    test_file.write_bytes(content)

    calculated = UpdaterService.calculate_sha256(test_file)
    assert calculated == expected_hash

    # Extração de checksums.txt
    checksums_txt = f"{expected_hash}  app.apk\ne3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  other.apk"
    extracted = UpdaterService.extract_expected_sha256("app.apk", "", checksums_txt)
    assert extracted == expected_hash

    # Extração das notas de release
    release_body = f"Release v0.6.0\nSHA256: {expected_hash}\nNovidades..."
    extracted_body = UpdaterService.extract_expected_sha256("app.apk", release_body, None)
    assert extracted_body == expected_hash


@pytest.mark.asyncio
async def test_check_for_updates_available_with_arch_selection():
    """Testa detecção bem-sucedida de atualização disponível com asset .apk para arm64."""
    service = UpdaterService(repo_owner="Lucas2Araujo", repo_name="NHA_Intel")

    mock_release_payload = {
        "tag_name": "v0.6.0",
        "body": "## Novidades da Versão 0.6.0\n- Modo escuro aprimorado\n- Download automático",
        "published_at": "2026-08-23T20:00:00Z",
        "html_url": "https://github.com/Lucas2Araujo/NHA_Intel/releases/tag/v0.6.0",
        "assets": [
            {
                "name": "hinario_v0.6.0_armeabi-v7a.apk",
                "browser_download_url": "https://github.com/Lucas2Araujo/NHA_Intel/releases/download/v0.6.0/hinario_v0.6.0_armv7.apk",
                "size": 14000000,
            },
            {
                "name": "hinario_v0.6.0_arm64-v8a.apk",
                "browser_download_url": "https://github.com/Lucas2Araujo/NHA_Intel/releases/download/v0.6.0/hinario_v0.6.0_arm64.apk",
                "size": 15728640,
            },
            {
                "name": "checksums.txt",
                "browser_download_url": "https://github.com/Lucas2Araujo/NHA_Intel/releases/download/v0.6.0/checksums.txt",
                "size": 128,
            },
        ],
    }

    with patch.object(service, "_fetch_latest_release_sync", return_value=mock_release_payload), \
         patch.object(service, "_fetch_checksums_sync", return_value="a" * 64 + "  hinario_v0.6.0_arm64-v8a.apk"):
        result = await service.check_for_updates(current_version="0.5.0", target_arch="arm64-v8a")

        assert result["update_available"] is True
        assert result["latest_version"] == "0.6.0"
        assert result["current_version"] == "0.5.0"
        assert result["download_url"] == "https://github.com/Lucas2Araujo/NHA_Intel/releases/download/v0.6.0/hinario_v0.6.0_arm64.apk"
        assert result["asset_name"] == "hinario_v0.6.0_arm64-v8a.apk"
        assert result["asset_size"] == 15728640
        assert result["expected_sha256"] == "a" * 64
        assert result["error"] is None


@pytest.mark.asyncio
async def test_check_for_updates_cache():
    """Testa que chamadas subsequentes utilizam o cache em memória dentro do TTL."""
    service = UpdaterService(cache_ttl_seconds=600)
    mock_payload = {
        "tag_name": "v0.6.0",
        "body": "Notas",
        "assets": [{"name": "app.apk", "browser_download_url": "https://example.com/app.apk", "size": 1000}],
    }

    with patch.object(service, "_fetch_latest_release_sync", return_value=mock_payload) as mock_fetch:
        res1 = await service.check_for_updates(current_version="0.5.0")
        assert res1["update_available"] is True
        assert mock_fetch.call_count == 1

        # Segunda chamada deve vir do cache (call_count permanece 1)
        res2 = await service.check_for_updates(current_version="0.5.0")
        assert res2["update_available"] is True
        assert mock_fetch.call_count == 1

        # Chamada com force_refresh=True deve refazer a requisição
        res3 = await service.check_for_updates(current_version="0.5.0", force_refresh=True)
        assert res3["update_available"] is True
        assert mock_fetch.call_count == 2


@pytest.mark.asyncio
async def test_check_for_updates_rate_limit_error():
    """Testa tratamento amigável de HTTP 403 (Rate Limit)."""
    import urllib.error
    service = UpdaterService()

    with patch.object(
        service,
        "_fetch_latest_release_sync",
        side_effect=urllib.error.HTTPError(
            "url", 403, "Forbidden", {}, None
        ),
    ):
        result = await service.check_for_updates(current_version="0.5.0", force_refresh=True)
        assert result["update_available"] is False
        assert "Limite de requisições" in result["error"]


@pytest.mark.asyncio
async def test_download_apk_atomic_and_integrity_success(tmp_path: Path):
    """Testa download atômico com validação bem-sucedida de SHA-256 e tamanho."""
    service = UpdaterService()
    fake_apk_content = b"PK\x03\x04" + b"A" * 1024
    expected_sha256 = hashlib.sha256(fake_apk_content).hexdigest()

    mock_response = MagicMock()
    mock_response.headers = {"Content-Length": str(len(fake_apk_content))}
    mock_response.read.side_effect = [fake_apk_content, b""]
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        target_dir = str(tmp_path)
        saved_file = await service.download_apk(
            download_url="https://example.com/test.apk",
            target_dir=target_dir,
            filename="app_test.apk",
            expected_size=len(fake_apk_content),
            expected_sha256=expected_sha256,
        )

        assert Path(saved_file).exists()
        assert Path(saved_file).read_bytes() == fake_apk_content
        # Garante que o arquivo .tmp foi removido/renomeado
        assert not (tmp_path / "app_test.apk.tmp").exists()


@pytest.mark.asyncio
async def test_download_apk_sha256_mismatch_fails_and_cleans_up(tmp_path: Path):
    """Testa falha de integridade SHA-256 com limpeza do arquivo temporário."""
    service = UpdaterService()
    fake_apk_content = b"PK\x03\x04" + b"A" * 1024

    mock_response = MagicMock()
    mock_response.headers = {"Content-Length": str(len(fake_apk_content))}
    mock_response.read.side_effect = [fake_apk_content, b""]
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        target_dir = str(tmp_path)
        with pytest.raises(ValueError, match="Falha de integridade SHA-256"):
            await service.download_apk(
                download_url="https://example.com/test.apk",
                target_dir=target_dir,
                filename="corrupt_app.apk",
                expected_sha256="0" * 64,  # Hash incorreto
            )

        # Garante que nenhum arquivo corrompido ou .tmp sobrou no disco
        assert not (tmp_path / "corrupt_app.apk").exists()
        assert not (tmp_path / "corrupt_app.apk.tmp").exists()


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
        "release_notes": "## Correções e melhorias\n- Item 1",
        "detected_arch": "arm64-v8a",
        "asset_size": 15000000,
    }

    show_update_dialog(page, update_info, service)
    page.show_dialog.assert_called_once()
    dialog = page.show_dialog.call_args[0][0]
    assert isinstance(dialog, ft.AlertDialog)

    # Teste de disparo de instalação
    test_apk = tmp_path / "test.apk"
    test_apk.write_bytes(b"dummy apk")

    page.launch_url = AsyncMock()
    await trigger_apk_installation(page, str(test_apk), "https://example.com/update.apk")
    page.launch_url.assert_called_once_with(f"file://{test_apk.resolve()}")


@pytest.mark.asyncio
async def test_open_in_browser():
    """Testa função utilitária para abrir URL no navegador."""
    page = MagicMock(spec=ft.Page)
    page.launch_url = AsyncMock()

    await open_in_browser(page, "https://github.com/Lucas2Araujo/NHA_Intel")
    page.launch_url.assert_called_once_with("https://github.com/Lucas2Araujo/NHA_Intel")


