import os
import re
import asyncio
from typing import Optional, Dict, Any
import yt_dlp


class MediaService:
    """
    Serviço assíncrono seguro responsável pela extração de mídias, geração de links embutidos
    e gerenciamento de downloads offline através do yt-dlp.
    Garante sanitização estrita de entrada e execução em thread separada para não bloquear a UI.
    """

    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)

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
