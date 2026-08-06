import pytest
from unittest.mock import patch
from src.services.media_service import MediaService


@pytest.mark.asyncio
async def test_sanitize_url_validation():
    """
    Testa a validação e sanitização de URLs no MediaService.
    """
    service = MediaService(download_dir="tmp_downloads")

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

    url1 = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    url2 = "https://youtu.be/dQw4w9WgXcQ"

    assert service.extract_youtube_id(url1) == "dQw4w9WgXcQ"
    assert service.extract_youtube_id(url2) == "dQw4w9WgXcQ"

    embed_url = service.get_embed_url(url1)
    assert embed_url == "https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1"


@pytest.mark.asyncio
async def test_get_info_mocked():
    """
    Testa a extração assíncrona de metadados com mock de yt_dlp.
    """
    service = MediaService(download_dir="tmp_downloads")

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
