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

    async def delete_lista_culto(self, lista_id: int) -> bool:
        """Exclui uma lista de culto e seus itens associados."""
        conn = await self.db_connection.get_connection()
        try:
            # Aiosqlite/SQLite pode não estar com ON DELETE CASCADE ativado por padrão
            await conn.execute("DELETE FROM item_lista_culto WHERE lista_id = ?", (lista_id,))
            await conn.execute("DELETE FROM lista_culto WHERE id = ?", (lista_id,))
            await conn.commit()
            return True
        except Exception:
            return False

    async def rename_lista_culto(self, lista_id: int, novo_tema: str) -> bool:
        """Atualiza o tema gerador de uma lista de culto."""
        if not novo_tema or not novo_tema.strip():
            return False
        conn = await self.db_connection.get_connection()
        try:
            await conn.execute(
                "UPDATE lista_culto SET tema_gerador = ? WHERE id = ?",
                (novo_tema.strip(), lista_id)
            )
            await conn.commit()
            return True
        except Exception:
            return False

    async def remove_hino_da_lista(self, lista_id: int, hino_id: int) -> bool:
        """
        Remove um hino de uma lista de culto.
        Pode haver hinos duplicados na mesma lista, mas esta função removerá
        apenas a primeira ocorrência ou todas dependendo da modelagem.
        Vamos remover apenas um registro baseado no ROWID para ser seguro,
        ou simplesmente todos com esse hino_id nesta lista.
        Para simplificar, deletamos todos os registros com aquele hino_id na lista.
        """
        conn = await self.db_connection.get_connection()
        try:
            # Deletamos usando limit 1 caso aiosqlite suporte (SQLite compiled with certain options),
            # ou usamos subquery. O mais simples e seguro é subquery com rowid.
            query = """
                DELETE FROM item_lista_culto
                WHERE rowid = (
                    SELECT rowid FROM item_lista_culto
                    WHERE lista_id = ? AND hino_id = ?
                    LIMIT 1
                )
            """
            await conn.execute(query, (lista_id, hino_id))
            return True
        except Exception:
            return False

    async def add_hino_a_lista(self, lista_id: int, hino_id: int) -> bool:
        """Adiciona um hino ao final da lista de culto."""
        conn = await self.db_connection.get_connection()
        try:
            # Pega a última ordem de execução
            async with conn.execute(
                "SELECT MAX(ordem_execucao) as max_ordem FROM item_lista_culto WHERE lista_id = ?", 
                (lista_id,)
            ) as cursor:
                row = await cursor.fetchone()
                max_ordem = (row["max_ordem"] if row else 0) or 0
                prox_ordem = max_ordem + 1
            
            await conn.execute(
                "INSERT INTO item_lista_culto (lista_id, hino_id, ordem_execucao) VALUES (?, ?, ?)",
                (lista_id, hino_id, prox_ordem),
            )
            await conn.commit()
            return True
        except Exception:
            return False

    async def update_hino_da_lista(self, lista_id: int, old_hino_id: int, new_hino_id: int) -> bool:
        """
        Substitui um hino por outro em uma lista de culto, atualizando apenas a
        primeira ocorrência do hino antigo para preservar a ordem.
        """
        conn = await self.db_connection.get_connection()
        try:
            # Substitui apenas um registro limitando pelo rowid
            query = """
                UPDATE item_lista_culto
                SET hino_id = ?
                WHERE rowid = (
                    SELECT rowid FROM item_lista_culto
                    WHERE lista_id = ? AND hino_id = ?
                    LIMIT 1
                )
            """
            await conn.execute(query, (new_hino_id, lista_id, old_hino_id))
            await conn.commit()
            return True
        except Exception:
            return False
