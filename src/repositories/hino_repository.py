import re
import unicodedata
from collections.abc import Sequence
from typing import Any

import aiosqlite

from src.database.connection import DatabaseConnection
from src.models.hino import Hino


class HinoRepository:
    """
    Repositório assíncrono para acesso e consulta dos hinos no banco SQLite hinario.db.
    Possui cache em memória ultraleve (< 1 MB) compatível com celulares antigos (ARMv7)
    e computadores modernos.
    """

    def __init__(self, db_connection: DatabaseConnection):
        self.db_connection = db_connection
        self._summary_cache: list[Hino] | None = None
        self._num_index: dict[str, Hino] | None = None
        self._detail_cache: dict[int, Hino] = {}
        self._detail_num_cache: dict[str, Hino] = {}
        self._categorias_cache: list[str] | None = None
        self._temas_cache: list[str] | None = None
        self._metadados_cache: dict[int, dict[str, list[str]]] = {}

    def clear_cache(self) -> None:
        """Limpa todos os caches em memória."""
        self._summary_cache = None
        self._num_index = None
        self._detail_cache.clear()
        self._detail_num_cache.clear()
        self._categorias_cache = None
        self._temas_cache = None
        self._metadados_cache.clear()

    @staticmethod
    def _row_to_hino_summary(row: aiosqlite.Row) -> Hino:
        """Converte uma linha contendo id, numero e titulo em um DTO Hino resumido."""
        return Hino(
            id=row["id"],
            numero=str(row["numero"]),
            titulo=str(row["titulo"]),
        )

    @staticmethod
    def _row_to_hino(row: aiosqlite.Row) -> Hino:
        """Converte uma linha completa do SQLite em uma instância de Hino com todos os metadados."""
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

    async def get_all(self) -> list[Hino]:
        """
        Retorna todos os hinos do banco de dados contendo id, numero e titulo,
        ordenados numericamente. Utiliza cache em memória para resposta instantânea (0 ms).
        """
        if self._summary_cache is not None:
            return list(self._summary_cache)

        conn = await self.db_connection.get_connection()
        query = """
            SELECT id, numero, titulo 
            FROM hino 
            ORDER BY CAST(numero AS INTEGER) ASC, numero ASC;
        """
        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()

        summaries = [self._row_to_hino_summary(row) for row in rows]
        self._summary_cache = summaries
        self._num_index = {h.numero.strip().upper(): h for h in summaries}
        return list(summaries)

    async def get_all_complete(self) -> list[Hino]:
        """
        Retorna todos os hinos com todos os campos completos em uma única consulta otimizada.
        Elimina o problema de N+1 queries em processamento em lote.
        """
        conn = await self.db_connection.get_connection()
        query = """
            SELECT * 
            FROM hino 
            ORDER BY CAST(numero AS INTEGER) ASC, numero ASC;
        """
        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()

        return [self._row_to_hino(row) for row in rows]

    async def get_by_id(self, hino_id: int) -> Hino | None:
        """
        Retorna um hino completo pelo ID único, com cache LRU leve (máximo 30 itens).
        """
        if hino_id in self._detail_cache:
            return self._detail_cache[hino_id]

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

        hino = self._row_to_hino(row)
        # Limite de 30 itens no cache para proteger a RAM de celulares antigos (ARMv7)
        if len(self._detail_cache) >= 30:
            first_key = next(iter(self._detail_cache))
            del self._detail_cache[first_key]
        self._detail_cache[hino_id] = hino
        return hino

    async def get_by_numero(self, numero: str) -> Hino | None:
        """
        Retorna um hino completo pelo número (ex: '18', '587A').
        """
        if not numero:
            return None

        num_clean = numero.strip().upper()
        if num_clean in self._detail_num_cache:
            return self._detail_num_cache[num_clean]

        conn = await self.db_connection.get_connection()
        query = """
            SELECT * 
            FROM hino 
            WHERE numero = ? OR numero = ?
            LIMIT 1;
        """
        num_with_underscore = (
            num_clean.replace("A", "_A").replace("B", "_B")
            if ("A" in num_clean or "B" in num_clean) and "_" not in num_clean
            else num_clean
        )
        async with conn.execute(query, (num_clean, num_with_underscore)) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        hino = self._row_to_hino(row)
        if len(self._detail_num_cache) >= 30:
            first_key = next(iter(self._detail_num_cache))
            del self._detail_num_cache[first_key]
        self._detail_num_cache[num_clean] = hino
        return hino

    STOPWORDS = {
        "de",
        "da",
        "do",
        "das",
        "dos",
        "e",
        "o",
        "a",
        "os",
        "as",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "um",
        "uma",
        "com",
        "por",
        "para",
    }

    async def _search_by_number(self, conn: Any, clean_term: str) -> list[Hino]:
        """Busca hinos por número exato ou prefixo numérico."""
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
        async with conn.execute(
            query_num, (clean_term, num_pattern, clean_term)
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_hino_summary(row) for row in rows]

    async def _search_by_metadata(
        self,
        conn: Any,
        clean_term: str,
        results: list[Hino],
        seen_ids: set[int],
    ) -> None:
        """Busca direta por título, categoria e tema com ranking de relevância."""
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
                (
                    exact_term,
                    like_pattern,
                    exact_term,
                    like_pattern,
                    exact_term,
                    like_pattern,
                    like_pattern,
                    like_pattern,
                    like_pattern,
                    like_pattern,
                ),
            ) as cursor:
                rows = await cursor.fetchall()
            self._collect_unique_hinos(results, seen_ids, rows)
        except Exception:
            pass

    async def _search_by_fts(
        self,
        conn: Any,
        clean_term: str,
        results: list[Hino],
        seen_ids: set[int],
    ) -> None:
        """Busca via FTS5 por palavras significativas."""
        sanitized = re.sub(r"[^\w\s]", " ", clean_term)
        significant_words = [
            w
            for w in sanitized.split()
            if len(w) >= 2 and w.lower() not in self.STOPWORDS
        ]
        if not significant_words:
            return

        fts_term = " ".join(f"{w}*" for w in significant_words)
        fts_query = """
            SELECT h.id, h.numero, h.titulo
            FROM hino h
            INNER JOIN hino_fts ON h.id = hino_fts.rowid
            WHERE hino_fts MATCH ?
            ORDER BY rank
            LIMIT 100;
        """
        try:
            async with conn.execute(fts_query, (fts_term,)) as cursor:
                rows = await cursor.fetchall()
            self._collect_unique_hinos(results, seen_ids, rows)
        except Exception:
            pass

    async def _search_by_fallback_like(
        self,
        conn: Any,
        clean_term: str,
        results: list[Hino],
        seen_ids: set[int],
    ) -> None:
        """Busca ampla com LIKE como fallback caso não haja resultados em metadados/FTS."""
        like_pattern = f"%{clean_term}%"
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
                rows = await cursor.fetchall()
            self._collect_unique_hinos(results, seen_ids, rows)
        except Exception:
            pass

    def _collect_unique_hinos(
        self,
        results: list[Hino],
        seen_ids: set[int],
        rows: Sequence[Any],
    ) -> None:
        """Adiciona linhas aos resultados convertendo para Hino resumido se não duplicadas."""
        for row in rows:
            h_id = int(row["id"])
            if h_id not in seen_ids:
                seen_ids.add(h_id)
                results.append(self._row_to_hino_summary(row))

    async def search(self, term: str) -> list[Hino]:
        """
        Busca inteligente de hinos com relevância ponderada:
        1. Se for número: busca por número exato ou prefixo do número.
        2. Se for texto: prioriza correspondências no título, categoria e tema, depois FTS5 e LIKE.
        """
        if not term or not term.strip():
            return await self.get_all()

        conn = await self.db_connection.get_connection()
        clean_term = term.strip()

        # 1. Busca por Número
        if clean_term.isdigit():
            number_results = await self._search_by_number(conn, clean_term)
            if number_results:
                return number_results

        seen_ids: set[int] = set()
        results: list[Hino] = []

        # 2. Busca direta por Título, Categoria e Tema (Alta relevância)
        await self._search_by_metadata(conn, clean_term, results, seen_ids)

        # 3. Busca por FTS5 (Letra, textos bíblicos)
        await self._search_by_fts(conn, clean_term, results, seen_ids)

        # 4. Fallback com LIKE se nada foi encontrado
        if not results:
            await self._search_by_fallback_like(conn, clean_term, results, seen_ids)

        return results

    async def get_categorias(self) -> list[str]:
        """Retorna todas as categorias únicas de hinos, ordenadas alfabeticamente e normalizadas."""
        if self._categorias_cache is not None:
            return list(self._categorias_cache)

        conn = await self.db_connection.get_connection()
        query = """
            SELECT DISTINCT categoria 
            FROM hino 
            WHERE categoria IS NOT NULL AND categoria != ''
            ORDER BY categoria ASC;
        """
        async with conn.execute(query) as cursor:
            rows = await cursor.fetchall()
        categorias = [
            unicodedata.normalize("NFC", str(row["categoria"])) for row in rows
        ]
        self._categorias_cache = categorias
        return list(categorias)

    async def get_temas(self) -> list[str]:
        """Retorna todos os temas únicos do banco, ordenados alfabeticamente e normalizados."""
        if self._temas_cache is not None:
            return list(self._temas_cache)

        conn = await self.db_connection.get_connection()
        query = """
            SELECT DISTINCT t.nome 
            FROM tema t
            ORDER BY t.nome ASC;
        """
        try:
            async with conn.execute(query) as cursor:
                rows = await cursor.fetchall()
            temas = [unicodedata.normalize("NFC", str(row["nome"])) for row in rows]
            self._temas_cache = temas
            return list(temas)
        except Exception:
            return []

    async def search_by_categoria(self, categoria: str) -> list[Hino]:
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
        return [self._row_to_hino_summary(row) for row in rows]

    async def search_by_tema(self, tema: str) -> list[Hino]:
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
            return [self._row_to_hino_summary(row) for row in rows]
        except Exception:
            return []

    async def get_metadados_relacionados(self, hino_id: int) -> dict[str, list[str]]:
        """
        Consulta as tabelas de junção 'hino_tema'/'tema' e 'hino_texto'/'texto_biblico'
        retornando os temas e referências bíblicas associadas ao hino.
        Utiliza cache LRU em memória limitado a 50 itens para poupar RAM.
        """
        if hino_id in self._metadados_cache:
            return self._metadados_cache[hino_id]

        conn = await self.db_connection.get_connection()

        # Consulta Temas Relacionados
        query_temas = """
            SELECT t.nome 
            FROM tema t
            INNER JOIN hino_tema ht ON t.id = ht.tema_id
            WHERE ht.hino_id = ?;
        """
        temas: list[str] = []
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
        textos: list[str] = []
        try:
            async with conn.execute(query_textos, (hino_id,)) as cursor:
                rows = await cursor.fetchall()
                textos = [str(r["referencia"]) for r in rows if r["referencia"]]
        except Exception:
            textos = []

        result = {
            "temas": temas,
            "textos_biblicos": textos,
        }
        if len(self._metadados_cache) >= 50:
            first_key = next(iter(self._metadados_cache))
            del self._metadados_cache[first_key]
        self._metadados_cache[hino_id] = result
        return result
