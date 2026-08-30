import os
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any

import aiosqlite

DEFAULT_DB_NAME: str = "hinario.db"


def _is_single_threaded_env() -> bool:
    """Detecta se o runtime atual não suporta threads do SO (ex: Pyodide, WASM, Emscripten)."""
    if sys.platform in ("emscripten", "wasi"):
        return True
    if "PYODIDE" in os.environ or "PYODIDE_ROOT" in os.environ:
        return True
    return False


class _AsyncSqliteCompatCursor:
    """
    Cursor assíncrono compatível baseado em sqlite3 síncrono.
    Permite uso tanto via 'await conn.execute(...)' quanto via 'async with conn.execute(...) as cur:'
    sem necessidade de threads no sistema operacional (WebAssembly / Pyodide).
    """

    def __init__(self, raw_cursor: sqlite3.Cursor):
        self._raw = raw_cursor

    def __await__(self):
        async def _resolve():
            return self

        return _resolve().__await__()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def fetchone(self) -> Any | None:
        return self._raw.fetchone()

    async def fetchall(self) -> list[Any]:
        return self._raw.fetchall()

    async def fetchmany(self, size: int | None = None) -> list[Any]:
        if size is not None:
            return self._raw.fetchmany(size)
        return self._raw.fetchmany()

    @property
    def lastrowid(self) -> int | None:
        return self._raw.lastrowid

    @property
    def rowcount(self) -> int:
        return self._raw.rowcount

    @property
    def description(self) -> Any:
        return self._raw.description

    async def close(self) -> None:
        try:
            self._raw.close()
        except Exception:
            pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        row = self._raw.fetchone()
        if row is None:
            raise StopAsyncIteration
        return row


class _AsyncSqliteCompatConnection:
    """
    Conexão assíncrona compatível baseada em sqlite3 síncrono.
    Provê a mesma interface do aiosqlite.Connection para ambientes sem suporte a threads.
    """

    def __init__(self, raw_conn: sqlite3.Connection):
        self._raw = raw_conn

    @property
    def row_factory(self) -> Any:
        return self._raw.row_factory

    @row_factory.setter
    def row_factory(self, val: Any) -> None:
        self._raw.row_factory = val

    @property
    def total_changes(self) -> int:
        return self._raw.total_changes

    def execute(self, sql: str, parameters: Any = ()) -> _AsyncSqliteCompatCursor:
        if parameters:
            raw_cur = self._raw.execute(sql, parameters)
        else:
            raw_cur = self._raw.execute(sql)
        return _AsyncSqliteCompatCursor(raw_cur)

    def executemany(self, sql: str, seq_of_parameters: Any) -> _AsyncSqliteCompatCursor:
        raw_cur = self._raw.executemany(sql, seq_of_parameters)
        return _AsyncSqliteCompatCursor(raw_cur)

    def executescript(self, sql_script: str) -> _AsyncSqliteCompatCursor:
        raw_cur = self._raw.executescript(sql_script)
        return _AsyncSqliteCompatCursor(raw_cur)

    async def commit(self) -> None:
        self._raw.commit()

    async def rollback(self) -> None:
        self._raw.rollback()

    async def close(self) -> None:
        try:
            self._raw.close()
        except Exception:
            pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class DatabaseConnection:
    """
    Gerenciador de Conexão assíncrona com o banco de dados SQLite usando aiosqlite.
    Suporta conexão física em arquivo ou banco em memória (:memory:).
    """

    def __init__(self, db_path: str | None = DEFAULT_DB_NAME, read_only: bool = False):
        self.db_path = self._resolve_db_path(db_path or DEFAULT_DB_NAME)
        self.read_only = read_only
        self._connection: aiosqlite.Connection | None = None

    @staticmethod
    def _resolve_env_db_path() -> str | None:
        """Verifica se há caminho configurado via variável de ambiente."""
        env_db = os.environ.get("HINARIO_DB_PATH") or os.environ.get("DB_PATH")
        if env_db and os.path.exists(env_db):
            return str(Path(env_db).resolve())
        return None

    @staticmethod
    def _gather_env_candidates(filename: str) -> list[Path]:
        """Coleta caminhos candidatos baseados em variáveis de ambiente."""
        candidates: list[Path] = []
        env_vars = [
            "FLET_APP_STORAGE_DATA",
            "FILES_DIR",
            "ANDROID_PRIVATE",
            "PYTHON_SERVICE_ARGUMENT",
            "ANDROID_ARGUMENT",
        ]
        for env_var in env_vars:
            val = os.environ.get(env_var)
            if val:
                path_val = Path(val)
                candidates.append(path_val / filename)
                candidates.append(path_val / "assets" / filename)
        return candidates

    @staticmethod
    def _gather_sys_path_candidates(filename: str) -> list[Path]:
        """Coleta caminhos candidatos a partir dos diretórios em sys.path."""
        candidates: list[Path] = []
        for p in sys.path:
            if not p:
                continue
            try:
                base = Path(p)
                candidates.append(base / filename)
                candidates.append(base / "assets" / filename)
            except Exception:
                pass
        return candidates

    @staticmethod
    def _gather_sys_candidates(filename: str) -> list[Path]:
        """Coleta caminhos candidatos baseados em sys e diretório de trabalho atual."""
        candidates: list[Path] = []
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / filename)

        if sys.argv and sys.argv[0]:
            try:
                candidates.append(Path(sys.argv[0]).resolve().parent / filename)
            except Exception:
                pass

        try:
            candidates.append(Path.cwd() / filename)
        except Exception:
            pass

        candidates.extend(DatabaseConnection._gather_sys_path_candidates(filename))
        return candidates

    @staticmethod
    def _gather_seed_candidates(db_path: str, filename: str) -> list[Path]:
        """Coleta caminhos candidatos para localizar o arquivo seed do banco de dados."""
        candidates: list[Path] = []

        path_input = Path(db_path)
        if path_input.is_absolute() and path_input.exists():
            candidates.append(path_input)
        elif path_input.exists():
            candidates.append(path_input.resolve())

        project_root = Path(__file__).resolve().parent.parent.parent
        candidates.append(project_root / filename)
        candidates.append(project_root / "assets" / filename)

        candidates.extend(DatabaseConnection._gather_env_candidates(filename))
        candidates.extend(DatabaseConnection._gather_sys_candidates(filename))

        return candidates

    @staticmethod
    def _find_seed_path(candidates: list[Path]) -> Path | None:
        """Retorna o primeiro arquivo seed candidato existente em disco."""
        for cand in candidates:
            try:
                if cand and cand.exists() and cand.is_file():
                    return cand.resolve()
            except Exception:
                pass
        return None

    @staticmethod
    def _is_android_environment() -> bool:
        """Detecta se a execução ocorre em ambiente Android / Serious Python."""
        return (
            "ANDROID_ARGUMENT" in os.environ
            or "ANDROID_PRIVATE" in os.environ
            or "FILES_DIR" in os.environ
            or "PYTHON_SERVICE_ARGUMENT" in os.environ
            or "FLET_APP_STORAGE_DATA" in os.environ
            or hasattr(sys, "getandroidapilevel")
            or "android" in sys.platform.lower()
        )

    @staticmethod
    def _is_writable(p: Path) -> bool:
        """Verifica se um caminho ou seu diretório pai é gravável."""
        try:
            if p.exists():
                return os.access(p, os.W_OK)
            parent = p.parent
            return parent.exists() and os.access(parent, os.W_OK)
        except Exception:
            return False

    @staticmethod
    def _get_platform_user_dir() -> Path | None:
        """Retorna o diretório de dados do usuário por plataforma desktop/OS."""
        import tempfile

        try:
            if sys.platform.startswith("win"):
                base = Path(os.environ.get("APPDATA", Path.home()))
                p = base / "HinarioApp"
            elif sys.platform == "darwin":
                p = Path.home() / "Library" / "Application Support" / "HinarioApp"
            else:
                home = Path.home()
                if str(home) == "/data" or not os.access(home, os.W_OK):
                    base = Path(tempfile.gettempdir())
                else:
                    base = Path(
                        os.environ.get("XDG_DATA_HOME", home / ".local" / "share")
                    )
                p = base / "hinario_app"

            p.mkdir(parents=True, exist_ok=True)
            if os.access(p, os.W_OK):
                return p
        except Exception:
            pass
        return None

    @staticmethod
    def _get_user_data_dir() -> Path:
        """Determina o diretório gravável de dados do aplicativo."""
        import tempfile

        for env_var in ["FLET_APP_STORAGE_DATA", "FILES_DIR", "ANDROID_PRIVATE"]:
            val = os.environ.get(env_var)
            if val:
                p = Path(val)
                try:
                    p.mkdir(parents=True, exist_ok=True)
                    if os.access(p, os.W_OK):
                        return p
                except Exception:
                    pass

        platform_dir = DatabaseConnection._get_platform_user_dir()
        if platform_dir:
            return platform_dir

        p = Path(tempfile.gettempdir()) / "hinario_app"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def _copy_seed_file(seed_path: Path, target_path: Path) -> None:
        """Copia o arquivo seed para o destino com fallback de método de cópia."""
        try:
            shutil.copy2(seed_path, target_path)
        except Exception:
            try:
                shutil.copyfile(seed_path, target_path)
            except Exception:
                pass

    @staticmethod
    def _resolve_db_path(db_path: str) -> str:
        """
        Resolve o caminho absoluto e gravável do banco de dados SQLite de forma robusta
        para suportar Desktop, Web, Android (serious_python/Flet) e PyInstaller.
        """
        if not db_path or db_path == ":memory:" or db_path.startswith("file:"):
            return db_path

        env_override = DatabaseConnection._resolve_env_db_path()
        if env_override:
            return env_override

        filename = os.path.basename(db_path) or DEFAULT_DB_NAME
        candidates = DatabaseConnection._gather_seed_candidates(db_path, filename)
        seed_path = DatabaseConnection._find_seed_path(candidates)

        is_android = DatabaseConnection._is_android_environment()

        # Se no Android ou se o arquivo/pasta do seed não for gravável
        if is_android or (seed_path and not DatabaseConnection._is_writable(seed_path)):
            user_dir = DatabaseConnection._get_user_data_dir()
            target_path = user_dir / filename

            if seed_path and not target_path.exists():
                DatabaseConnection._copy_seed_file(seed_path, target_path)

            if target_path.exists():
                return str(target_path)

        if seed_path:
            return str(seed_path)

        user_dir = DatabaseConnection._get_user_data_dir()
        return str(user_dir / filename)

    def _create_compat_connection(self) -> _AsyncSqliteCompatConnection:
        """Cria uma conexão assíncrona compatível via sqlite3 nativo sem criar threads de SO."""
        if self.read_only:
            try:
                raw_conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            except Exception:
                raw_conn = sqlite3.connect(self.db_path)
        else:
            raw_conn = sqlite3.connect(self.db_path)
        raw_conn.row_factory = sqlite3.Row
        return _AsyncSqliteCompatConnection(raw_conn)

    async def get_connection(
        self,
    ) -> aiosqlite.Connection | _AsyncSqliteCompatConnection:
        """
        Retorna/abre uma conexão assíncrona ativa com o SQLite.
        Configura o row_factory para acesso amigável às colunas.
        Suporta aiosqlite (Desktop/Android) e fallback transparente para sqlite3 puro (WebAssembly/Pyodide).
        Na primeira conexão, executa otimizações (índices, FTS5, limpeza).
        """
        if self._connection is None:
            if _is_single_threaded_env():
                self._connection = self._create_compat_connection()
            else:
                try:
                    self._connection = await aiosqlite.connect(self.db_path)
                    self._connection.row_factory = aiosqlite.Row
                except (RuntimeError, NotImplementedError, Exception):
                    # Se falhar ao iniciar thread (ex: Pyodide no navegador)
                    self._connection = self._create_compat_connection()

            if (
                not hasattr(self._connection, "row_factory")
                or self._connection.row_factory is None
            ):
                self._connection.row_factory = sqlite3.Row

            await self._initialize_db(self._connection)
        return self._connection

    @staticmethod
    async def _apply_pragmas(
        conn: Any, db_path: str = "", read_only: bool = False
    ) -> None:
        """
        Aplica PRAGMAs de alta velocidade adaptativos à arquitetura (ARMv7 32-bit vs 64-bit).
        - 32-bit (ARMv7 / x86): mmap_size limitado a 16MB e cache_size a 4MB (seguro contra fragmentação de memória virtual).
        - 64-bit (ARM64 / x86_64): mmap_size de 64MB e cache_size de 16MB.
        - synchronous = NORMAL e journal_mode = WAL aceleram I/O em memórias flash e eMMC lentos.
        """
        is_32bit = sys.maxsize <= 2**32
        mmap_bytes = 16 * 1024 * 1024 if is_32bit else 64 * 1024 * 1024
        cache_kib = -4000 if is_32bit else -16000

        pragmas = [
            f"PRAGMA mmap_size = {mmap_bytes};",
            f"PRAGMA cache_size = {cache_kib};",
            "PRAGMA temp_store = MEMORY;",
            "PRAGMA synchronous = NORMAL;",
        ]
        if (
            not read_only
            and db_path
            and db_path != ":memory:"
            and not db_path.startswith("file:")
        ):
            pragmas.insert(0, "PRAGMA journal_mode = WAL;")

        for pragma in pragmas:
            try:
                await conn.execute(pragma)
            except Exception:
                pass

    @staticmethod
    async def _initialize_db(conn: aiosqlite.Connection) -> None:
        """
        Executa otimizações e manutenção no banco na primeira conexão:
        1. Aplica PRAGMAs de alta velocidade
        2. Cria índices de performance (IF NOT EXISTS)
        3. Cria tabela FTS5 para busca full-text
        4. Cria tabela de preferências do usuário
        5. Limpa histórico antigo (> 90 dias)
        """
        await DatabaseConnection._apply_pragmas(conn)

        # Índices de performance
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_historico_hino_data ON historico(hino_id, data_acesso DESC);",
            "CREATE INDEX IF NOT EXISTS idx_favorito_data ON favorito(data_favoritado DESC);",
            "CREATE INDEX IF NOT EXISTS idx_hino_numero ON hino(numero);",
            "CREATE INDEX IF NOT EXISTS idx_hino_titulo ON hino(titulo);",
            "CREATE INDEX IF NOT EXISTS idx_hino_tema_hino ON hino_tema(hino_id);",
            "CREATE INDEX IF NOT EXISTS idx_hino_tema_tema ON hino_tema(tema_id);",
            "CREATE INDEX IF NOT EXISTS idx_hino_texto_hino ON hino_texto(hino_id);",
        ]
        for stmt in index_statements:
            try:
                await conn.execute(stmt)
            except Exception:
                pass

        # Tabela FTS5 para busca full-text (letra, categoria, subcategoria, texto_base, autores, temas, textos)
        try:
            async with conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='hino_fts';"
            ) as cursor:
                table_info = await cursor.fetchone()
                if table_info and "temas" not in (table_info[0] or "").lower():
                    await conn.execute("DROP TABLE IF EXISTS hino_fts;")

            await conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS hino_fts USING fts5(
                    numero, titulo, letra, categoria, subcategoria, texto_base, autor_letra, autor_musica, temas, textos,
                    tokenize='unicode61 remove_diacritics 2'
                );
            """)
            # Verifica se o FTS está vazio e precisa ser populado
            async with conn.execute("SELECT COUNT(*) FROM hino_fts;") as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0
            if count == 0:
                await conn.execute("""
                    INSERT INTO hino_fts(rowid, numero, titulo, letra, categoria, subcategoria, texto_base, autor_letra, autor_musica, temas, textos)
                    SELECT 
                        h.id, 
                        COALESCE(h.numero, ''), 
                        COALESCE(h.titulo, ''), 
                        COALESCE(h.letra, ''), 
                        COALESCE(h.categoria, ''), 
                        COALESCE(h.subcategoria, ''), 
                        COALESCE(h.texto_base, ''), 
                        COALESCE(h.autor_letra, ''), 
                        COALESCE(h.autor_musica, ''),
                        COALESCE((SELECT GROUP_CONCAT(t.nome, ' ') FROM hino_tema ht JOIN tema t ON ht.tema_id = t.id WHERE ht.hino_id = h.id), ''),
                        COALESCE((SELECT GROUP_CONCAT(tb.referencia, ' ') FROM hino_texto htx JOIN texto_biblico tb ON htx.texto_id = tb.id WHERE htx.hino_id = h.id), '')
                    FROM hino h;
                """)
        except Exception:
            pass

        # Tabela de preferências do usuário
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS preferencias (
                    chave TEXT PRIMARY KEY,
                    valor TEXT
                );
            """)
        except Exception:
            pass

        # Limpeza automática de histórico antigo (> 90 dias)
        try:
            await conn.execute(
                "DELETE FROM historico WHERE data_acesso < datetime('now', '-90 days');"
            )
        except Exception:
            pass

        await conn.commit()

    async def close(self) -> None:
        """Encerra a conexão assíncrona ativa se existir."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def __aenter__(self) -> aiosqlite.Connection:
        return await self.get_connection()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
