from typing import List
import aiosqlite
from src.database.connection import DatabaseConnection
from src.models.hino import Hino


class HistoricoRepository:
    """
    Repositório assíncrono para manipulação da tabela de Histórico (historico).
    Registra os acessos aos hinos e permite recuperar os mais recentes.
    """

    def __init__(self, db_connection: DatabaseConnection):
        self.db_connection = db_connection

    async def add_acesso(self, hino_id: int) -> bool:
        """Registra a visualização de um hino no histórico de acessos."""
        query = "INSERT INTO historico (hino_id) VALUES (?)"
        conn = await self.db_connection.get_connection()
        async with conn.execute(query, (hino_id,)) as cursor:
            await conn.commit()
            return cursor.rowcount > 0

    async def get_recentes(self, limit: int = 50) -> List[Hino]:
        """Retorna os hinos mais recentemente acessados (sem duplicatas consecutivas)."""
        query = """
            SELECT DISTINCT h.id, h.numero, h.titulo 
            FROM hino h
            INNER JOIN historico hist ON h.id = hist.hino_id
            ORDER BY hist.data_acesso DESC, hist.id DESC
            LIMIT ?
        """
        conn = await self.db_connection.get_connection()
        async with conn.execute(query, (limit,)) as cursor:
            rows = await cursor.fetchall()

        hinos: List[Hino] = []
        for row in rows:
            hinos.append(
                Hino(id=row["id"], numero=str(row["numero"]), titulo=str(row["titulo"]))
            )

        return hinos
