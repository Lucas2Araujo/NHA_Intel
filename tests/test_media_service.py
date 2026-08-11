import os
import pytest
from unittest.mock import patch, MagicMock
from src.services.media_service import (
    MediaService,
    QUALITY_SD,
    QUALITY_HD,
    path_to_file_uri,
)


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

    # Verifica caminhos de áudio
    audio_path = service.get_local_audio_path(1)
    assert service.AUDIO_SUBDIR in audio_path
    assert service.is_audio_downloaded(1) is False
    assert service.is_downloaded(1) is False

    # Cria arquivo dummy de áudio
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    with open(audio_path, "w") as f:
        f.write("audio data")

    assert service.is_audio_downloaded(1) is True
    assert service.is_downloaded(1) is True

    # Verifica caminhos de vídeo
    video_sd_path = service.get_local_video_path(1, QUALITY_SD)
    video_hd_path = service.get_local_video_path(1, QUALITY_HD)
    assert service.VIDEO_SD_SUBDIR in video_sd_path
    assert service.VIDEO_HD_SUBDIR in video_hd_path
    assert service.is_video_downloaded(1, QUALITY_SD) is False
    assert service.is_video_downloaded(1, QUALITY_HD) is False

    # Cria arquivo dummy de vídeo SD
    os.makedirs(os.path.dirname(video_sd_path), exist_ok=True)
    with open(video_sd_path, "w") as f:
        f.write("video data")

    assert service.is_video_downloaded(1, QUALITY_SD) is True
    assert service.is_video_downloaded(1, QUALITY_HD) is False

    # Verifica status completo
    status = service.get_download_status(1)
    assert status["audio"] is True
    assert status["video_sd"] is True
    assert status["video_hd"] is False


@pytest.mark.asyncio
async def test_file_uri_conversion():
    """
    Testa a conversão de caminhos para URIs file://.
    """
    uri = path_to_file_uri("/data/user/0/app/files/downloads/audio/hino_1.mp3")
    assert uri.startswith("file://")
    assert "hino_1.mp3" in uri


@pytest.mark.asyncio
async def test_play_and_stop_audio_process():
    """
    Testa a inicialização e interrupção do processo de áudio.
    """
    service = MediaService(download_dir="tmp_downloads")

    assert service.play_audio("") is False

    with patch("shutil.which", return_value="/usr/bin/ffplay"), patch("subprocess.Popen") as MockPopen:
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        MockPopen.return_value = mock_proc

        started = service.play_audio("tmp_downloads/dummy.mp3")
        assert started is True
        assert service.is_audio_playing() is True

        service.stop_audio()
        assert service.is_audio_playing() is False

    # Testa quando nenhum player de mídia está instalado no sistema (ex: CI Linux headless)
    with patch("shutil.which", return_value=None):
        assert service.play_audio("tmp_downloads/dummy.mp3") is False


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

    # Simula download criando o arquivo esperado
    audio_path = service.get_local_audio_path(1)
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)

    with patch("yt_dlp.YoutubeDL") as MockYDL:
        instance = MockYDL.return_value.__enter__.return_value

        def _fake_download(urls):
            with open(audio_path, "w") as f:
                f.write("fake audio")

        instance.download.side_effect = _fake_download

        filepath = await service.download_audio(1, "https://www.youtube.com/watch?v=123")
        assert filepath is not None
        assert os.path.isfile(filepath)


@pytest.mark.asyncio
async def test_download_video_mocked(tmp_path):
    """
    Testa o download de vídeo SD e HD com mock do yt_dlp.
    """
    download_dir = str(tmp_path)
    service = MediaService(download_dir=download_dir)

    assert await service.download_video(1, "") is None

    # Testa download de vídeo SD
    video_sd_path = service.get_local_video_path(1, QUALITY_SD)
    os.makedirs(os.path.dirname(video_sd_path), exist_ok=True)

    with patch("yt_dlp.YoutubeDL") as MockYDL:
        instance = MockYDL.return_value.__enter__.return_value

        def _fake_download_sd(urls):
            with open(video_sd_path, "w") as f:
                f.write("fake video sd")

        instance.download.side_effect = _fake_download_sd

        filepath = await service.download_video(
            1, "https://www.youtube.com/watch?v=123", QUALITY_SD
        )
        assert filepath is not None
        assert os.path.isfile(filepath)

    assert service.is_video_downloaded(1, QUALITY_SD) is True


@pytest.mark.asyncio
async def test_storage_usage_and_cleanup(tmp_path):
    """
    Testa o cálculo de uso de armazenamento e limpeza de downloads.
    """
    download_dir = str(tmp_path)
    service = MediaService(download_dir=download_dir)

    # Cria arquivos dummy
    audio_path = service.get_local_audio_path(1)
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    with open(audio_path, "w") as f:
        f.write("x" * 1024)

    video_path = service.get_local_video_path(1, QUALITY_SD)
    os.makedirs(os.path.dirname(video_path), exist_ok=True)
    with open(video_path, "w") as f:
        f.write("y" * 2048)

    usage = service.get_storage_usage()
    assert usage["audio"] > 0
    assert usage["video_sd"] > 0
    assert usage["video_hd"] == 0

    # Limpa apenas áudios
    count = service.clear_downloads("audio")
    assert count == 1
    assert service.is_audio_downloaded(1) is False
    assert service.is_video_downloaded(1, QUALITY_SD) is True

    # Limpa tudo
    count = service.clear_downloads()
    assert count == 1  # Sobrou apenas o vídeo SD
    assert service.is_video_downloaded(1, QUALITY_SD) is False


@pytest.mark.asyncio
async def test_audio_file_uri(tmp_path):
    """
    Testa a geração de URIs file:// para arquivos de áudio.
    """
    download_dir = str(tmp_path)
    service = MediaService(download_dir=download_dir)

    # Sem arquivo, retorna None
    assert service.get_audio_file_uri(1) is None

    # Com arquivo, retorna URI
    audio_path = service.get_local_audio_path(1)
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)
    with open(audio_path, "w") as f:
        f.write("audio")

    uri = service.get_audio_file_uri(1)
    assert uri is not None
    assert uri.startswith("file://")
    assert "hino_1" in uri
