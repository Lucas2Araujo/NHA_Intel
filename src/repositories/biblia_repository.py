import re
import unicodedata
from typing import Optional, List, Dict, Tuple, Any

from pathlib import Path

from src.database.connection import DatabaseConnection
from src.models.biblia import PassagemBiblica, Versiculo


def _normalize_text(text: str) -> str:
    """Normaliza texto removendo acentuação e convertendo para minúsculas."""
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower().strip()


# Mapeamento completo de aliases, abreviações e variações dos livros bíblicos
BOOK_ALIASES: dict[str, int] = {
    "gn": 1,
    "gen": 1,
    "genesis": 1,
    "gênesis": 1,
    "ex": 2,
    "exo": 2,
    "exodo": 2,
    "êxodo": 2,
    "lv": 3,
    "lev": 3,
    "levitico": 3,
    "levítico": 3,
    "nm": 4,
    "num": 4,
    "numeros": 4,
    "números": 4,
    "dt": 5,
    "deu": 5,
    "deut": 5,
    "deuteronomio": 5,
    "deuteronômio": 5,
    "js": 6,
    "jos": 6,
    "josue": 6,
    "josué": 6,
    "jz": 7,
    "juiz": 7,
    "juizes": 7,
    "juízes": 7,
    "rt": 8,
    "rut": 8,
    "rute": 8,
    "1sm": 9,
    "1 sm": 9,
    "1sam": 9,
    "1 sam": 9,
    "1samuel": 9,
    "1 samuel": 9,
    "i samuel": 9,
    "i sm": 9,
    "1º samuel": 9,
    "1o samuel": 9,
    "2sm": 10,
    "2 sm": 10,
    "2sam": 10,
    "2 sam": 10,
    "2samuel": 10,
    "2 samuel": 10,
    "ii samuel": 10,
    "ii sm": 10,
    "2º samuel": 10,
    "2o samuel": 10,
    "1rs": 11,
    "1 rs": 11,
    "1reis": 11,
    "1 reis": 11,
    "i reis": 11,
    "i rs": 11,
    "1º reis": 11,
    "1o reis": 11,
    "2rs": 12,
    "2 rs": 12,
    "2reis": 12,
    "2 reis": 12,
    "ii reis": 12,
    "ii rs": 12,
    "2º reis": 12,
    "2o reis": 12,
    "1cr": 13,
    "1 cr": 13,
    "1cronicas": 13,
    "1 cronicas": 13,
    "1 crônicas": 13,
    "i cronicas": 13,
    "i crônicas": 13,
    "i cr": 13,
    "1º cronicas": 13,
    "1o cronicas": 13,
    "1º crônicas": 13,
    "1o crônicas": 13,
    "2cr": 14,
    "2 cr": 14,
    "2cronicas": 14,
    "2 cronicas": 14,
    "2 crônicas": 14,
    "ii cronicas": 14,
    "ii crônicas": 14,
    "ii cr": 14,
    "2º cronicas": 14,
    "2o cronicas": 14,
    "2º crônicas": 14,
    "2o crônicas": 14,
    "ed": 15,
    "esd": 15,
    "esdras": 15,
    "ne": 16,
    "nee": 16,
    "neemias": 16,
    "et": 17,
    "est": 17,
    "ester": 17,
    "jo": 18,
    "job": 18,
    "jó": 18,
    "sl": 19,
    "sal": 19,
    "salmo": 19,
    "salmos": 19,
    "pv": 20,
    "prv": 20,
    "proverbios": 20,
    "provérbios": 20,
    "proverbio": 20,
    "provérbio": 20,
    "ec": 21,
    "ecl": 21,
    "eclesiastes": 21,
    "ct": 22,
    "cant": 22,
    "cantares": 22,
    "canticos": 22,
    "cânticos": 22,
    "cantico dos canticos": 22,
    "cântico dos cânticos": 22,
    "is": 23,
    "isa": 23,
    "isaias": 23,
    "isaías": 23,
    "jr": 24,
    "jer": 24,
    "jeremias": 24,
    "lm": 25,
    "lam": 25,
    "lamentacoes": 25,
    "lamentações": 25,
    "lamentacoes de jeremias": 25,
    "lamentações de jeremias": 25,
    "ez": 26,
    "eze": 26,
    "ezequiel": 26,
    "dn": 27,
    "dan": 27,
    "daniel": 27,
    "os": 28,
    "ose": 28,
    "oseias": 28,
    "oséias": 28,
    "jl": 29,
    "joe": 29,
    "joel": 29,
    "am": 30,
    "amo": 30,
    "amos": 30,
    "amós": 30,
    "ob": 31,
    "oba": 31,
    "obadias": 31,
    "jn": 32,
    "jon": 32,
    "jonas": 32,
    "mq": 33,
    "miq": 33,
    "miqueias": 33,
    "miquéias": 33,
    "na": 34,
    "nau": 34,
    "naum": 34,
    "hc": 35,
    "hab": 35,
    "habacuque": 35,
    "habacuc": 35,
    "sf": 36,
    "sof": 36,
    "sofonias": 36,
    "ag": 37,
    "age": 37,
    "ageu": 37,
    "zc": 38,
    "zac": 38,
    "zacarias": 38,
    "ml": 39,
    "mal": 39,
    "malaquias": 39,
    "mt": 40,
    "mat": 40,
    "mateus": 40,
    "mc": 41,
    "mar": 41,
    "marcos": 41,
    "lc": 42,
    "luc": 42,
    "lucas": 42,
    "joao": 43,
    "joão": 43,
    "at": 44,
    "ato": 44,
    "atos": 44,
    "rm": 45,
    "rom": 45,
    "romanos": 45,
    "romano": 45,
    "1co": 46,
    "1 co": 46,
    "1cor": 46,
    "1 cor": 46,
    "1corintios": 46,
    "1 corintios": 46,
    "1 coríntios": 46,
    "i corintios": 46,
    "i coríntios": 46,
    "i co": 46,
    "1º corintios": 46,
    "1o corintios": 46,
    "1º coríntios": 46,
    "1o coríntios": 46,
    "2co": 47,
    "2 co": 47,
    "2cor": 47,
    "2 cor": 47,
    "2corintios": 47,
    "2 corintios": 47,
    "2 coríntios": 47,
    "ii corintios": 47,
    "ii coríntios": 47,
    "ii co": 47,
    "2º corintios": 47,
    "2o corintios": 47,
    "2º coríntios": 47,
    "2o coríntios": 47,
    "gl": 48,
    "gal": 48,
    "galatas": 48,
    "gálatas": 48,
    "ef": 49,
    "efe": 49,
    "efesios": 49,
    "efésios": 49,
    "fp": 50,
    "fil": 50,
    "filipenses": 50,
    "cl": 51,
    "col": 51,
    "colossenses": 51,
    "1ts": 52,
    "1 ts": 52,
    "1tes": 52,
    "1 tes": 52,
    "1tessalonicenses": 52,
    "1 tessalonicenses": 52,
    "i tessalonicenses": 52,
    "i ts": 52,
    "1º tessalonicenses": 52,
    "1o tessalonicenses": 52,
    "2ts": 53,
    "2 ts": 53,
    "2tes": 53,
    "2 tes": 53,
    "2tessalonicenses": 53,
    "2 tessalonicenses": 53,
    "ii tessalonicenses": 53,
    "ii ts": 53,
    "2º tessalonicenses": 53,
    "2o tessalonicenses": 53,
    "1tm": 54,
    "1 tm": 54,
    "1tim": 54,
    "1 tim": 54,
    "1timoteo": 54,
    "1 timoteo": 54,
    "1 timóteo": 54,
    "i timoteo": 54,
    "i timóteo": 54,
    "i tm": 54,
    "1º timoteo": 54,
    "1o timoteo": 54,
    "1º timóteo": 54,
    "1o timóteo": 54,
    "2tm": 55,
    "2 tm": 55,
    "2tim": 55,
    "2 tim": 55,
    "2timoteo": 55,
    "2 timoteo": 55,
    "2 timóteo": 55,
    "ii timoteo": 55,
    "ii timóteo": 55,
    "ii tm": 55,
    "2º timoteo": 55,
    "2o timoteo": 55,
    "2º timóteo": 55,
    "2o timóteo": 55,
    "tt": 56,
    "tit": 56,
    "tito": 56,
    "fm": 57,
    "flm": 57,
    "filemon": 57,
    "filemom": 57,
    "hb": 58,
    "heb": 58,
    "hebreus": 58,
    "tg": 59,
    "tia": 59,
    "tiago": 59,
    "1pe": 60,
    "1 pe": 60,
    "1ped": 60,
    "1 ped": 60,
    "1pedro": 60,
    "1 pedro": 60,
    "i pedro": 60,
    "1p": 60,
    "ip": 60,
    "1º pedro": 60,
    "1o pedro": 60,
    "2pe": 61,
    "2 pe": 61,
    "2ped": 61,
    "2 ped": 61,
    "2pedro": 61,
    "2 pedro": 61,
    "ii pedro": 61,
    "2p": 61,
    "iip": 61,
    "2º pedro": 61,
    "2o pedro": 61,
    "1jo": 62,
    "1 jo": 62,
    "1joao": 62,
    "1 joao": 62,
    "1 joão": 62,
    "i joao": 62,
    "i joão": 62,
    "1º joao": 62,
    "1o joao": 62,
    "1º joão": 62,
    "1o joão": 62,
    "2jo": 63,
    "2 jo": 63,
    "2joao": 63,
    "2 joao": 63,
    "2 joão": 63,
    "ii joao": 63,
    "ii joão": 63,
    "2º joao": 63,
    "2o joao": 63,
    "2º joão": 63,
    "2o joão": 63,
    "3jo": 64,
    "3 jo": 64,
    "3joao": 64,
    "3 joao": 64,
    "3 joão": 64,
    "iii joao": 64,
    "iii joão": 64,
    "3º joao": 64,
    "3o joao": 64,
    "3º joão": 64,
    "3o joão": 64,
    "jd": 65,
    "jud": 65,
    "judas": 65,
    "ap": 66,
    "apoc": 66,
    "apocalipse": 66,
    "revelacao": 66,
    "revelação": 66,
}

_NORMALIZED_ALIASES: dict[str, int] = {
    _normalize_text(k): v for k, v in BOOK_ALIASES.items()
}

# Livros que possuem apenas 1 capítulo
SINGLE_CHAPTER_BOOKS: set[int] = {
    31,
    57,
    63,
    64,
    65,
}  # Obadias, Filemom, 2 João, 3 João, Judas

BIBLE_VERSION_NAMES: dict[str, str] = {
    "ARA": "Almeida Revista e Atualizada",
    "NVI": "Nova Versão Internacional",
    "NTLH": "Nova Tradução na Linguagem de Hoje",
    "KJA": "King James Atualizada",
    "AS21": "Almeida Século 21",
}


class BibliaRepository:
    """
    Repositório assíncrono para consulta de textos bíblicos em bancos SQLite (ex: ARA.sqlite, NVI.sqlite).
    Suporta descoberta dinâmica de múltiplas versões da Bíblia na pasta assets/biblias e chaveamento de versões.
    Opera estritamente em modo de leitura com queries parametrizadas (?).
    """

    DEFAULT_VERSION = "ARA"

    def __init__(
        self,
        db_connection: DatabaseConnection | None = None,
        default_version: str = DEFAULT_VERSION,
    ):
        self.active_version: str = (
            (default_version or self.DEFAULT_VERSION).strip().upper()
        )
        self._connections: dict[str, DatabaseConnection] = {}
        if db_connection is not None:
            self._connections[self.active_version] = db_connection

        self._book_names: dict[str, dict[int, str]] = {}
        self._passagem_cache: dict[str, PassagemBiblica | None] = {}

    @classmethod
    def get_version_name(cls, version: str) -> str:
        """Retorna o nome completo e descritivo da versão bíblica."""
        v = (version or "").strip().upper()
        return BIBLE_VERSION_NAMES.get(v, v)

    @classmethod
    def get_available_versions_with_names(cls) -> list[tuple[str, str]]:
        """Retorna lista de tuplas (código, nome_completo) das versões disponíveis."""
        versions = cls.get_available_versions()
        return [(v, cls.get_version_name(v)) for v in versions]

    @property
    def db_connection(self) -> DatabaseConnection:
        """Retorna a conexão ativa para a versão corrente (compatibilidade legada)."""
        return self._get_connection(self.active_version)

    @db_connection.setter
    def db_connection(self, conn: DatabaseConnection) -> None:
        self._connections[self.active_version] = conn

    @staticmethod
    def get_available_versions() -> list[str]:
        """
        Descobre dinamicamente as versões da Bíblia disponíveis nos diretórios de assets e dados.
        Retorna uma lista ordenada com os nomes das versões (ex: ['ARA', 'NVI']), mantendo 'ARA' como prioritária.
        """
        versions: set[str] = set()
        module_dir = Path(__file__).resolve().parent.parent  # src
        root_dir = module_dir.parent  # project root

        candidate_dirs = [
            root_dir / "assets" / "biblias",
            root_dir / "assets",
            module_dir / "assets" / "biblias",
            module_dir / "assets",
            module_dir / "database" / "data" / "biblias",
            module_dir / "database" / "data",
            DatabaseConnection._get_user_data_dir() / "biblias",
            DatabaseConnection._get_user_data_dir(),
        ]

        ignored_prefixes = ("hinario", "test", "temp", "cache")
        valid_extensions = {".sqlite", ".db", ".sqlite3"}

        for d in candidate_dirs:
            if not d.exists() or not d.is_dir():
                continue
            try:
                for item in d.iterdir():
                    if item.is_file() and item.suffix.lower() in valid_extensions:
                        name = item.stem
                        if any(name.lower().startswith(p) for p in ignored_prefixes):
                            continue
                        if item.stat().st_size > 0:
                            versions.add(name.upper())
            except Exception:
                pass

        if not versions:
            return ["ARA"]

        sorted_versions = sorted(versions)
        if "ARA" in sorted_versions:
            sorted_versions.remove("ARA")
            sorted_versions.insert(0, "ARA")
        return sorted_versions

    def set_version(self, version: str) -> None:
        """Altera a versão bíblica ativa corrente."""
        if version and version.strip():
            self.active_version = version.strip().upper()

    def _get_connection(self, version: str | None = None) -> DatabaseConnection:
        """Obtém ou instancia a conexão com o banco SQLite da versão especificada."""
        v = (version or self.active_version or self.DEFAULT_VERSION).strip().upper()
        if v not in self._connections:
            self._connections[v] = DatabaseConnection(
                db_path=f"biblias/{v}.sqlite", read_only=True
            )
        return self._connections[v]

    def clear_cache(self) -> None:
        """Limpa os caches em memória de passagens e nomes de livros."""
        self._book_names.clear()
        self._passagem_cache.clear()

    async def close(self) -> None:
        """Encerra todas as conexões ativas com os bancos das Bíblias."""
        for conn in list(self._connections.values()):
            try:
                await conn.close()
            except Exception:
                pass
        self._connections.clear()

    async def _get_book_names(self, version: str | None = None) -> dict[int, str]:
        """Carrega e armazena em cache o mapa de id -> nome canônico dos livros da versão."""
        v = (version or self.active_version).strip().upper()
        if v not in self._book_names:
            names: dict[int, str] = {}
            try:
                conn_mgr = self._get_connection(v)
                conn = await conn_mgr.get_connection()
                query = "SELECT id, name FROM book ORDER BY id ASC;"
                async with conn.execute(query) as cursor:
                    rows = await cursor.fetchall()
                for row in rows:
                    names[int(row["id"])] = str(row["name"])
            except Exception:
                pass
            self._book_names[v] = names
        return self._book_names.get(v, {})

    @staticmethod
    def _parse_verse_range(token: str) -> list[int]:
        """Extrai intervalo de versículos 'start-end' se válido."""
        parts = token.split("-")
        if (
            len(parts) == 2
            and parts[0].strip().isdigit()
            and parts[1].strip().isdigit()
        ):
            start, end = int(parts[0].strip()), int(parts[1].strip())
            if start <= end:
                return list(range(start, end + 1))
        return []

    @classmethod
    def _parse_verse_token(cls, token: str) -> list[int]:
        """Interpreta um token numérico ou intervalo."""
        token = token.strip()
        if not token:
            return []
        if "-" in token:
            return cls._parse_verse_range(token)
        if token.isdigit():
            return [int(token)]
        return []

    @classmethod
    def _parse_verses_sequence(cls, verse_str: str) -> list[int] | None:
        """
        Interpreta expressões de versículos (ex: '16', '1-6', '1, 2', '23, 24', '1, 11-18').
        Retorna lista ordenada e única de inteiros.
        """
        if not verse_str:
            return None
        verses: list[int] = []
        for token in re.split(r"[,;]+", verse_str):
            verses.extend(cls._parse_verse_token(token))

        if not verses:
            return None
        return sorted(set(verses))

    @classmethod
    def _parse_separated_chapter_and_verses(
        cls, num_str: str
    ) -> tuple[int, list[int] | None] | None:
        """Trata referências com separador ':' ou '.' (ex: '3:16', '23:1-6')."""
        for sep in (":", "."):
            if sep in num_str:
                ch_part, _, v_part = num_str.partition(sep)
                if ch_part.strip().isdigit():
                    return int(ch_part.strip()), cls._parse_verses_sequence(
                        v_part.strip()
                    )
        return None

    @classmethod
    def _parse_single_chapter_numbers(
        cls, num_str: str
    ) -> tuple[int, list[int] | None]:
        """Trata números para livros de capítulo único (ex: Judas, Filemom)."""
        if num_str.isdigit():
            num = int(num_str)
            return 1, [num] if num > 1 else None
        return 1, cls._parse_verses_sequence(num_str)

    @classmethod
    def _parse_compound_chapter_numbers(
        cls, num_str: str
    ) -> tuple[int, list[int] | None]:
        """Trata número puro ou 'capítulo, versículos' (ex: '148', '9, 1-2')."""
        if num_str.isdigit():
            return int(num_str), None
        parts = re.split(r"[,;\s]+", num_str)
        if parts and parts[0].isdigit():
            chapter = int(parts[0])
            rest = num_str[len(parts[0]) :].lstrip(" ,;-")
            verses = cls._parse_verses_sequence(rest) if rest else None
            return chapter, verses
        return 1, None

    @classmethod
    def _parse_reference_numbers(
        cls, numbers_part: str | None, is_single_chapter: bool
    ) -> tuple[int, list[int] | None]:
        """Extrai (capítulo, versículos) a partir da string numérica da referência."""
        if not numbers_part or not numbers_part.strip():
            return 1, None

        num_str = numbers_part.strip()
        separated = cls._parse_separated_chapter_and_verses(num_str)
        if separated is not None:
            return separated

        if is_single_chapter:
            return cls._parse_single_chapter_numbers(num_str)

        return cls._parse_compound_chapter_numbers(num_str)

    def parse_referencia(self, referencia: str) -> dict | None:
        """
        Interpreta uma referência bíblica em texto livre e extrai:
        - book_id: ID numérico do livro (1 a 66)
        - book_name: Nome do livro
        - chapter: Número do capítulo
        - verses: Lista de versículos ou None (se for o capítulo completo)
        """
        if not referencia or not referencia.strip():
            return None

        raw = referencia.strip()
        # Remove anomalias de prefixo (ex: "And God SaidGênesis 2:1-3")
        raw = re.sub(r"^(?:And God Said)?\s*", "", raw, flags=re.IGNORECASE)

        # Normaliza sem acentos e trata numerais romanos (I, II, III)
        norm_raw = _normalize_text(raw)
        norm_raw = re.sub(
            r"^i{1,3}\s+", lambda m: f"{len(m.group(0).strip())} ", norm_raw
        )

        # Expressão regular para separar prefixo numérico (1, 2, 3), nome do livro e parte numérica
        m = re.match(r"^(?:([123])\s*)?([a-z]+(?:\s+[a-z]+)*)(?:\s*(\d.*))?$", norm_raw)
        if not m:
            return None

        num_prefix, book_name_raw, numbers_part = m.groups()
        book_key = f"{num_prefix or ''} {book_name_raw or ''}".strip()
        book_id = _NORMALIZED_ALIASES.get(book_key)
        if not book_id and book_name_raw:
            book_id = _NORMALIZED_ALIASES.get(book_name_raw.strip())

        if not book_id:
            return None

        is_single_chapter = book_id in SINGLE_CHAPTER_BOOKS
        chapter, verses = self._parse_reference_numbers(numbers_part, is_single_chapter)

        return {
            "book_id": book_id,
            "book_name": book_key.title(),
            "chapter": chapter,
            "verses": verses,
        }

    async def buscar_passagem(
        self, referencia: str, versao: str | None = None
    ) -> PassagemBiblica | None:
        """
        Consulta o banco de dados da Bíblia da versão especificada e retorna os versículos
        correspondentes à referência bíblica informada. Utiliza cache LRU em memória (máximo 50 itens).
        """
        if not referencia:
            return None

        clean_ref = referencia.strip()
        v = (versao or self.active_version or self.DEFAULT_VERSION).strip().upper()
        cache_key = f"{v}:{clean_ref}"

        if cache_key in self._passagem_cache:
            return self._passagem_cache[cache_key]

        parsed = self.parse_referencia(clean_ref)
        if not parsed:
            return None

        book_id = parsed["book_id"]
        chapter = parsed["chapter"]
        verses = parsed["verses"]

        book_names = await self._get_book_names(v)
        canonical_book_name = book_names.get(book_id, parsed["book_name"])

        try:
            conn_mgr = self._get_connection(v)
            conn = await conn_mgr.get_connection()

            if verses:
                placeholders = ",".join("?" * len(verses))
                query = f"""
                    SELECT verse, text 
                    FROM verse 
                    WHERE book_id = ? AND chapter = ? AND verse IN ({placeholders})
                    ORDER BY verse ASC;
                """
                params = [book_id, chapter] + verses
            else:
                query = """
                    SELECT verse, text 
                    FROM verse 
                    WHERE book_id = ? AND chapter = ?
                    ORDER BY verse ASC;
                """
                params = [book_id, chapter]

            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()

            if not rows:
                return None

            versiculos = [
                Versiculo(
                    livro=canonical_book_name,
                    capitulo=chapter,
                    numero=int(row["verse"]),
                    texto=str(row["text"]).strip(),
                )
                for row in rows
            ]

            # Formata a referência canônica final
            if verses:
                if len(verses) == 1:
                    v_str = str(verses[0])
                elif verses == list(range(verses[0], verses[-1] + 1)):
                    v_str = f"{verses[0]}-{verses[-1]}"
                else:
                    v_str = ", ".join(str(v) for v in verses)
                canonical_ref = f"{canonical_book_name} {chapter}:{v_str}"
            else:
                canonical_ref = f"{canonical_book_name} {chapter}"

            passagem = PassagemBiblica(
                referencia=canonical_ref,
                livro=canonical_book_name,
                capitulo=chapter,
                versiculos=versiculos,
            )
            if len(self._passagem_cache) >= 50:
                first_key = next(iter(self._passagem_cache))
                del self._passagem_cache[first_key]
            self._passagem_cache[cache_key] = passagem
            return passagem
        except Exception:
            return None

    async def buscar_capitulo_completo(
        self, referencia: str, versao: str | None = None
    ) -> PassagemBiblica | None:
        """
        Consulta todos os versículos do capítulo associado a uma dada referência bíblica.
        Ideal para fornecer contexto de leitura completo ao usuário.
        """
        if not referencia:
            return None

        clean_ref = referencia.strip()
        parsed = self.parse_referencia(clean_ref)
        if not parsed:
            return None

        book_id = parsed["book_id"]
        chapter = parsed["chapter"]
        v = (versao or self.active_version or self.DEFAULT_VERSION).strip().upper()
        cache_key = f"{v}:full:{book_id}:{chapter}"

        if cache_key in self._passagem_cache:
            return self._passagem_cache[cache_key]

        book_names = await self._get_book_names(v)
        canonical_book_name = book_names.get(book_id, parsed["book_name"])

        try:
            conn_mgr = self._get_connection(v)
            conn = await conn_mgr.get_connection()

            query = """
                SELECT verse, text 
                FROM verse 
                WHERE book_id = ? AND chapter = ?
                ORDER BY verse ASC;
            """
            async with conn.execute(query, (book_id, chapter)) as cursor:
                rows = await cursor.fetchall()

            if not rows:
                return None

            versiculos = [
                Versiculo(
                    livro=canonical_book_name,
                    capitulo=chapter,
                    numero=int(row["verse"]),
                    texto=str(row["text"]).strip(),
                )
                for row in rows
            ]

            passagem = PassagemBiblica(
                referencia=f"{canonical_book_name} {chapter}",
                livro=canonical_book_name,
                capitulo=chapter,
                versiculos=versiculos,
            )

            if len(self._passagem_cache) >= 50:
                first_key = next(iter(self._passagem_cache))
                del self._passagem_cache[first_key]
            self._passagem_cache[cache_key] = passagem
            return passagem
        except Exception:
            return None
