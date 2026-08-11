import os
import re
import sys
import shutil
import asyncio
import subprocess
from typing import Optional, Dict, Any, Callable, List, cast
from urllib.parse import quote as url_quote

try:
    import yt_dlp
except ImportError:
    yt_dlp = None  # type: ignore


# Qualidade de vídeo
QUALITY_SD = "sd"
QUALITY_HD = "hd"

# Formatos do yt-dlp otimizados para Android (prioriza containers nativos mp4/m4a)
_YDL_FORMAT_AUDIO = "bestaudio[ext=m4a]/bestaudio/best"
_YDL_FORMAT_VIDEO_SD = (
    "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]"
    "/best[height<=480][ext=mp4]"
    "/best[height<=480]"
    "/best"
)
_YDL_FORMAT_VIDEO_HD = (
    "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
    "/best[height<=720][ext=mp4]"
    "/best[height<=720]"
    "/best"
)


def _resolve_download_root(download_dir: str) -> str:
    """Resolve o diretório raiz de downloads respeitando variáveis de ambiente Android/Flet."""
    if not os.path.isabs(download_dir):
        base = os.environ.get("FLET_APP_STORAGE_DATA") or os.environ.get("FILES_DIR")
        if base:
            download_dir = os.path.join(base, download_dir)
    try:
        os.makedirs(download_dir, exist_ok=True)
    except Exception:
        import tempfile
        download_dir = os.path.join(tempfile.gettempdir(), "hinario_downloads")
        os.makedirs(download_dir, exist_ok=True)
    return download_dir


def path_to_file_uri(filepath: str) -> str:
    """
    Converte um caminho absoluto do sistema de arquivos para uma URI ``file://`` 
    válida e compatível com Flutter/Android (Audio, Video).
    
    Exemplo:
        /data/user/0/app/files/downloads/audio/hino_1.mp3
        → file:///data/user/0/app/files/downloads/audio/hino_1.mp3
    """
    filepath = os.path.abspath(filepath)
    # No Windows, caminhos usam barras invertidas
    if sys.platform == "win32":
        filepath = filepath.replace("\\", "/")
    # url_quote preserva / e :
    return "file://" + url_quote(filepath, safe="/:")


class MediaService:
    """
    Serviço assíncrono seguro para gerenciamento completo de mídias do Hinário.

    Responsabilidades:
    - Download de áudio (MP3/M4A) via yt-dlp
    - Download de vídeo em SD (480p) e HD (720p / melhor disponível) via yt-dlp
    - Verificação de status de downloads por tipo e qualidade
    - Conversão de caminhos locais para URIs ``file://`` compatíveis com Flutter
    - Geração de URLs YouTube Embed para reprodução online via WebView
    - Reprodução de áudio local via subprocesso (desktop fallback)
    - Download em lote com callback de progresso e suporte a cancelamento
    """

    # ── Subdiretórios de mídia ────────────────────────────────────────
    AUDIO_SUBDIR = "audio"
    VIDEO_SD_SUBDIR = "video_sd"
    VIDEO_HD_SUBDIR = "video_hd"

    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = _resolve_download_root(download_dir)
        # Cria subdiretórios organizados
        for subdir in (self.AUDIO_SUBDIR, self.VIDEO_SD_SUBDIR, self.VIDEO_HD_SUBDIR):
            os.makedirs(os.path.join(self.download_dir, subdir), exist_ok=True)
        # Subprocesso de reprodução desktop (legacy)
        self.player_process: Optional[subprocess.Popen] = None

    # ── Sanitização ───────────────────────────────────────────────────

    def _sanitize_url(self, url: Optional[str]) -> str:
        """Sanitiza URLs para evitar injeção de parâmetros e comandos."""
        if not url:
            return ""
        url = url.strip()
        if not re.match(r"^https?://[^\s\"']+$", url, re.IGNORECASE):
            raise ValueError("URL de mídia inválida ou insegura.")
        return url

    # ── YouTube Helpers ───────────────────────────────────────────────

    def extract_youtube_id(self, url: Optional[str]) -> Optional[str]:
        """Extrai o ID do vídeo do YouTube de diversos formatos de URL."""
        if not url:
            return None
        match = re.search(r"(?:v=|\/|embed\/|shorts\/)([a-zA-Z0-9_-]{11})", url)
        return match.group(1) if match else None

    def get_embed_url(self, url: Optional[str]) -> Optional[str]:
        """Retorna a URL formatada para exibição do vídeo embutido (embed)."""
        video_id = self.extract_youtube_id(url)
        if video_id:
            return f"https://www.youtube.com/embed/{video_id}?autoplay=1"
        return url if url and url.startswith("http") else None

    # ── Caminhos de Arquivo Local ─────────────────────────────────────

    def get_local_filepath(self, hino_id: int) -> str:
        """Retorna o caminho do arquivo de áudio local baixado (compatibilidade)."""
        return self.get_local_audio_path(hino_id)

    def get_local_audio_path(self, hino_id: int) -> str:
        """Retorna o caminho do arquivo de áudio local (MP3 ou M4A)."""
        mp3 = os.path.join(self.download_dir, self.AUDIO_SUBDIR, f"hino_{hino_id}.mp3")
        if os.path.isfile(mp3):
            return mp3
        m4a = os.path.join(self.download_dir, self.AUDIO_SUBDIR, f"hino_{hino_id}.m4a")
        if os.path.isfile(m4a):
            return m4a
        # Compatibilidade: verifica na raiz antiga
        legacy = os.path.join(self.download_dir, f"hino_{hino_id}.mp3")
        if os.path.isfile(legacy):
            return legacy
        return mp3  # Retorna caminho mp3 padrão mesmo que não exista

    def get_local_video_path(self, hino_id: int, quality: str = QUALITY_SD) -> str:
        """Retorna o caminho do arquivo de vídeo local."""
        subdir = self.VIDEO_HD_SUBDIR if quality == QUALITY_HD else self.VIDEO_SD_SUBDIR
        return os.path.join(self.download_dir, subdir, f"hino_{hino_id}.mp4")

    # ── Verificação de Status de Download ─────────────────────────────

    def is_downloaded(self, hino_id: int) -> bool:
        """Verifica se o áudio do hino já foi baixado (compatibilidade)."""
        return self.is_audio_downloaded(hino_id)

    def is_audio_downloaded(self, hino_id: int) -> bool:
        """Verifica se o áudio do hino existe localmente."""
        path = self.get_local_audio_path(hino_id)
        return os.path.isfile(path)

    def is_video_downloaded(self, hino_id: int, quality: str = QUALITY_SD) -> bool:
        """Verifica se o vídeo do hino existe localmente na qualidade especificada."""
        path = self.get_local_video_path(hino_id, quality)
        return os.path.isfile(path)

    def get_download_status(self, hino_id: int) -> Dict[str, bool]:
        """Retorna o status completo de download de um hino."""
        return {
            "audio": self.is_audio_downloaded(hino_id),
            "video_sd": self.is_video_downloaded(hino_id, QUALITY_SD),
            "video_hd": self.is_video_downloaded(hino_id, QUALITY_HD),
        }

    # ── URIs file:// para Flutter ─────────────────────────────────────

    def get_audio_file_uri(self, hino_id: int) -> Optional[str]:
        """Retorna a URI file:// do áudio local, ou None se não baixado."""
        if not self.is_audio_downloaded(hino_id):
            return None
        return path_to_file_uri(self.get_local_audio_path(hino_id))

    def get_video_file_uri(self, hino_id: int, quality: str = QUALITY_SD) -> Optional[str]:
        """Retorna a URI file:// do vídeo local, ou None se não baixado."""
        if not self.is_video_downloaded(hino_id, quality):
            return None
        return path_to_file_uri(self.get_local_video_path(hino_id, quality))

    # ── Extração de Metadados (yt-dlp) ────────────────────────────────

    async def get_stream_url(self, video_url: Optional[str], is_video: bool = False) -> Optional[str]:
        """
        Retorna a URL direta de streaming usando yt-dlp.
        NOTA: URLs do YouTube expiram rapidamente e podem falhar com 403.
        Prefira get_embed_url() para reprodução online via WebView.
        """
        if not yt_dlp:
            return None
        sanitized_url = self._sanitize_url(video_url)
        if not sanitized_url:
            return None

        format_str = "best" if is_video else "bestaudio/best"
        ydl_opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "format": format_str,
        }

        def _extract():
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                info = ydl.extract_info(sanitized_url, download=False)
                return info.get("url")

        try:
            return await asyncio.to_thread(_extract)
        except Exception:
            return None

    async def get_info(self, video_url: Optional[str]) -> Optional[Dict[str, Any]]:
        """Extrai metadados do vídeo/áudio de forma assíncrona não-bloqueante."""
        if not yt_dlp:
            return None
        sanitized_url = self._sanitize_url(video_url)
        if not sanitized_url:
            return None

        ydl_opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "format": "bestaudio/best",
        }

        def _extract():
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                info = ydl.extract_info(sanitized_url, download=False)
                return {
                    "title": info.get("title"),
                    "duration": info.get("duration"),
                    "url": info.get("url"),
                    "thumbnail": info.get("thumbnail"),
                    "video_id": self.extract_youtube_id(sanitized_url),
                }

        try:
            return await asyncio.to_thread(_extract)
        except Exception:
            return None

    # ── Download de Áudio ─────────────────────────────────────────────

    async def download_audio(
        self,
        hino_id: int,
        video_url: Optional[str],
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> Optional[str]:
        """
        Realiza o download do áudio com fallback nativo sem FFmpeg obrigatório.
        
        Estratégia:
        1. Tenta FFmpegExtractAudio → MP3 192kbps (se FFmpeg disponível)
        2. Fallback: baixa áudio nativo (M4A/WebM) sem pós-processamento
        """
        if not yt_dlp:
            return None
        sanitized_url = self._sanitize_url(video_url)
        if not sanitized_url:
            return None

        audio_dir = os.path.join(self.download_dir, self.AUDIO_SUBDIR)
        output_template = os.path.join(audio_dir, f"hino_{hino_id}.%(ext)s")

        def _make_progress_hook(callback):
            def _hook(d):
                if callback and d.get("status") == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    downloaded = d.get("downloaded_bytes", 0)
                    if total > 0:
                        callback(downloaded / total)
            return _hook

        # Estratégia 1: FFmpeg MP3
        ydl_opts_mp3: Dict[str, Any] = {
            "format": _YDL_FORMAT_AUDIO,
            "outtmpl": output_template,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "quiet": True,
            "no_warnings": True,
        }
        if progress_callback:
            ydl_opts_mp3["progress_hooks"] = [_make_progress_hook(progress_callback)]

        def _download_mp3():
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts_mp3)) as ydl:
                ydl.download([sanitized_url])
            return self.get_local_audio_path(hino_id)

        try:
            result = await asyncio.to_thread(_download_mp3)
            if os.path.isfile(result):
                return result
        except Exception:
            pass

        # Estratégia 2: Download nativo (M4A sem pós-processamento)
        ydl_opts_native: Dict[str, Any] = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": os.path.join(audio_dir, f"hino_{hino_id}.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }
        if progress_callback:
            ydl_opts_native["progress_hooks"] = [_make_progress_hook(progress_callback)]

        def _download_native():
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts_native)) as ydl:
                ydl.download([sanitized_url])
            return self.get_local_audio_path(hino_id)

        try:
            result = await asyncio.to_thread(_download_native)
            if os.path.isfile(result):
                return result
        except Exception:
            pass

        return None

    # ── Download de Vídeo ─────────────────────────────────────────────

    async def download_video(
        self,
        hino_id: int,
        video_url: Optional[str],
        quality: str = QUALITY_SD,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> Optional[str]:
        """
        Realiza o download do vídeo em SD (480p) ou HD (720p / melhor disponível).
        Prioriza containers MP4 nativos para compatibilidade com Android.
        """
        if not yt_dlp:
            return None
        sanitized_url = self._sanitize_url(video_url)
        if not sanitized_url:
            return None

        subdir = self.VIDEO_HD_SUBDIR if quality == QUALITY_HD else self.VIDEO_SD_SUBDIR
        video_dir = os.path.join(self.download_dir, subdir)
        output_path = os.path.join(video_dir, f"hino_{hino_id}.mp4")
        output_template = os.path.join(video_dir, f"hino_{hino_id}.%(ext)s")

        format_str = _YDL_FORMAT_VIDEO_HD if quality == QUALITY_HD else _YDL_FORMAT_VIDEO_SD

        def _make_progress_hook(callback):
            def _hook(d):
                if callback and d.get("status") == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    downloaded = d.get("downloaded_bytes", 0)
                    if total > 0:
                        callback(downloaded / total)
            return _hook

        ydl_opts: Dict[str, Any] = {
            "format": format_str,
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
        }
        if progress_callback:
            ydl_opts["progress_hooks"] = [_make_progress_hook(progress_callback)]

        def _download():
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                ydl.download([sanitized_url])
            return output_path

        try:
            result = await asyncio.to_thread(_download)
            if os.path.isfile(result):
                return result
        except Exception:
            pass

        # Fallback: tenta formato genérico "best" como MP4
        ydl_opts_fallback: Dict[str, Any] = {
            "format": "best[ext=mp4]/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
        }
        if progress_callback:
            ydl_opts_fallback["progress_hooks"] = [_make_progress_hook(progress_callback)]

        def _download_fallback():
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts_fallback)) as ydl:
                ydl.download([sanitized_url])
            return output_path

        try:
            result = await asyncio.to_thread(_download_fallback)
            if os.path.isfile(result):
                return result
        except Exception:
            pass

        return None

    # ── Download em Lote (Batch) ──────────────────────────────────────

    async def download_library_batch(
        self,
        hino_list: List[Dict[str, Any]],
        media_type: str,
        quality: str = QUALITY_SD,
        progress_callback: Optional[Callable[[int, int, Optional[str]], None]] = None,
        cancel_event: Optional[asyncio.Event] = None,
    ) -> Dict[str, Any]:
        """
        Realiza o download em lote de uma lista de hinos.

        Args:
            hino_list: Lista de dicts com 'id' e 'link_video'.
            media_type: 'audio' ou 'video'.
            quality: 'sd' ou 'hd' (apenas para vídeo).
            progress_callback: Chamado com (completed, total, current_title).
            cancel_event: asyncio.Event que, quando setado, cancela o download.

        Returns:
            Dict com 'completed', 'failed', 'skipped', 'cancelled'.
        """
        total = len(hino_list)
        completed = 0
        failed = 0
        skipped = 0

        for i, hino_info in enumerate(hino_list):
            # Verifica cancelamento
            if cancel_event and cancel_event.is_set():
                return {
                    "completed": completed,
                    "failed": failed,
                    "skipped": skipped,
                    "cancelled": True,
                    "total": total,
                }

            hino_id = hino_info.get("id")
            link = hino_info.get("link_video", "")
            titulo = hino_info.get("titulo", f"Hino {hino_id}")

            if hino_id is None or not link:
                skipped += 1
                if progress_callback:
                    progress_callback(completed + skipped + failed, total, titulo)
                continue

            # Verifica se já baixado
            already = False
            if media_type == "audio":
                already = self.is_audio_downloaded(hino_id)
            else:
                already = self.is_video_downloaded(hino_id, quality)

            if already:
                skipped += 1
                if progress_callback:
                    progress_callback(completed + skipped + failed, total, titulo)
                continue

            # Executa download
            try:
                if media_type == "audio":
                    result = await self.download_audio(hino_id, link)
                else:
                    result = await self.download_video(hino_id, link, quality)

                if result:
                    completed += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

            if progress_callback:
                progress_callback(completed + skipped + failed, total, titulo)

        return {
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
            "cancelled": False,
            "total": total,
        }

    # ── Reprodução via Subprocesso (Desktop Fallback) ─────────────────

    def play_audio(self, source: str) -> bool:
        """
        Inicia a reprodução de áudio via subprocesso (desktop Linux/macOS).
        Retorna True se o player foi iniciado com sucesso.
        """
        if not source:
            return False
        self.stop_audio()

        players = ["ffplay", "mpv", "paplay", "aplay"]
        player_args = {
            "ffplay": ["-nodisp", "-autoexit", "-loglevel", "quiet"],
            "mpv": ["--no-video", "--really-quiet"],
            "paplay": [],
            "aplay": [],
        }

        for player in players:
            exe = shutil.which(player)
            if exe:
                try:
                    cmd = [exe] + player_args.get(player, []) + [source]
                    self.player_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return True
                except Exception:
                    continue
        return False

    def stop_audio(self) -> None:
        """Para a reprodução de áudio via subprocesso."""
        if self.player_process:
            try:
                self.player_process.terminate()
                self.player_process.wait(timeout=2)
            except Exception:
                try:
                    self.player_process.kill()
                except Exception:
                    pass
            self.player_process = None

    def is_audio_playing(self) -> bool:
        """Verifica se o subprocesso de áudio está ativo."""
        if self.player_process and self.player_process.poll() is None:
            return True
        return False

    # ── Gerenciamento de Armazenamento ────────────────────────────────

    def get_storage_usage(self) -> Dict[str, int]:
        """Retorna o uso de armazenamento em bytes por categoria."""
        usage = {"audio": 0, "video_sd": 0, "video_hd": 0}
        for category, subdir in [
            ("audio", self.AUDIO_SUBDIR),
            ("video_sd", self.VIDEO_SD_SUBDIR),
            ("video_hd", self.VIDEO_HD_SUBDIR),
        ]:
            dir_path = os.path.join(self.download_dir, subdir)
            if os.path.isdir(dir_path):
                for f in os.listdir(dir_path):
                    fp = os.path.join(dir_path, f)
                    if os.path.isfile(fp):
                        usage[category] += os.path.getsize(fp)
        return usage

    def clear_downloads(self, media_type: Optional[str] = None) -> int:
        """
        Remove downloads. Se media_type for None, remove tudo.
        Retorna o número de arquivos removidos.
        """
        count = 0
        subdirs = {
            "audio": self.AUDIO_SUBDIR,
            "video_sd": self.VIDEO_SD_SUBDIR,
            "video_hd": self.VIDEO_HD_SUBDIR,
        }
        if media_type and media_type in subdirs:
            targets = {media_type: subdirs[media_type]}
        else:
            targets = subdirs

        for _, subdir in targets.items():
            dir_path = os.path.join(self.download_dir, subdir)
            if os.path.isdir(dir_path):
                for f in os.listdir(dir_path):
                    fp = os.path.join(dir_path, f)
                    if os.path.isfile(fp):
                        try:
                            os.remove(fp)
                            count += 1
                        except Exception:
                            pass
        return count
