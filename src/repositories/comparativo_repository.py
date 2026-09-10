from src.database.connection import DatabaseConnection
from src.models.comparativo import HinoComparativo


class ComparativoRepository:
    """
    Repositório assíncrono para acesso e consulta dos cruzamentos e diffs
    entre o Hinário Novo e o Hinário Antigo no banco hinario_comparativo.db.
    Garante o uso de queries parametrizadas (?) para máxima segurança e performance.
    """

    def __init__(self, db_connection: DatabaseConnection):
        self.db_connection = db_connection
        self._cache_novo: dict[str, HinoComparativo | None] = {}
        self._cache_antigo: dict[str, HinoComparativo | None] = {}

    def clear_cache(self) -> None:
        """Limpa os caches em memória."""
        self._cache_novo.clear()
        self._cache_antigo.clear()

    @staticmethod
    def _row_to_comparativo(row) -> HinoComparativo:
        data = dict(row)

        def _str_or_none(val) -> str | None:
            return str(val) if val is not None else None

        modificado_val = data.get("modificado")
        sim_val = data.get("similaridade_pct")

        return HinoComparativo(
            id=data.get("id"),
            numero_novo=_str_or_none(data.get("numero_novo")),
            numero_antigo=_str_or_none(data.get("numero_antigo")),
            titulo_novo=_str_or_none(data.get("titulo_novo")),
            titulo_antigo=_str_or_none(data.get("titulo_antigo")),
            categoria_nova=data.get("categoria_nova"),
            categoria_antiga=data.get("categoria_antiga"),
            status_comparacao=str(data.get("status_comparacao") or ""),
            modificado=int(modificado_val) if modificado_val is not None else 0,
            similaridade_pct=float(sim_val) if sim_val is not None else 0.0,
            diff_texto=data.get("diff_texto"),
            diff_json=data.get("diff_json"),
            resumo_alteracoes=data.get("resumo_alteracoes"),
            metodo_cruzamento=data.get("metodo_cruzamento"),
        )

    async def get_by_numero_novo(self, numero_novo: str) -> HinoComparativo | None:
        """
        Retorna o registro comparativo pelo número do hino no Hinário Novo.
        """
        if not numero_novo:
            return None

        num_clean = (numero_novo).strip().upper()
        if num_clean in self._cache_novo:
            return self._cache_novo[num_clean]

        conn = await self.db_connection.get_connection()
        query = """
            SELECT * 
            FROM comparativo_hinos 
            WHERE numero_novo = ? OR numero_novo = ?
            LIMIT 1;
        """
        num_with_underscore = (
            num_clean.replace("A", "_A").replace("B", "_B")
            if ("A" in num_clean or "B" in num_clean) and "_" not in num_clean
            else num_clean
        )
        async with conn.execute(query, (num_clean, num_with_underscore)) as cursor:
            row = await cursor.fetchone()

        result = self._row_to_comparativo(row) if row is not None else None
        if len(self._cache_novo) >= 40:
            first_key = next(iter(self._cache_novo))
            del self._cache_novo[first_key]
        self._cache_novo[num_clean] = result
        return result

    async def get_by_numero_antigo(self, numero_antigo: str) -> HinoComparativo | None:
        """
        Retorna o registro comparativo pelo número do hino no Hinário Antigo.
        """
        if not numero_antigo:
            return None

        num_clean = (numero_antigo).strip().upper()
        if num_clean in self._cache_antigo:
            return self._cache_antigo[num_clean]

        conn = await self.db_connection.get_connection()
        query = """
            SELECT * 
            FROM comparativo_hinos 
            WHERE numero_antigo = ? OR numero_antigo = ?
            LIMIT 1;
        """
        num_with_underscore = (
            num_clean.replace("A", "_A").replace("B", "_B")
            if ("A" in num_clean or "B" in num_clean) and "_" not in num_clean
            else num_clean
        )
        async with conn.execute(query, (num_clean, num_with_underscore)) as cursor:
            row = await cursor.fetchone()

        result = self._row_to_comparativo(row) if row is not None else None
        if len(self._cache_antigo) >= 40:
            first_key = next(iter(self._cache_antigo))
            del self._cache_antigo[first_key]
        self._cache_antigo[num_clean] = result
        return result

    async def get_all(self, limit: int = 1000) -> list[HinoComparativo]:
        """
        Retorna todos os registros comparativos ordenados pelo número novo/antigo.
        """
        conn = await self.db_connection.get_connection()
        query = """
            SELECT * 
            FROM comparativo_hinos 
            ORDER BY 
                CASE WHEN numero_novo IS NOT NULL THEN 0 ELSE 1 END,
                CAST(numero_novo AS INTEGER) ASC,
                numero_novo ASC,
                CAST(numero_antigo AS INTEGER) ASC
            LIMIT ?;
        """
        async with conn.execute(query, (limit,)) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_comparativo(row) for row in rows]

    async def search_comparativo(
        self, term: str, limit: int = 50
    ) -> list[HinoComparativo]:
        """
        Busca comparativa utilizando FTS ou correspondência por número/título.
        """
        if not term or not term.strip():
            return await self.get_all(limit=limit)

        clean_term = term.strip()
        conn = await self.db_connection.get_connection()

        # 1. Busca direta por número exato
        query_num = """
            SELECT * FROM comparativo_hinos
            WHERE numero_novo = ? OR numero_antigo = ?
            LIMIT ?;
        """
        async with conn.execute(query_num, (clean_term, clean_term, limit)) as cursor:
            rows = await cursor.fetchall()
            if rows:
                return [self._row_to_comparativo(r) for r in rows]

        # 2. Busca por FTS se tabela comparativo_fts existir
        try:
            fts_query = """
                SELECT c.* FROM comparativo_hinos c
                INNER JOIN comparativo_fts fts ON c.rowid = fts.rowid
                WHERE comparativo_fts MATCH ?
                ORDER BY rank
                LIMIT ?;
            """
            fts_term = f"{clean_term}*"
            async with conn.execute(fts_query, (fts_term, limit)) as cursor:
                rows = await cursor.fetchall()
                if rows:
                    return [self._row_to_comparativo(r) for r in rows]
        except Exception:
            pass

        # 3. Fallback LIKE
        query_like = """
            SELECT * FROM comparativo_hinos
            WHERE titulo_novo LIKE ? 
               OR titulo_antigo LIKE ?
               OR resumo_alteracoes LIKE ?
            LIMIT ?;
        """
        pattern = f"%{clean_term}%"
        async with conn.execute(
            query_like, (pattern, pattern, pattern, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_comparativo(r) for r in rows]
