import re
import unicodedata
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
        conn = await self.db_connection.get_connection()
        query = """
            SELECT id, numero, titulo 
            FROM hino 
            ORDER BY CAST(numero AS INTEGER) ASC, numero ASC;
        """
        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()

        return [
            Hino(id=row["id"], numero=str(row["numero"]), titulo=str(row["titulo"]))
            for row in rows
        ]

    async def get_by_id(self, hino_id: int) -> Optional[Hino]:
        """
        Retorna um hino completo pelo ID único.
        """
        conn = await self.db_connection.get_connection()
        query = """
            SELECT * 
            FROM hino 
            WHERE id = ?;
        """
        async with conn.execute(query, (hino_id,)) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        keys = row.keys()
        return Hino(
            id=row["id"],
            numero=str(row["numero"]),
            titulo=str(row["titulo"]),
            letra=row["letra"] if "letra" in keys else None,
            autor_letra=row["autor_letra"] if "autor_letra" in keys else None,
            autor_musica=row["autor_musica"] if "autor_musica" in keys else None,
            texto_base=row["texto_base"] if "texto_base" in keys else None,
            categoria=row["categoria"] if "categoria" in keys else None,
            subcategoria=row["subcategoria"] if "subcategoria" in keys else None,
            link_video=row["link_video"] if "link_video" in keys else None,
            letra_json=row["letra_json"] if "letra_json" in keys else None,
            autores=row["autores"] if "autores" in keys else None,
        )

    async def search(self, term: str) -> List[Hino]:
        """
        Busca inteligente de hinos com relevância ponderada:
        1. Se for número: busca por número exato ou prefixo do número (ex: '1' -> Hino 1 em 1º lugar, depois 10, 11...).
        2. Se for texto: prioriza correspondências no título, categoria e tema, depois na letra e textos bíblicos via FTS5 / LIKE.
        """
        if not term or not term.strip():
            return await self.get_all()

        conn = await self.db_connection.get_connection()
        clean_term = term.strip()

        # 1. Busca por Número (prioridade total quando o termo é puramente numérico)
        if clean_term.isdigit():
            query_num = """
                SELECT id, numero, titulo 
                FROM hino 
                WHERE numero = ? OR numero LIKE ?
                ORDER BY 
                    CASE WHEN numero = ? THEN 0 ELSE 1 END,
                    CAST(numero AS INTEGER) ASC,
                    numero ASC
                LIMIT 100;
            """
            num_pattern = f"{clean_term}%"
            async with conn.execute(query_num, (clean_term, num_pattern, clean_term)) as cursor:
                rows = await cursor.fetchall()
            if rows:
                return [
                    Hino(id=row["id"], numero=str(row["numero"]), titulo=str(row["titulo"]))
                    for row in rows
                ]

        # Lista de hinos encontrados por id para evitar duplicatas mantendo a ordem de relevância
        seen_ids = set()
        results: List[Hino] = []

        def _add_rows(rows_to_add):
            for row in rows_to_add:
                h_id = int(row["id"])
                if h_id not in seen_ids:
                    seen_ids.add(h_id)
                    results.append(Hino(id=h_id, numero=str(row["numero"]), titulo=str(row["titulo"])))

        # 2. Busca direta por Título, Categoria e Tema (Alta relevância)
        query_meta = """
            SELECT h.id, h.numero, h.titulo,
                   MIN(CASE 
                       WHEN LOWER(h.titulo) = LOWER(?) THEN 1
                       WHEN LOWER(h.titulo) LIKE LOWER(?) THEN 2
                       WHEN LOWER(h.categoria) = LOWER(?) THEN 3
                       WHEN LOWER(h.categoria) LIKE LOWER(?) THEN 4
                       WHEN LOWER(t.nome) = LOWER(?) THEN 5
                       WHEN LOWER(t.nome) LIKE LOWER(?) THEN 6
                       ELSE 7
                   END) AS rel
            FROM hino h
            LEFT JOIN hino_tema ht ON h.id = ht.hino_id
            LEFT JOIN tema t ON t.id = ht.tema_id
            WHERE LOWER(h.titulo) LIKE LOWER(?)
               OR LOWER(h.categoria) LIKE LOWER(?)
               OR LOWER(h.subcategoria) LIKE LOWER(?)
               OR LOWER(t.nome) LIKE LOWER(?)
            GROUP BY h.id, h.numero, h.titulo
            ORDER BY rel, CAST(h.numero AS INTEGER) ASC
            LIMIT 100;
        """
        exact_term = clean_term
        like_pattern = f"%{clean_term}%"
        try:
            async with conn.execute(
                query_meta, 
                (exact_term, like_pattern, exact_term, like_pattern, exact_term, like_pattern,
                 like_pattern, like_pattern, like_pattern, like_pattern)
            ) as cursor:
                rows_meta = await cursor.fetchall()
                _add_rows(rows_meta)
        except Exception:
            pass

        # 3. Busca por FTS5 (Letra, textos bíblicos, conteúdo geral)
        stopwords = {"de", "da", "do", "das", "dos", "e", "o", "a", "os", "as", "em", "no", "na", "nos", "nas", "um", "uma", "com", "por", "para"}
        sanitized = re.sub(r'[^\w\s]', ' ', clean_term)
        significant_words = [w for w in sanitized.split() if len(w) >= 2 and w.lower() not in stopwords]

        if significant_words:
            fts_term = " ".join(f"{w}*" for w in significant_words)
            try:
                fts_query = """
                    SELECT h.id, h.numero, h.titulo
                    FROM hino h
                    INNER JOIN hino_fts ON h.id = hino_fts.rowid
                    WHERE hino_fts MATCH ?
                    ORDER BY rank
                    LIMIT 100;
                """
                async with conn.execute(fts_query, (fts_term,)) as cursor:
                    rows_fts = await cursor.fetchall()
                    _add_rows(rows_fts)
            except Exception:
                pass

        # 4. Fallback com LIKE na letra e referências se ainda não encontrou nada
        if not results:
            query_fallback = """
                SELECT DISTINCT h.id, h.numero, h.titulo 
                FROM hino h
                LEFT JOIN hino_tema ht ON h.id = ht.hino_id
                LEFT JOIN tema t ON t.id = ht.tema_id
                LEFT JOIN hino_texto htx ON h.id = htx.hino_id
                LEFT JOIN texto_biblico tb ON tb.id = htx.texto_id
                WHERE h.numero LIKE ? 
                   OR h.titulo LIKE ? 
                   OR h.letra LIKE ? 
                   OR h.categoria LIKE ? 
                   OR h.subcategoria LIKE ? 
                   OR h.texto_base LIKE ? 
                   OR h.autor_letra LIKE ? 
                   OR h.autor_musica LIKE ? 
                   OR t.nome LIKE ?
                   OR tb.referencia LIKE ?
                ORDER BY CAST(h.numero AS INTEGER) ASC, h.numero ASC
                LIMIT 100;
            """
            params = (like_pattern,) * 10
            try:
                async with conn.execute(query_fallback, params) as cursor:
                    rows_fb = await cursor.fetchall()
                    _add_rows(rows_fb)
            except Exception:
                pass

        return results

    async def get_categorias(self) -> List[str]:
        """Retorna todas as categorias únicas de hinos, ordenadas alfabeticamente e normalizadas."""
        conn = await self.db_connection.get_connection()
        query = """
            SELECT DISTINCT categoria 
            FROM hino 
            WHERE categoria IS NOT NULL AND categoria != ''
            ORDER BY categoria ASC;
        """
        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()
        return [unicodedata.normalize("NFC", str(row["categoria"])) for row in rows]

    async def get_temas(self) -> List[str]:
        """Retorna todos os temas únicos do banco, ordenados alfabeticamente e normalizados."""
        conn = await self.db_connection.get_connection()
        query = """
            SELECT DISTINCT t.nome 
            FROM tema t
            ORDER BY t.nome ASC;
        """
        try:
            async with conn.execute(query) as cursor:
                rows = await cursor.fetchall()
            return [unicodedata.normalize("NFC", str(row["nome"])) for row in rows]
        except Exception:
            return []

    async def search_by_categoria(self, categoria: str) -> List[Hino]:
        """Retorna todos os hinos de uma categoria específica (case-insensitive e normalizada)."""
        cat_norm = unicodedata.normalize("NFC", (categoria or "").strip())
        conn = await self.db_connection.get_connection()
        query = """
            SELECT id, numero, titulo
            FROM hino
            WHERE LOWER(categoria) = LOWER(?) OR categoria LIKE ?
            ORDER BY CAST(numero AS INTEGER) ASC, numero ASC;
        """
        cat_pattern = f"%{cat_norm}%"
        async with conn.execute(query, (cat_norm, cat_pattern)) as cursor:
            rows = await cursor.fetchall()
        return [
            Hino(id=row["id"], numero=str(row["numero"]), titulo=str(row["titulo"]))
            for row in rows
        ]

    async def search_by_tema(self, tema: str) -> List[Hino]:
        """Retorna todos os hinos associados a um tema específico (case-insensitive e normalizada)."""
        tema_norm = unicodedata.normalize("NFC", (tema or "").strip())
        conn = await self.db_connection.get_connection()
        query = """
            SELECT DISTINCT h.id, h.numero, h.titulo
            FROM hino h
            INNER JOIN hino_tema ht ON h.id = ht.hino_id
            INNER JOIN tema t ON t.id = ht.tema_id
            WHERE LOWER(t.nome) = LOWER(?) OR t.nome LIKE ?
            ORDER BY CAST(h.numero AS INTEGER) ASC, h.numero ASC;
        """
        tema_pattern = f"%{tema_norm}%"
        try:
            async with conn.execute(query, (tema_norm, tema_pattern)) as cursor:
                rows = await cursor.fetchall()
            return [
                Hino(id=row["id"], numero=str(row["numero"]), titulo=str(row["titulo"]))
                for row in rows
            ]
        except Exception:
            return []

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
