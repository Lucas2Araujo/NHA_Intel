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
        keys = row.keys()
        return HinoComparativo(
            id=row["id"] if "id" in keys else None,
            numero_novo=(
                str(row["numero_novo"]) if row["numero_novo"] is not None else None
            ),
            numero_antigo=(
                str(row["numero_antigo"]) if row["numero_antigo"] is not None else None
            ),
            titulo_novo=(
                str(row["titulo_novo"]) if row["titulo_novo"] is not None else None
            ),
            titulo_antigo=(
                str(row["titulo_antigo"]) if row["titulo_antigo"] is not None else None
            ),
            categoria_nova=row["categoria_nova"] if "categoria_nova" in keys else None,
            categoria_antiga=(
                row["categoria_antiga"] if "categoria_antiga" in keys else None
            ),
            status_comparacao=(
                str(row["status_comparacao"])
                if "status_comparacao" in keys and row["status_comparacao"]
                else ""
            ),
            modificado=(
                int(row["modificado"])
                if "modificado" in keys and row["modificado"] is not None
                else 0
            ),
            similaridade_pct=(
                float(row["similaridade_pct"])
                if "similaridade_pct" in keys and row["similaridade_pct"] is not None
                else 0.0
            ),
            diff_texto=row["diff_texto"] if "diff_texto" in keys else None,
            diff_json=row["diff_json"] if "diff_json" in keys else None,
            resumo_alteracoes=(
                row["resumo_alteracoes"] if "resumo_alteracoes" in keys else None
            ),
            metodo_cruzamento=(
                row["metodo_cruzamento"] if "metodo_cruzamento" in keys else None
            ),
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
