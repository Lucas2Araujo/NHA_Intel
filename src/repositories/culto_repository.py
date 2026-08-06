from typing import List, Dict, Any, Optional
import aiosqlite
from src.database.connection import DatabaseConnection
from src.models.hino import Hino


class CultoRepository:
    """
    Repositório assíncrono para criação, listagem e gerenciamento de listas de culto.
    Manipula as tabelas 'lista_culto' e 'item_lista_culto' usando aiosqlite.
    """

    def __init__(self, db_connection: DatabaseConnection):
        self.db_connection = db_connection

    async def create_lista_culto(
        self, tema_gerador: str, hino_ids: List[int]
    ) -> Optional[int]:
        """
        Cria uma nova lista de culto no banco de dados com a lista ordenada de hinos.
        Retorna o ID da lista criada.
        """
        if not hino_ids:
            return None

        conn = await self.db_connection.get_connection()

        # Insere a lista principal
        cursor = await conn.execute(
            "INSERT INTO lista_culto (tema_gerador) VALUES (?)", (tema_gerador.strip(),)
        )
        lista_id = cursor.lastrowid
        await cursor.close()

        # Insere os itens da lista
        for ordem, hino_id in enumerate(hino_ids, start=1):
            await conn.execute(
                "INSERT INTO item_lista_culto (lista_id, hino_id, ordem_execucao) VALUES (?, ?, ?)",
                (lista_id, hino_id, ordem),
            )

        await conn.commit()
        return lista_id

    async def get_listas_culto(self) -> List[Dict[str, Any]]:
        """Retorna todas as listas de culto salvas com contagem de hinos."""
        query = """
            SELECT lc.id, lc.tema_gerador, lc.data_criacao, COUNT(ilc.hino_id) as total_hinos
            FROM lista_culto lc
            LEFT JOIN item_lista_culto ilc ON lc.id = ilc.lista_id
            GROUP BY lc.id
            ORDER BY lc.data_criacao DESC
        """
        conn = await self.db_connection.get_connection()
        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()

        listas = []
        for row in rows:
            listas.append(
                {
                    "id": row["id"],
                    "tema_gerador": row["tema_gerador"],
                    "data_criacao": row["data_criacao"],
                    "total_hinos": row["total_hinos"],
                }
            )
        return listas

    async def get_hinos_da_lista(self, lista_id: int) -> List[Hino]:
        """Retorna os hinos pertencentes a uma lista de culto na ordem de execução."""
        query = """
            SELECT h.id, h.numero, h.titulo, h.letra, ilc.ordem_execucao
            FROM hino h
            INNER JOIN item_lista_culto ilc ON h.id = ilc.hino_id
            WHERE ilc.lista_id = ?
            ORDER BY ilc.ordem_execucao ASC
        """
        conn = await self.db_connection.get_connection()
        async with conn.execute(query, (lista_id,)) as cursor:
            rows = await cursor.fetchall()

        hinos: List[Hino] = []
        for row in rows:
            hinos.append(
                Hino(
                    id=row["id"],
                    numero=str(row["numero"]),
                    titulo=str(row["titulo"]),
                    letra=row["letra"],
                )
            )
        return hinos
