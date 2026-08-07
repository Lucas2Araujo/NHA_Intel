import os
import sys
import shutil
from pathlib import Path
import aiosqlite
from typing import Optional


class DatabaseConnection:
    """
    Gerenciador de Conexão assíncrona com o banco de dados SQLite usando aiosqlite.
    Suporta conexão física em arquivo ou banco em memória (:memory:).
    """

    def __init__(self, db_path: Optional[str] = "hinario_normalizado.db"):
        self.db_path = self._resolve_db_path(db_path or "hinario_normalizado.db")
        self._connection: Optional[aiosqlite.Connection] = None

    @staticmethod
    def _resolve_db_path(db_path: str) -> str:
        """
        Resolve o caminho absoluto e gravável do banco de dados SQLite de forma robusta
        para suportar Desktop, Web, Android (serious_python/Flet) e PyInstaller.
        """
        if not db_path or db_path == ":memory:" or db_path.startswith("file:"):
            return db_path

        filename = os.path.basename(db_path) or "hinario_normalizado.db"

        # 1. Variável de ambiente (HINARIO_DB_PATH ou DB_PATH)
        env_db = os.environ.get("HINARIO_DB_PATH") or os.environ.get("DB_PATH")
        if env_db and os.path.exists(env_db):
            return str(Path(env_db).resolve())

        # 2. Caminhos candidatos onde localizar o arquivo seed pré-populado
        candidates = []

        path_input = Path(db_path)
        if path_input.is_absolute() and path_input.exists():
            candidates.append(path_input)
        elif path_input.exists():
            candidates.append(path_input.resolve())

        # Diretório raiz do projeto calculado a partir deste arquivo (src/database/connection.py)
        project_root = Path(__file__).resolve().parent.parent.parent
        module_root = project_root / filename
        candidates.append(module_root)

        # Pasta assets/ (empacotada pelo Flet build)
        assets_path = project_root / "assets" / filename
        candidates.append(assets_path)

        # FLET_APP_STORAGE_DATA — diretório de dados do app Flet no Android
        flet_storage = os.environ.get("FLET_APP_STORAGE_DATA")
        if flet_storage:
            candidates.append(Path(flet_storage) / filename)

        # PyInstaller / serious_python temp dir (_MEIPASS)
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(getattr(sys, "_MEIPASS")) / filename)

        # Diretório do executável/script principal (sys.argv[0])
        if sys.argv and sys.argv[0]:
            try:
                candidates.append(Path(sys.argv[0]).resolve().parent / filename)
            except Exception:
                pass

        # Diretório de trabalho atual (cwd)
        try:
            candidates.append(Path.cwd() / filename)
        except Exception:
            pass

        # Variáveis de ambiente com diretórios no Android
        for env_var in ["FILES_DIR", "ANDROID_PRIVATE", "PYTHON_SERVICE_ARGUMENT", "ANDROID_ARGUMENT"]:
            val = os.environ.get(env_var)
            if val:
                candidates.append(Path(val) / filename)

        # Encontra o primeiro candidato que realmente existe
        seed_path: Optional[Path] = None
        for cand in candidates:
            if cand and cand.exists() and cand.is_file():
                seed_path = cand.resolve()
                break

        # 3. Detectar ambiente Android ou diretório read-only
        is_android = (
            "ANDROID_ARGUMENT" in os.environ
            or "ANDROID_PRIVATE" in os.environ
            or "FILES_DIR" in os.environ
            or "PYTHON_SERVICE_ARGUMENT" in os.environ
            or hasattr(sys, "getandroidapilevel")
        )

        def is_writable(p: Path) -> bool:
            if p.exists():
                return os.access(p, os.W_OK)
            parent = p.parent
            return parent.exists() and os.access(parent, os.W_OK)

        def get_user_data_dir() -> Path:
            for env_var in ["FILES_DIR", "ANDROID_PRIVATE"]:
                val = os.environ.get(env_var)
                if val:
                    p = Path(val)
                    p.mkdir(parents=True, exist_ok=True)
                    return p

            if sys.platform.startswith("win"):
                base = Path(os.environ.get("APPDATA", Path.home()))
                p = base / "HinarioApp"
            elif sys.platform == "darwin":
                p = Path.home() / "Library" / "Application Support" / "HinarioApp"
            else:
                base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
                p = base / "hinario_app"

            p.mkdir(parents=True, exist_ok=True)
            return p

        # Se no Android ou se o arquivo/pasta do seed não for gravável
        if is_android or (seed_path and not is_writable(seed_path)):
            user_dir = get_user_data_dir()
            target_path = user_dir / filename

            if seed_path and not target_path.exists():
                try:
                    shutil.copy2(seed_path, target_path)
                except Exception:
                    try:
                        shutil.copyfile(seed_path, target_path)
                    except Exception:
                        pass

            if target_path.exists():
                return str(target_path)

        if seed_path:
            return str(seed_path)

        user_dir = get_user_data_dir()
        return str(user_dir / filename)

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
