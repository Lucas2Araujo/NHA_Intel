"""
Serviço de Verificação e Download de Atualizações Automáticas via GitHub Releases.
Suporta consultas assíncronas não-bloqueantes, parsing semver, download com progresso e
integração com instaladores nativos Android/Desktop.
"""

import os
import sys
import json
import re
import tempfile
import asyncio
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Tuple

try:
    from src.version import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = "0.5.0"


class UpdaterService:
    """
    Serviço assíncrono para verificação e download de novas versões
    do aplicativo Hinário Inteligente a partir da API de Releases do GitHub.
    """

    def __init__(
        self,
        repo_owner: str = "Lucas2Araujo",
        repo_name: str = "NHA_Intel",
        timeout_seconds: int = 10,
    ):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def parse_version_tuple(version_str: str) -> Tuple[int, ...]:
        """
        Converte uma string de versão (ex: 'v0.5.0', '0.6.1', '1.0.0-rc1')
        em uma tupla de inteiros para comparação numérica consistente.
        """
        if not version_str:
            return (0, 0, 0)
        clean = version_str.strip().lstrip("vV")
        parts = clean.split(".")
        numbers = []
        for part in parts:
            match = re.match(r"^(\d+)", part)
            if match:
                numbers.append(int(match.group(1)))
            else:
                numbers.append(0)
        while len(numbers) < 3:
            numbers.append(0)
        return tuple(numbers)

    @classmethod
    def is_newer_version(cls, latest_version: str, current_version: str) -> bool:
        """
        Retorna True se latest_version for estritamente mais recente que current_version.
        """
        return cls.parse_version_tuple(latest_version) > cls.parse_version_tuple(current_version)

    def _fetch_latest_release_sync(self, current_ver: str) -> Dict[str, Any]:
        """Executa a requisição GET síncrona na API do GitHub."""
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
        headers = {
            "User-Agent": f"HinarioInteligente/{current_ver}",
            "Accept": "application/vnd.github.v3+json",
        }
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
            if response.status != 200:
                raise urllib.error.HTTPError(
                    url, response.status, f"HTTP Error {response.status}", response.headers, None
                )
            data = json.loads(response.read().decode("utf-8"))
            return data

    async def check_for_updates(self, current_version: Optional[str] = None) -> Dict[str, Any]:
        """
        Consulta a API do GitHub Releases para verificar se há uma nova versão disponível.

        Retorna:
            dict com:
                - update_available: bool
                - latest_version: str
                - current_version: str
                - download_url: Optional[str] (URL do asset .apk ou link da release)
                - release_notes: str (corpo das notas de lançamento)
                - published_at: Optional[str]
                - asset_name: Optional[str]
                - asset_size: Optional[int]
                - error: Optional[str]
        """
        cur_ver = current_version or APP_VERSION

        try:
            data = await asyncio.to_thread(self._fetch_latest_release_sync, cur_ver)
            tag_name = data.get("tag_name", "").strip()
            clean_tag = tag_name.lstrip("vV")
            body = data.get("body", "") or ""
            published_at = data.get("published_at")
            html_url = data.get("html_url")

            assets = data.get("assets", [])
            download_url = None
            asset_name = None
            asset_size = None

            # Procura especificamente por um asset de extensão .apk
            for asset in assets:
                name = asset.get("name", "")
                if name.lower().endswith(".apk"):
                    download_url = asset.get("browser_download_url")
                    asset_name = name
                    asset_size = asset.get("size")
                    break

            # Se não encontrar arquivo APK nos assets, usa o link direto da release no GitHub
            if not download_url:
                download_url = html_url

            update_available = self.is_newer_version(clean_tag, cur_ver)

            return {
                "update_available": update_available,
                "latest_version": clean_tag,
                "current_version": cur_ver,
                "download_url": download_url,
                "release_notes": body,
                "published_at": published_at,
                "asset_name": asset_name,
                "asset_size": asset_size,
                "html_url": html_url,
                "error": None,
            }

        except urllib.error.HTTPError as e:
            # 404 significa que não há releases publicadas ainda no repositório
            error_msg = f"HTTP {e.code}: {e.reason}"
            return {
                "update_available": False,
                "latest_version": cur_ver,
                "current_version": cur_ver,
                "download_url": None,
                "release_notes": "",
                "published_at": None,
                "asset_name": None,
                "asset_size": None,
                "html_url": None,
                "error": error_msg,
            }
        except Exception as e:
            return {
                "update_available": False,
                "latest_version": cur_ver,
                "current_version": cur_ver,
                "download_url": None,
                "release_notes": "",
                "published_at": None,
                "asset_name": None,
                "asset_size": None,
                "html_url": None,
                "error": str(e),
            }

    def _download_apk_sync(
        self,
        download_url: str,
        target_path: Path,
        on_progress: Optional[Callable[[float, int, int], None]] = None,
    ) -> str:
        """Executa o download com streaming síncrono e reporte de progresso."""
        headers = {"User-Agent": "HinarioInteligente/Updater"}
        req = urllib.request.Request(download_url, headers=headers)

        with urllib.request.urlopen(req, timeout=30) as response:
            total_size_header = response.headers.get("Content-Length")
            total_size = int(total_size_header) if total_size_header and total_size_header.isdigit() else 0

            downloaded = 0
            chunk_size = 64 * 1024  # 64 KB por bloco

            with open(target_path, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress and total_size > 0:
                        progress = min(1.0, downloaded / total_size)
                        on_progress(progress, downloaded, total_size)

        return str(target_path.resolve())

    async def download_apk(
        self,
        download_url: str,
        on_progress: Optional[Callable[[float, int, int], None]] = None,
        target_dir: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> str:
        """
        Baixa o arquivo de atualização (.apk) de forma assíncrona.

        Args:
            download_url: URL direta do download do asset APK.
            on_progress: Callback opcional recebendo (progress_ratio, bytes_baixados, total_bytes).
            target_dir: Diretório de destino (se None, utiliza a pasta temporária do SO).
            filename: Nome do arquivo (se None, extrai da URL ou usa 'Hinario_Update.apk').

        Returns:
            Caminho absoluto do arquivo APK baixado.
        """
        if not target_dir:
            temp_dir = Path(tempfile.gettempdir()) / "hinario_updates"
        else:
            temp_dir = Path(target_dir)

        temp_dir.mkdir(parents=True, exist_ok=True)

        if not filename:
            parsed_name = os.path.basename(download_url.split("?")[0])
            if parsed_name and parsed_name.lower().endswith(".apk"):
                filename = parsed_name
            else:
                filename = "Hinario_Update.apk"

        target_path = temp_dir / filename

        loop = asyncio.get_running_loop()

        def thread_progress(progress: float, current: int, total: int):
            if on_progress:
                loop.call_soon_threadsafe(on_progress, progress, current, total)

        saved_path = await asyncio.to_thread(
            self._download_apk_sync, download_url, target_path, thread_progress
        )
        return saved_path

