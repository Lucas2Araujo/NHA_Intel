import asyncio
import gzip
import inspect
import json
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

import anyio
import httpx

logger = logging.getLogger(__name__)

MANIFEST_FILENAME: str = "manifest.json"
DEFAULT_MANIFEST_URL = (
    "https://raw.githubusercontent.com/Lucas2Araujo/biblias/main/manifest.json"
)

# Mapeamento padrão caso o manifesto ainda não esteja carregado
DEFAULT_MODULE_EXTENSIONS: dict[str, str] = {
    "hinario": ".db",
    "hinario_antigo": ".db",
    "hinario_comparativo": ".db",
}

BIBLE_MODULE_IDS: set[str] = {
    "ACF",
    "ARA",
    "ARC",
    "AS21",
    "JFAA",
    "KJA",
    "KJF",
    "NAA",
    "NBV",
    "NTLH",
    "NVI",
    "NVT",
    "TB",
}


def _save_manifest_cache_sync(cache_file: Path, data: dict[str, Any]) -> None:
    """Grava o manifesto no cache local em disco em formato JSON."""
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class ContentManager:
    """
    Gerenciador assíncrono responsável pelo ciclo de vida de módulos on-demand (Bíblias e Hinários).
    - Localização e criação do diretório gravável de módulos
    - Busca e cache local do manifest.json
    - Download em streaming com barra de progresso
    - Descompactação gzip (.gz -> .sqlite/.db)
    - Verificação de status de instalação e exclusão de módulos
    - Atualização no client_storage do Flet
    """

    def __init__(
        self,
        modules_dir: Path | str | None = None,
        manifest_url: str = DEFAULT_MANIFEST_URL,
    ):
        self._custom_modules_dir = Path(modules_dir) if modules_dir else None
        self.manifest_url = manifest_url
        self._manifest_cache: dict[str, Any] | None = None
        self._active_downloads: dict[str, asyncio.Event] = {}

    @staticmethod
    def _get_android_storage_dir() -> Path | None:
        """Tenta resolver o diretório de módulos em ambiente Android."""
        for env_var in ["FLET_APP_STORAGE_DATA", "FILES_DIR", "ANDROID_PRIVATE"]:
            val = os.environ.get(env_var)
            if val:
                p = Path(val) / "modules"
                try:
                    p.mkdir(parents=True, exist_ok=True)
                    if os.access(p, os.W_OK):
                        return p
                except Exception:
                    pass
        return None

    @staticmethod
    def _get_desktop_modules_dir() -> Path | None:
        """Determina o diretório padrão de dados da aplicação em sistemas Desktop."""
        try:
            if sys.platform.startswith("win"):
                base = Path(os.environ.get("APPDATA", Path.home()))
                p = base / "HinarioApp" / "modules"
            elif sys.platform == "darwin":
                p = Path.home() / "Library" / "Application Support" / "HinarioApp" / "modules"
            else:
                home = Path.home()
                if str(home) == "/data" or not os.access(home, os.W_OK):
                    base = Path(tempfile.gettempdir())
                else:
                    base = Path(
                        os.environ.get("XDG_DATA_HOME", home / ".local" / "share")
                    )
                p = base / "hinario_app" / "modules"

            p.mkdir(parents=True, exist_ok=True)
            if os.access(p, os.W_OK):
                return p
        except Exception:
            pass
        return None

    @classmethod
    def get_modules_dir(cls, custom_dir: Path | str | None = None) -> Path:
        """
        Determina o diretório gravável seguro para armazenar os módulos baixados.
        Compatível com Android (serious_python/Flet), Desktop (Linux, Windows, macOS) e testes.
        """
        if custom_dir:
            p = Path(custom_dir)
            p.mkdir(parents=True, exist_ok=True)
            return p

        # 1. Variável de ambiente explícita
        env_dir = os.environ.get("HINARIO_MODULES_DIR")
        if env_dir:
            p = Path(env_dir)
            p.mkdir(parents=True, exist_ok=True)
            return p

        # 2. Variáveis de ambiente Android / Flet
        android_dir = cls._get_android_storage_dir()
        if android_dir:
            return android_dir

        # 3. Diretório de usuário padrão da plataforma (Desktop)
        desktop_dir = cls._get_desktop_modules_dir()
        if desktop_dir:
            return desktop_dir

        # 4. Fallback no diretório temporário
        p = Path(tempfile.gettempdir()) / "hinario_app" / "modules"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def modules_dir(self) -> Path:
        """Retorna o diretório de módulos desta instância."""
        return self.get_modules_dir(self._custom_modules_dir)

    def _find_bundled_manifest(self) -> Path | None:
        """Procura o manifest.json embutido nos assets ou na raiz do projeto."""
        module_dir = Path(__file__).resolve().parent
        candidates = [
            self.modules_dir / MANIFEST_FILENAME,
            module_dir.parent.parent / "assets" / MANIFEST_FILENAME,
            module_dir.parent.parent / MANIFEST_FILENAME,
            module_dir.parent / "assets" / MANIFEST_FILENAME,
            Path.cwd() / "assets" / MANIFEST_FILENAME,
            Path.cwd() / MANIFEST_FILENAME,
        ]
        for c in candidates:
            if c.exists() and c.is_file() and c.stat().st_size > 0:
                return c.resolve()
        return None

    def _read_cached_or_bundled_manifest(self) -> dict[str, Any] | None:
        """Lê o manifesto do cache local em disco ou do arquivo embutido."""
        manifest_path = self._find_bundled_manifest()
        if manifest_path:
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning(f"Erro ao ler manifesto local {manifest_path}: {exc}")
        return None

    async def get_manifest(self, force_refresh: bool = False) -> dict[str, Any]:
        """
        Obtém o manifesto de módulos, buscando da URL remota via httpx
        com fallback automático para o cache local em disco ou asset embutido.
        """
        if not force_refresh and self._manifest_cache:
            return self._manifest_cache

        remote_data: dict[str, Any] | None = None
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(self.manifest_url)
                if response.status_code == 200:
                    remote_data = response.json()
        except Exception as exc:
            logger.debug(f"Falha ao buscar manifesto remoto ({self.manifest_url}): {exc}")

        if remote_data and isinstance(remote_data, dict) and "modules" in remote_data:
            self._manifest_cache = remote_data
            try:
                cache_file = self.modules_dir / MANIFEST_FILENAME
                await asyncio.to_thread(_save_manifest_cache_sync, cache_file, remote_data)
            except Exception as e:
                logger.warning(f"Não foi possível salvar cache do manifesto: {e}")
            return remote_data

        # Fallback para cache local / arquivo embutido
        local_data = self._read_cached_or_bundled_manifest()
        if local_data:
            self._manifest_cache = local_data
            return local_data

        return {"version": 1, "modules": []}

    def get_module_target_filename(self, module_info_or_id: dict[str, Any] | str) -> str:
        """Retorna o nome do arquivo descompactado correspondente ao módulo (.sqlite ou .db)."""
        if isinstance(module_info_or_id, dict):
            file_name = module_info_or_id.get("file", "")
            if file_name.endswith(".gz"):
                return file_name[:-3]
            if file_name:
                return file_name
            mod_id = module_info_or_id.get("id", "")
        else:
            mod_id = module_info_or_id

        ext = DEFAULT_MODULE_EXTENSIONS.get(mod_id, ".sqlite")
        return f"{mod_id}{ext}"

    def get_module_path(self, module_id: str) -> Path | None:
        """
        Retorna o Path do arquivo do módulo caso esteja instalado no diretório gravável,
        ou None caso não esteja presente.
        """
        target_name = self.get_module_target_filename(module_id)
        target_path = self.modules_dir / target_name
        if target_path.exists() and target_path.stat().st_size > 0:
            return target_path

        # Verifica também se está em subpasta 'biblias'
        alt_path = self.modules_dir / "biblias" / target_name
        if alt_path.exists() and alt_path.stat().st_size > 0:
            return alt_path

        return None

    def is_module_installed(self, module_id: str) -> bool:
        """Verifica se o módulo correspondente está instalado e não corrompido (tamanho > 0)."""
        return self.get_module_path(module_id) is not None

    def has_any_bible_installed(self) -> bool:
        """Informa se ao menos uma versão completa da Bíblia está instalada localmente."""
        return len(self.get_installed_bible_ids()) > 0

    def get_installed_bible_ids(self) -> list[str]:
        """Retorna a lista de IDs das Bíblias completas instaladas localmente."""
        installed = []
        for bid in sorted(BIBLE_MODULE_IDS):
            if self.is_module_installed(bid):
                installed.append(bid)
        return installed

    async def _report_progress(
        self, callback: Callable[[float], Any] | None, val: float
    ) -> None:
        """Executa callback de progresso suportando funções síncronas e corrotinas."""
        if not callback:
            return
        try:
            if inspect.iscoroutinefunction(callback):
                await callback(val)
            else:
                res = callback(val)
                if asyncio.iscoroutine(res):
                    await res
        except Exception:
            pass

    async def _stream_chunks_to_file(
        self,
        response: httpx.Response,
        tmp_gz_path: Path,
        expected_size: int,
        cancel_event: asyncio.Event,
        mod_id: str,
        on_progress: Callable[[float], Any] | None,
    ) -> None:
        """Grava os chunks HTTP baixados no arquivo temporário assincronamente com cálculo de progresso."""
        downloaded_bytes = 0
        async with await anyio.open_file(tmp_gz_path, "wb") as f_tmp:
            async for chunk in response.aiter_bytes(chunk_size=65536):
                if cancel_event.is_set():
                    raise asyncio.CancelledError(
                        f"Download de {mod_id} cancelado pelo usuário."
                    )
                await f_tmp.write(chunk)
                downloaded_bytes += len(chunk)
                if expected_size > 0:
                    ratio = min(0.95, (downloaded_bytes / expected_size) * 0.95)
                    await self._report_progress(on_progress, ratio)

    @staticmethod
    async def _update_client_storage_installed(
        page: Any | None, mod_id: str, installed: bool
    ) -> None:
        """Atualiza a flag de instalação do módulo no client_storage do Flet."""
        if not page or not hasattr(page, "client_storage") or not page.client_storage:
            return
        key = f"module_{mod_id}_installed"
        try:
            await page.client_storage.set_async(key, installed)
        except Exception:
            try:
                page.client_storage.set(key, installed)
            except Exception:
                pass

    async def download_module(
        self,
        module_info: dict[str, Any],
        on_progress: Callable[[float], Any] | None = None,
        page: Any | None = None,
    ) -> Path:
        """
        Baixa o módulo via streaming HTTP com httpx, salva como arquivo temporário .tmp.gz,
        reporta progresso via on_progress(float), descompacta via gzip nativo para o formato
        final (.sqlite ou .db) e atualiza o client_storage.
        """
        mod_id = module_info.get("id", "unknown")
        url = module_info.get("url")
        if not url:
            raise ValueError(f"URL de download ausente para o módulo {mod_id}")

        final_filename = self.get_module_target_filename(module_info)
        target_path = self.modules_dir / final_filename
        tmp_gz_path = self.modules_dir / f"{final_filename}.tmp.gz"

        cancel_event = asyncio.Event()
        self._active_downloads[mod_id] = cancel_event

        expected_size = int(module_info.get("size_bytes") or 0)
        await self._report_progress(on_progress, 0.0)

        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    total_header = response.headers.get("content-length")
                    if total_header and total_header.isdigit():
                        expected_size = int(total_header)

                    await self._stream_chunks_to_file(
                        response, tmp_gz_path, expected_size, cancel_event, mod_id, on_progress
                    )

            # Notifica descompactação e descompacta em thread
            await self._report_progress(on_progress, 0.96)
            await asyncio.to_thread(self._decompress_gzip, tmp_gz_path, target_path)

            if tmp_gz_path.exists():
                try:
                    tmp_gz_path.unlink()
                except OSError:
                    pass

            await self._update_client_storage_installed(page, mod_id, True)
            await self._report_progress(on_progress, 1.0)
            return target_path

        except Exception:
            if tmp_gz_path.exists():
                try:
                    tmp_gz_path.unlink()
                except OSError:
                    pass
            raise
        finally:
            self._active_downloads.pop(mod_id, None)

    @staticmethod
    def _decompress_gzip(src_gz: Path, dest_file: Path) -> None:
        """Descompacta um arquivo .gz para o destino final em blocos seguros de memória."""
        temp_dest = Path(f"{dest_file}.extracting")
        with gzip.open(src_gz, "rb") as f_in, open(temp_dest, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out, length=131072)
        if dest_file.exists():
            dest_file.unlink()
        temp_dest.rename(dest_file)

    def cancel_download(self, module_id: str) -> bool:
        """Sinaliza cancelamento para um download ativo."""
        if module_id in self._active_downloads:
            self._active_downloads[module_id].set()
            return True
        return False

    @staticmethod
    def _remove_sqlite_files(target_path: Path) -> None:
        """Remove o arquivo de banco de dados SQLite e quaisquer arquivos auxiliares (-wal, -shm, -journal)."""
        for ext in ["-wal", "-shm", "-journal"]:
            aux = Path(f"{target_path}{ext}")
            if aux.exists():
                try:
                    aux.unlink()
                except OSError:
                    pass
        if target_path.exists():
            target_path.unlink()

    async def delete_module(self, module_id: str, page: Any | None = None) -> bool:
        """
        Exclui o arquivo do módulo correspondente e quaisquer arquivos auxiliares SQLite (-wal, -shm).
        Atualiza o client_storage.
        """
        target_path = self.get_module_path(module_id)
        if not target_path or not target_path.exists():
            return False

        try:
            self._remove_sqlite_files(target_path)
            await self._update_client_storage_installed(page, module_id, False)
            return True
        except Exception:
            logger.exception("Erro ao excluir módulo %s", module_id)
            raise

