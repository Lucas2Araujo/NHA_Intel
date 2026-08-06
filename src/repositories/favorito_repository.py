from typing import List
import aiosqlite
from src.database.connection import DatabaseConnection
from src.models.hino import Hino


class FavoritoRepository:
    """
    Repositório assíncrono para manipulação da tabela de Favoritos (favorito).
    Aplica o Repository Pattern com aiosqlite e queries parametrizadas.
    """

    def __init__(self, db_connection: DatabaseConnection):
        self.db_connection = db_connection

    async def add_favorito(self, hino_id: int) -> bool:
        """Adiciona um hino aos favoritos se ainda não estiver presente."""
        query = "INSERT OR IGNORE INTO favorito (hino_id) VALUES (?)"
        conn = await self.db_connection.get_connection()
        async with conn.execute(query, (hino_id,)) as cursor:
            await conn.commit()
            return cursor.rowcount > 0

    async def remove_favorito(self, hino_id: int) -> bool:
        """Remove um hino dos favoritos."""
        query = "DELETE FROM favorito WHERE hino_id = ?"
        conn = await self.db_connection.get_connection()
        async with conn.execute(query, (hino_id,)) as cursor:
            await conn.commit()
            return cursor.rowcount > 0

    async def is_favorito(self, hino_id: int) -> bool:
        """Verifica se um hino está marcado como favorito."""
        query = "SELECT 1 FROM favorito WHERE hino_id = ?"
        conn = await self.db_connection.get_connection()
        async with conn.execute(query, (hino_id,)) as cursor:
            row = await cursor.fetchone()
            return row is not None

    async def get_favoritos(self) -> List[Hino]:
        """Retorna a lista de todos os hinos favoritados pelo usuário."""
        query = """
            SELECT h.id, h.numero, h.titulo 
            FROM hino h
            INNER JOIN favorito f ON h.id = f.hino_id
            ORDER BY f.data_favoritado DESC
        """
        conn = await self.db_connection.get_connection()
        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()

        hinos: List[Hino] = []
        for row in rows:
            hinos.append(
                Hino(id=row["id"], numero=str(row["numero"]), titulo=str(row["titulo"]))
            )

        return hinos
