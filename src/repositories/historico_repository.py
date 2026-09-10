import asyncio
import sqlite3

from src.database.connection import DatabaseConnection
from src.models.hino import Hino


class HistoricoRepository:
    """
    Repositório assíncrono para manipulação da tabela de Histórico (historico).
    Registra os acessos aos hinos e permite recuperar os mais recentes.
    """

    def __init__(self, db_connection: DatabaseConnection):
        self.db_connection = db_connection

    async def _safe_rollback(self) -> None:
        try:
            conn = await self.db_connection.get_connection()
            await conn.rollback()
        except Exception:
            pass

    async def add_acesso(self, hino_id: int) -> bool:
        """Registra a visualização de um hino no histórico de acessos com resiliência a concorrência e locks."""
        query = "INSERT INTO historico (hino_id) VALUES (?)"
        max_retries = 3
        for attempt in range(max_retries):
            try:
                conn = await self.db_connection.get_connection()
                async with conn.execute(query, (hino_id,)) as cursor:
                    success = cursor.rowcount > 0
                await conn.commit()
                return success
            except sqlite3.OperationalError as exc:
                await self._safe_rollback()
                is_lock = "locked" in str(exc).lower() or "busy" in str(exc).lower()
                if is_lock and attempt < max_retries - 1:
                    await asyncio.sleep(0.05 * (2 ** attempt))
                    continue
                return False
            except Exception:
                await self._safe_rollback()
                return False
        return False

    async def get_recentes(self, limit: int = 50) -> list[Hino]:
        """Retorna os hinos mais recentemente acessados (sem duplicatas consecutivas)."""
        query = """
            SELECT h.id, h.numero, h.titulo
            FROM hino h
            INNER JOIN (
                SELECT hino_id, MAX(data_acesso) AS ultimo_acesso, MAX(id) AS ultimo_id
                FROM historico
                GROUP BY hino_id
            ) latest ON h.id = latest.hino_id
            ORDER BY latest.ultimo_acesso DESC, latest.ultimo_id DESC
            LIMIT ?
        """
        try:
            conn = await self.db_connection.get_connection()
            async with conn.execute(query, (limit,)) as cursor:
                rows = await cursor.fetchall()

            hinos: list[Hino] = []
            for row in rows:
                hinos.append(
                    Hino(id=row["id"], numero=str(row["numero"]), titulo=str(row["titulo"]))
                )

            return hinos
        except Exception:
            return []
