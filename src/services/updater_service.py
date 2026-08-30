"""
Serviço de Verificação e Download de Atualizações Automáticas via GitHub Releases.
Focado no ecossistema Android com detecção de arquitetura de CPU (ARMv7, ARM64/v8, x86_64),
seleção inteligente de APK por ABI, validação de integridade SHA-256, download atômico,
cache em memória e integração com o instalador nativo do Android.
"""

import asyncio
import hashlib
import json
import os
import platform
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

try:
    from src.version import __version__ as APP_VERSION
except ImportError:
    APP_VERSION = "0.1.0"


# Mapeamento de ABIs padrão do Android
ABI_ARM64 = "arm64-v8a"
ABI_ARMV7 = "armeabi-v7a"
ABI_X86_64 = "x86_64"
ABI_X86 = "x86"
ABI_UNIVERSAL = "universal"


async def _run_sync_or_thread(func, *args, **kwargs):
    """Executa a função em thread ou síncrona se o ambiente não suportar threads (WebAssembly/Pyodide)."""
    try:
        return await asyncio.to_thread(func, *args, **kwargs)
    except (RuntimeError, NotImplementedError):
        return func(*args, **kwargs)


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
        cache_ttl_seconds: int = 600,
    ):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.timeout_seconds = timeout_seconds
        self.cache_ttl_seconds = cache_ttl_seconds

        # Cache em memória para mitigar rate-limit do GitHub (60 req/h sem token)
        self._cached_release_data: dict[str, Any] | None = None
        self._cache_timestamp: float = 0.0

    @staticmethod
    def get_device_architecture() -> str:
        """
        Detecta a arquitetura de CPU / ABI do dispositivo Android ou sistema atual.
        Retorna uma das strings canônicas: 'arm64-v8a', 'armeabi-v7a', 'x86_64', 'x86'.
        """
        # 1. Variável de ambiente explícita (para testes ou containers)
        env_abi = os.environ.get("ANDROID_CPU_ABI", "").strip().lower()
        if env_abi:
            return UpdaterService._normalize_abi(env_abi)

        # 2. Se estiver rodando em ambiente Android nativo, tenta obter via getprop
        try:
            getprop_result = subprocess.run(
                ["getprop", "ro.product.cpu.abi"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if getprop_result.returncode == 0:
                prop_abi = getprop_result.stdout.strip().lower()
                if prop_abi:
                    return UpdaterService._normalize_abi(prop_abi)
        except Exception:
            pass

        # 3. Inspeciona a máquina via platform / os.uname
        machine = platform.machine().lower()
        return UpdaterService._normalize_abi(machine)

    @staticmethod
    def _normalize_abi(arch_str: str) -> str:
        """Normaliza aliases de arquitetura para a nomenclatura padrão Android."""
        arch = arch_str.lower().strip()
        if any(
            token in arch for token in ("arm64", "aarch64", "armv8", "armv8l", "armv8b")
        ):
            return ABI_ARM64
        elif any(
            token in arch
            for token in (
                "armv7",
                "armv7l",
                "armv7b",
                "armv7a",
                "armeabi-v7a",
                "armeabi",
                "arm32",
                "arm",
            )
        ):
            return ABI_ARMV7
        elif any(token in arch for token in ("x86_64", "x86-64", "amd64", "x64")):
            return ABI_X86_64
        elif any(token in arch for token in ("i386", "i686", "x86")):
            return ABI_X86
        return arch or ABI_ARM64

    @staticmethod
    def format_architecture_label(abi: str) -> str:
        """Retorna um rótulo amigável para exibição na UI."""
        normalized = UpdaterService._normalize_abi(abi)
        if normalized == ABI_ARM64:
            return "ARM64 (64-bit)"
        elif normalized == ABI_ARMV7:
            return "ARMv7 (32-bit)"
        elif normalized == ABI_X86_64:
            return "x86_64 (64-bit)"
        elif normalized == ABI_X86:
            return "x86 (32-bit)"
        elif normalized == ABI_UNIVERSAL:
            return "Universal"
        return abi.upper()

    @classmethod
    def select_best_apk_asset(
        cls, assets: list[dict[str, Any]], current_arch: str | None = None
    ) -> dict[str, Any] | None:
        """
        Analisa a lista de assets da release e seleciona o melhor APK correspondente
        à arquitetura de CPU do dispositivo.

        Prioridades:
        1. Match exato com a arquitetura detectada (ex: arm64-v8a).
        2. APK Universal (se houver).
        3. Fallback compatível (ex: arm64 aceita armeabi-v7a como compatibilidade).
        4. Primeiro APK encontrado se for o único disponível.
        """
        if not assets:
            return None

        apk_assets = [a for a in assets if a.get("name", "").lower().endswith(".apk")]
        if not apk_assets:
            return None

        if len(apk_assets) == 1:
            return apk_assets[0]

        target_abi = cls._normalize_abi(current_arch or cls.get_device_architecture())

        def score_asset(asset: dict[str, Any]) -> int:
            name = asset.get("name", "").lower()
            # Mapeamento de termos de busca por arquitetura
            is_arm64_asset = any(t in name for t in ("arm64", "aarch64", "armv8"))
            is_armv7_asset = any(t in name for t in ("armv7", "armeabi", "arm32")) or (
                "arm" in name and not is_arm64_asset
            )
            is_x86_64_asset = any(
                t in name for t in ("x86_64", "x86-64", "amd64", "x64")
            )
            is_x86_asset = "x86" in name and not is_x86_64_asset
            is_universal = any(t in name for t in ("universal", "fat", "all")) or (
                not is_arm64_asset
                and not is_armv7_asset
                and not is_x86_64_asset
                and not is_x86_asset
            )

            if target_abi == ABI_ARM64:
                if is_arm64_asset:
                    return 100
                elif is_universal:
                    return 60
                elif is_armv7_asset:
                    return 30
                return 0

            elif target_abi == ABI_ARMV7:
                if is_armv7_asset:
                    return 100
                elif is_universal:
                    return 60
                return 0  # ARMv7 não roda ARM64 nem x86

            elif target_abi == ABI_X86_64:
                if is_x86_64_asset:
                    return 100
                elif is_universal:
                    return 60
                elif is_x86_asset:
                    return 30
                return 0

            elif target_abi == ABI_X86:
                if is_x86_asset:
                    return 100
                elif is_universal:
                    return 60
                return 0

            return 50 if is_universal else 10

        best_asset = max(apk_assets, key=score_asset)
        return best_asset

    @staticmethod
    def parse_version_tuple(version_str: str) -> tuple[int, ...]:
        """
        Converte uma string de versão (ex: 'v0.5.0', '0.6.1', '1.0.0-rc1')
        em uma tupla de inteiros para comparação numérica consistente.
        """
        if not version_str:
            return (0, 0, 0)
        clean = version_str.strip().lstrip("vV")
        # Separa a parte numérica principal de sufixos de pré-lançamento
        main_ver = clean.split("-")[0].split("+")[0]
        parts = main_ver.split(".")
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
        return cls.parse_version_tuple(latest_version) > cls.parse_version_tuple(
            current_version
        )

    @staticmethod
    def calculate_sha256(file_path: Path) -> str:
        """Calcula o hash SHA-256 de um arquivo local."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(64 * 1024), b""):
                sha256.update(chunk)
        return sha256.hexdigest().lower()

    @staticmethod
    def extract_expected_sha256(
        asset_name: str, release_body: str, checksums_content: str | None = None
    ) -> str | None:
        """
        Tenta extrair o hash SHA-256 esperado para o asset a partir do arquivo de checksums
        ou das notas de lançamento (release body).
        """
        if not asset_name:
            return None

        # 1. Procura no arquivo de checksums (formato: "<hash>  <filename>" ou "<hash> *<filename>")
        if checksums_content:
            for line in checksums_content.splitlines():
                clean_line = line.strip()
                if asset_name.lower() in clean_line.lower():
                    match = re.search(r"\b([a-fA-F0-9]{64})\b", clean_line)
                    if match:
                        return match.group(1).lower()

        # 2. Procura nas notas de lançamento (ex: "SHA256: <hash>" ou "<asset_name>: <hash>")
        if release_body:
            # Procura por menção direta ao arquivo e seu hash
            pattern = rf"{re.escape(asset_name)}.*?\b([a-fA-F0-9]{{64}})\b"
            match = re.search(pattern, release_body, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).lower()
            # Procura por padrão genérico "sha256: <hash>"
            generic_match = re.search(
                r"sha256\s*[:=]\s*([a-fA-F0-9]{64})", release_body, re.IGNORECASE
            )
            if generic_match:
                return generic_match.group(1).lower()

        return None

    def _fetch_latest_release_sync(self, current_ver: str) -> dict[str, Any]:
        """Executa a requisição GET síncrona na API do GitHub com headers apropriados."""
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
        headers = {
            "User-Agent": f"HinarioInteligente/{current_ver}",
            "Accept": "application/vnd.github.v3+json",
        }
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
            if response.status != 200:
                raise urllib.error.HTTPError(
                    url,
                    response.status,
                    f"HTTP Error {response.status}",
                    response.headers,
                    None,
                )
            data = json.loads(response.read().decode("utf-8"))
            return data

    def _fetch_checksums_sync(self, checksum_url: str) -> str:
        """Baixa o conteúdo em texto do arquivo de checksums da release."""
        headers = {"User-Agent": "HinarioInteligente/Updater"}
        req = urllib.request.Request(checksum_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
            return response.read().decode("utf-8", errors="ignore")

    async def check_for_updates(
        self,
        current_version: str | None = None,
        force_refresh: bool = False,
        target_arch: str | None = None,
    ) -> dict[str, Any]:
        """
        Consulta a API do GitHub Releases para verificar se há uma nova versão disponível.
        Usa cache em memória para evitar atingir o limite de 60 req/hora do GitHub.

        Args:
            current_version: Versão atual do aplicativo (ex: '0.5.0').
            force_refresh: Se True, ignora o cache em memória e faz nova requisição.
            target_arch: Arquitetura alvo para seleção de APK (se None, detecta automaticamente).

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
                - expected_sha256: Optional[str]
                - detected_arch: str
                - html_url: Optional[str]
                - error: Optional[str]
        """
        cur_ver = current_version or APP_VERSION
        current_arch = target_arch or self.get_device_architecture()
        now = time.time()

        try:
            # 1. Verifica cache em memória
            if (
                not force_refresh
                and self._cached_release_data is not None
                and (now - self._cache_timestamp) < self.cache_ttl_seconds
            ):
                data = self._cached_release_data
            else:
                data = await _run_sync_or_thread(
                    self._fetch_latest_release_sync, cur_ver
                )
                self._cached_release_data = data
                self._cache_timestamp = now

            tag_name = data.get("tag_name", "").strip()
            clean_tag = tag_name.lstrip("vV")
            body = data.get("body", "") or ""
            published_at = data.get("published_at")
            html_url = data.get("html_url")

            assets = data.get("assets", [])

            # 2. Seleciona o melhor APK correspondente à arquitetura do dispositivo
            best_apk = self.select_best_apk_asset(assets, current_arch)

            download_url = None
            asset_name = None
            asset_size = None

            if best_apk:
                download_url = best_apk.get("browser_download_url")
                asset_name = best_apk.get("name")
                asset_size = best_apk.get("size")

            # Se não houver asset APK publicado, usa o link direto da release no GitHub
            if not download_url:
                download_url = html_url

            # 3. Procura por arquivo de checksums entre os assets
            checksums_content = None
            for asset in assets:
                name_low = asset.get("name", "").lower()
                if any(
                    name_low.endswith(ext)
                    for ext in (
                        "checksums.txt",
                        "sha256sums",
                        "sha256sums.txt",
                        ".sha256",
                        "hashes.txt",
                    )
                ):
                    chk_url = asset.get("browser_download_url")
                    if chk_url:
                        try:
                            checksums_content = await _run_sync_or_thread(
                                self._fetch_checksums_sync, chk_url
                            )
                        except Exception:
                            checksums_content = None
                        break

            expected_sha256 = self.extract_expected_sha256(
                asset_name or "", body, checksums_content
            )

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
                "expected_sha256": expected_sha256,
                "detected_arch": current_arch,
                "html_url": html_url,
                "error": None,
            }

        except urllib.error.HTTPError as e:
            if e.code == 403:
                error_msg = (
                    "Limite de requisições da API do GitHub atingido (HTTP 403). "
                    "Tente novamente em alguns minutos ou acesse a página de releases."
                )
            elif e.code == 404:
                error_msg = (
                    "Nenhuma versão publicada encontrada no repositório (HTTP 404)."
                )
            else:
                error_msg = f"Erro no GitHub (HTTP {e.code}): {e.reason}"

            return {
                "update_available": False,
                "latest_version": cur_ver,
                "current_version": cur_ver,
                "download_url": None,
                "release_notes": "",
                "published_at": None,
                "asset_name": None,
                "asset_size": None,
                "expected_sha256": None,
                "detected_arch": current_arch,
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
                "expected_sha256": None,
                "detected_arch": current_arch,
                "html_url": None,
                "error": str(e),
            }

    def _download_apk_sync(
        self,
        download_url: str,
        target_path: Path,
        on_progress: Callable[[float, int, int], None] | None = None,
        expected_size: int | None = None,
        expected_sha256: str | None = None,
    ) -> str:
        """
        Executa o download com streaming síncrono, gravação atômica (.tmp) e validação de integridade.
        """
        temp_file = target_path.with_suffix(target_path.suffix + ".tmp")
        headers = {"User-Agent": "HinarioInteligente/Updater"}
        req = urllib.request.Request(download_url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size_header = response.headers.get("Content-Length")
                total_size = (
                    int(total_size_header)
                    if total_size_header and total_size_header.isdigit()
                    else (expected_size or 0)
                )

                downloaded = 0
                chunk_size = 64 * 1024  # 64 KB por bloco

                with open(temp_file, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if on_progress and total_size > 0:
                            progress = min(1.0, downloaded / total_size)
                            on_progress(progress, downloaded, total_size)

            # 1. Validação de tamanho final (se fornecido)
            if total_size > 0 and downloaded < total_size:
                if temp_file.exists():
                    temp_file.unlink()
                raise ValueError(
                    f"Download incompleto: recebidos {downloaded} bytes de {total_size} esperados."
                )

            # 2. Validação de Hash SHA-256 (se fornecido)
            if expected_sha256:
                actual_sha256 = self.calculate_sha256(temp_file)
                if actual_sha256.lower() != expected_sha256.lower():
                    if temp_file.exists():
                        temp_file.unlink()
                    raise ValueError(
                        f"Falha de integridade SHA-256: obtido '{actual_sha256}', esperado '{expected_sha256}'."
                    )

            # 3. Renomeação atômica
            if target_path.exists():
                target_path.unlink()
            temp_file.rename(target_path)
            return str(target_path.resolve())

        except Exception:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            raise

    async def download_apk(
        self,
        download_url: str,
        on_progress: Callable[[float, int, int], None] | None = None,
        target_dir: str | None = None,
        filename: str | None = None,
        expected_size: int | None = None,
        expected_sha256: str | None = None,
    ) -> str:
        """
        Baixa o arquivo de atualização (.apk) de forma assíncrona com validação de integridade.

        Args:
            download_url: URL direta do download do asset APK.
            on_progress: Callback opcional recebendo (progress_ratio, bytes_baixados, total_bytes).
            target_dir: Diretório de destino (se None, utiliza a pasta temporária do SO).
            filename: Nome do arquivo (se None, extrai da URL ou usa 'Hinario_Update.apk').
            expected_size: Tamanho esperado em bytes para validação.
            expected_sha256: Hash SHA-256 esperado para validação.

        Returns:
            Caminho absoluto do arquivo APK baixado e validado.
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

        saved_path = await _run_sync_or_thread(
            self._download_apk_sync,
            download_url,
            target_path,
            thread_progress,
            expected_size,
            expected_sha256,
        )
        return saved_path
