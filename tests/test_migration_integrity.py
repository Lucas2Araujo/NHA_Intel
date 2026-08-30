import pytest

from src.database.connection import DatabaseConnection
from src.repositories.culto_repository import CultoRepository
from src.repositories.favorito_repository import FavoritoRepository
from src.repositories.hino_repository import HinoRepository
from src.repositories.historico_repository import HistoricoRepository


@pytest.mark.asyncio
async def test_migrated_database_integrity():
    """Valida a integridade física e lógica dos 601 hinos no hinario.db."""
    db_conn = DatabaseConnection(db_path="hinario.db")
    try:
        repo = HinoRepository(db_conn)
        all_hinos = await repo.get_all()

        # Deve conter exatamente 601 hinos
        assert len(all_hinos) == 601

        # Hino 1 deve ter todos os campos preenchidos
        hino_1 = await repo.get_by_id(1)
        assert hino_1 is not None
        assert hino_1.numero == "1"
        assert hino_1.titulo == "Santo, Santo, Santo!"
        assert hino_1.letra is not None and len(hino_1.letra) > 0
        assert hino_1.letra_json is not None
        assert hino_1.autor_letra == "Reginald Heber"
        assert hino_1.autor_musica == "John Bacchus Dykes"
        assert hino_1.link_video.startswith("https://www.youtube.com")

        # Metadados relacionados do Hino 1
        meta = await repo.get_metadados_relacionados(1)
        assert "temas" in meta and len(meta["temas"]) > 0
        assert "textos_biblicos" in meta and len(meta["textos_biblicos"]) > 0

        # Validação de hinos com letras no número (587A e 587B)
        found_587a = [h for h in all_hinos if h.numero == "587A"]
        found_587b = [h for h in all_hinos if h.numero == "587B"]
        assert len(found_587a) == 1
        assert len(found_587b) == 1

        # Validação de busca FTS
        busca = await repo.search("Onipotente")
        assert len(busca) > 0
        assert any(h.numero == "1" for h in busca)
    finally:
        await db_conn.close()


@pytest.mark.asyncio
async def test_user_tables_in_migrated_database():
    """Valida o funcionamento das tabelas de favoritos, histórico, cultos e preferências."""
    db_conn = DatabaseConnection(db_path="hinario.db")
    try:
        fav_repo = FavoritoRepository(db_conn)
        hist_repo = HistoricoRepository(db_conn)
        culto_repo = CultoRepository(db_conn)

        # Favoritos
        favoritos = await fav_repo.get_favoritos()
        assert isinstance(favoritos, list)

        # Histórico
        recentes = await hist_repo.get_recentes()
        assert isinstance(recentes, list)

        # Listas de culto
        listas = await culto_repo.get_listas_culto()
        assert isinstance(listas, list)

        # Categorias e Temas
        hino_repo = HinoRepository(db_conn)
        categorias = await hino_repo.get_categorias()
        temas = await hino_repo.get_temas()
        assert len(categorias) > 0
        assert len(temas) == 15
    finally:
        await db_conn.close()
