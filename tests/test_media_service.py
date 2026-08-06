import os
import pytest
from unittest.mock import patch, MagicMock
from src.services.media_service import MediaService


@pytest.mark.asyncio
async def test_sanitize_url_validation():
    """
    Testa a validação e sanitização de URLs no MediaService.
    """
    service = MediaService(download_dir="tmp_downloads")

    assert service._sanitize_url("") == ""

    valid_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert service._sanitize_url(valid_url) == valid_url

    with pytest.raises(ValueError):
        service._sanitize_url("https://youtube.com; rm -rf /")


@pytest.mark.asyncio
async def test_extract_youtube_id_and_embed():
    """
    Testa a extração do ID do vídeo e a formatação do link embutido (embed).
    """
    service = MediaService(download_dir="tmp_downloads")

    assert service.extract_youtube_id("") is None
    assert service.extract_youtube_id("invalid_url") is None

    url1 = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    url2 = "https://youtu.be/dQw4w9WgXcQ"

    assert service.extract_youtube_id(url1) == "dQw4w9WgXcQ"
    assert service.extract_youtube_id(url2) == "dQw4w9WgXcQ"

    embed_url = service.get_embed_url(url1)
    assert embed_url == "https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1"
    assert service.get_embed_url("") is None


@pytest.mark.asyncio
async def test_download_filepath_and_status(tmp_path):
    """
    Testa a verificação de arquivo baixado e o caminho local.
    """
    download_dir = str(tmp_path)
    service = MediaService(download_dir=download_dir)

    filepath = service.get_local_filepath(1)
    assert filepath == os.path.join(download_dir, "hino_1.mp3")
    assert service.is_downloaded(1) is False

    # Cria arquivo dummy
    with open(filepath, "w") as f:
        f.write("audio data")

    assert service.is_downloaded(1) is True


@pytest.mark.asyncio
async def test_play_and_stop_audio_process():
    """
    Testa a inicialização e interrupção do processo de áudio.
    """
    service = MediaService(download_dir="tmp_downloads")

    assert service.play_audio("") is False

    with patch("subprocess.Popen") as MockPopen:
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        MockPopen.return_value = mock_proc

        started = service.play_audio("tmp_downloads/dummy.mp3")
        assert started is True
        assert service.is_audio_playing() is True

        service.stop_audio()
        assert service.is_audio_playing() is False


@pytest.mark.asyncio
async def test_get_info_mocked():
    """
    Testa a extração assíncrona de metadados com mock de yt_dlp.
    """
    service = MediaService(download_dir="tmp_downloads")

    assert await service.get_info("") is None

    mock_info = {
        "title": "Hino 1 - Santo, Santo, Santo!",
        "duration": 180,
        "url": "https://googlevideo.com/stream",
        "thumbnail": "https://img.youtube.com/thumb.jpg",
    }

    with patch("yt_dlp.YoutubeDL") as MockYDL:
        instance = MockYDL.return_value.__enter__.return_value
        instance.extract_info.return_value = mock_info

        info = await service.get_info("https://www.youtube.com/watch?v=123")

        assert info is not None
        assert info["title"] == "Hino 1 - Santo, Santo, Santo!"
        assert info["duration"] == 180


@pytest.mark.asyncio
async def test_download_audio_mocked(tmp_path):
    """
    Testa o download de áudio com mock do yt_dlp.
    """
    download_dir = str(tmp_path)
    service = MediaService(download_dir=download_dir)

    assert await service.download_audio(1, "") is None

    with patch("yt_dlp.YoutubeDL") as MockYDL:
        instance = MockYDL.return_value.__enter__.return_value
        instance.download.return_value = None

        filepath = await service.download_audio(1, "https://www.youtube.com/watch?v=123")
        assert filepath == os.path.join(download_dir, "hino_1.mp3")
