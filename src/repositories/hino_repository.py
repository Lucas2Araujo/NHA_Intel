from typing import List, Optional, Dict
import aiosqlite
from src.database.connection import DatabaseConnection
from src.models.hino import Hino


class HinoRepository:
    """
    Repositório assíncrono para acesso e consulta dos hinos no banco SQLite hinario_normalizado.db.
    Garante o uso exclusivo de queries parametrizadas (?) para segurança contra SQL Injection.
    """

    def __init__(self, db_connection: DatabaseConnection):
        self.db_connection = db_connection

    async def get_all(self) -> List[Hino]:
        """
        Retorna todos os hinos do banco de dados contendo id, numero e titulo,
        ordenados numericamente.
        """
        query = "SELECT id, numero, titulo FROM hino ORDER BY CAST(numero AS INTEGER) ASC, numero ASC;"
        conn = await self.db_connection.get_connection()

        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()

        hinos: List[Hino] = []
        for row in rows:
            hinos.append(
                Hino(
                    id=row["id"],
                    numero=str(row["numero"]),
                    titulo=str(row["titulo"]),
                )
            )

        return hinos

    async def get_by_id(self, hino_id: int) -> Optional[Hino]:
        """
        Busca um hino específico pelo seu ID (Primary Key) com suporte a todos os metadados.
        Usa query parametrizada (?).
        """
        query = """
            SELECT id, numero, titulo, letra, autor_letra, autor_musica, texto_base, categoria, subcategoria, link_video 
            FROM hino 
            WHERE id = ?;
        """
        conn = await self.db_connection.get_connection()

        async with conn.execute(query, (hino_id,)) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        return Hino(
            id=row["id"],
            numero=str(row["numero"]),
            titulo=str(row["titulo"]),
            letra=row["letra"],
            autor_letra=row["autor_letra"],
            autor_musica=row["autor_musica"],
            texto_base=row["texto_base"],
            categoria=row["categoria"],
            subcategoria=row["subcategoria"],
            link_video=row["link_video"],
        )

    async def search(self, term: str) -> List[Hino]:
        """
        Busca hinos por número ou título usando o operador LIKE parametrizado (?).
        """
        if not term or not term.strip():
            return await self.get_all()

        query = """
            SELECT id, numero, titulo 
            FROM hino 
            WHERE numero LIKE ? OR titulo LIKE ?
            ORDER BY CAST(numero AS INTEGER) ASC, numero ASC;
        """
        search_pattern = f"%{term.strip()}%"
        conn = await self.db_connection.get_connection()

        async with conn.execute(query, (search_pattern, search_pattern)) as cursor:
            rows = await cursor.fetchall()

        hinos: List[Hino] = []
        for row in rows:
            hinos.append(
                Hino(
                    id=row["id"],
                    numero=str(row["numero"]),
                    titulo=str(row["titulo"]),
                )
            )

        return hinos

    async def get_metadados_relacionados(self, hino_id: int) -> Dict[str, List[str]]:
        """
        Consulta as tabelas de junção 'hino_tema'/'tema' e 'hino_texto'/'texto_biblico'
        retornando os temas e referências bíblicas associadas ao hino.
        """
        conn = await self.db_connection.get_connection()

        # Consulta Temas Relacionados
        query_temas = """
            SELECT t.nome 
            FROM tema t
            INNER JOIN hino_tema ht ON t.id = ht.tema_id
            WHERE ht.hino_id = ?;
        """
        temas: List[str] = []
        try:
            async with conn.execute(query_temas, (hino_id,)) as cursor:
                rows = await cursor.fetchall()
                temas = [str(r["nome"]) for r in rows if r["nome"]]
        except Exception:
            temas = []

        # Consulta Textos Bíblicos Relacionados
        query_textos = """
            SELECT tb.referencia 
            FROM texto_biblico tb
            INNER JOIN hino_texto ht ON tb.id = ht.texto_id
            WHERE ht.hino_id = ?;
        """
        textos: List[str] = []
        try:
            async with conn.execute(query_textos, (hino_id,)) as cursor:
                rows = await cursor.fetchall()
                textos = [str(r["referencia"]) for r in rows if r["referencia"]]
        except Exception:
            textos = []

        return {
            "temas": temas,
            "textos_biblicos": textos,
        }
