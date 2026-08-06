import aiosqlite
from typing import Optional


class DatabaseConnection:
    """
    Gerenciador de Conexão assíncrona com o banco de dados SQLite usando aiosqlite.
    Suporta conexão física em arquivo ou banco em memória (:memory:).
    """

    def __init__(self, db_path: str = "hinario_normalizado.db"):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def get_connection(self) -> aiosqlite.Connection:
        """
        Retorna/abre uma conexão assíncrona ativa com o SQLite.
        Configura o row_factory para aiosqlite.Row para acesso amigável às colunas.
        """
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
        return self._connection

    async def close(self) -> None:
        """Encerra a conexão assíncrona ativa se existir."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def __aenter__(self) -> aiosqlite.Connection:
        return await self.get_connection()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
