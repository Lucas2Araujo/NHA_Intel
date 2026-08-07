import os
import re
import shutil
import asyncio
import subprocess
from typing import Optional, Dict, Any
import yt_dlp


class MediaService:
    """
    Serviço assíncrono seguro responsável pela extração de mídias, geração de links embutidos,
    reprodução real de áudio nos alto-falantes e gerenciamento de downloads offline através do yt-dlp.
    Garante sanitização estrita de entrada e execução não-bloqueante para não travar a UI.
    """

    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)
        self.player_process: Optional[subprocess.Popen] = None

    def _sanitize_url(self, url: str) -> str:
        """Sanitiza URLs para evitar injeção de parâmetros e comandos."""
        if not url:
            return ""
        url = url.strip()
        if not re.match(r"^https?://[^\s\"']+$", url, re.IGNORECASE):
            raise ValueError("URL de mídia inválida ou insegura.")
        return url

    def extract_youtube_id(self, url: str) -> Optional[str]:
        """Extrai o ID do vídeo do YouTube de diversos formatos de URL."""
        if not url:
            return None
        match = re.search(r"(?:v=|\/|embed\/|shorts\/)([a-zA-Z0-9_-]{11})", url)
        if match:
            return match.group(1)
        return None

    def get_embed_url(self, url: str) -> Optional[str]:
        """Retorna a URL formatada para exibição do vídeo embutido (embed)."""
        video_id = self.extract_youtube_id(url)
        if video_id:
            return f"https://www.youtube.com/embed/{video_id}?autoplay=1"
        return url if url and url.startswith("http") else None

    def is_downloaded(self, hino_id: int) -> bool:
        """Verifica se o áudio do hino já foi baixado e existe localmente."""
        filepath = self.get_local_filepath(hino_id)
        return os.path.isfile(filepath)

    def get_local_filepath(self, hino_id: int) -> str:
        """Retorna o caminho do arquivo de áudio local baixado."""
        return os.path.join(self.download_dir, f"hino_{hino_id}.mp3")

    def play_audio(self, source_path_or_url: str) -> bool:
        """
        Executa a reprodução física e real do áudio nos alto-falantes do dispositivo.
        Suporta caminhos de arquivos locais (.mp3) e URLs de streaming.
        """
        self.stop_audio()

        if not source_path_or_url:
            return False

        # Tenta encontrar um reprodutor de mídia do sistema operacional
        players_priority = [
            ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet"]),
            ("mpv", ["--no-video", "--really-quiet"]),
            ("paplay", []),
            ("aplay", []),
        ]

        player_bin = None
        player_args = []

        for p_name, p_args in players_priority:
            if shutil.which(p_name):
                player_bin = p_name
                player_args = p_args
                break

        if not player_bin:
            return False

        cmd = [player_bin] + player_args + [source_path_or_url]

        try:
            self.player_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            self.player_process = None
            return False

    def stop_audio(self) -> None:
        """Interrompe a reprodução real do áudio se estiver em andamento."""
        if self.player_process and self.player_process.poll() is None:
            try:
                self.player_process.terminate()
                self.player_process.wait(timeout=1.0)
            except Exception:
                try:
                    self.player_process.kill()
                except Exception:
                    pass
        self.player_process = None

    def is_audio_playing(self) -> bool:
        """Verifica se há um áudio sendo reproduzido no momento."""
        return self.player_process is not None and self.player_process.poll() is None

    async def get_info(self, video_url: str) -> Optional[Dict[str, Any]]:
        """
        Extrai metadados do vídeo/áudio de forma assíncrona não-bloqueante.
        """
        sanitized_url = self._sanitize_url(video_url)
        if not sanitized_url:
            return None

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "format": "bestaudio/best",
        }

        def _extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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

    async def download_audio(self, hino_id: int, video_url: str) -> Optional[str]:
        """
        Realiza o download do áudio no diretório local de forma assíncrona e segura.
        """
        sanitized_url = self._sanitize_url(video_url)
        if not sanitized_url:
            return None

        output_template = os.path.join(self.download_dir, f"hino_{hino_id}.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
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

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([sanitized_url])
            return self.get_local_filepath(hino_id)

        try:
            return await asyncio.to_thread(_download)
        except Exception:
            try:
                fallback_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": os.path.join(self.download_dir, f"hino_{hino_id}.mp3"),
                    "quiet": True,
                }
                def _fallback_download():
                    with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                        ydl.download([sanitized_url])
                    return self.get_local_filepath(hino_id)

                return await asyncio.to_thread(_fallback_download)
            except Exception:
                return None
