#!/usr/bin/env python3
"""
Gera o banco SQLite leve assets/biblia_leve.sqlite contendo apenas
os textos bíblicos referenciados nos hinos de hinario.db.
Reduz o consumo de assets de ~24 MB para ~200 KB.
"""

import os
import sqlite3
import sys
from pathlib import Path

# Adiciona o diretório raiz ao sys.path para importar os módulos da aplicação
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.repositories.biblia_repository import BibliaRepository


def generate_lightweight_bible() -> None:
    source_bible = PROJECT_ROOT / "assets" / "biblias" / "ARA.sqlite"
    if not source_bible.exists():
        source_bible = PROJECT_ROOT / "src" / "database" / "data" / "ARA.sqlite"
    if not source_bible.exists():
        print(f"[!] Banco fonte não encontrado: {source_bible}")
        sys.exit(1)

    hinario_db = PROJECT_ROOT / "assets" / "hinario.db"
    if not hinario_db.exists():
        hinario_db = PROJECT_ROOT / "src" / "database" / "data" / "hinario.db"

    dest_db = PROJECT_ROOT / "assets" / "biblia_leve.sqlite"
    print(f"[*] Fonte Bíblia: {source_bible}")
    print(f"[*] Fonte Hinário: {hinario_db}")
    print(f"[*] Destino Leve: {dest_db}")

    repo = BibliaRepository()
    conn_hinario = sqlite3.connect(str(hinario_db))
    cur_h = conn_hinario.cursor()
    cur_h.execute("SELECT referencia FROM texto_biblico ORDER BY id ASC;")
    refs = [r[0] for r in cur_h.fetchall()]
    conn_hinario.close()

    print(f"[*] Total de referências em texto_biblico: {len(refs)}")

    conn_ara = sqlite3.connect(str(source_bible))
    cur_ara = conn_ara.cursor()

    extracted_verses: dict[int, tuple] = {}
    for r in refs:
        parsed = repo.parse_referencia(r)
        if not parsed:
            continue
        b_id = parsed["book_id"]
        ch = parsed["chapter"]
        vs = parsed["verses"]
        if vs:
            for v in vs:
                cur_ara.execute(
                    "SELECT id, book_id, chapter, verse, text FROM verse WHERE book_id=? AND chapter=? AND verse=?",
                    (b_id, ch, v),
                )
                row = cur_ara.fetchone()
                if row:
                    extracted_verses[row[0]] = row
        else:
            cur_ara.execute(
                "SELECT id, book_id, chapter, verse, text FROM verse WHERE book_id=? AND chapter=?",
                (b_id, ch),
            )
            for row in cur_ara.fetchall():
                extracted_verses[row[0]] = row

    cur_ara.execute("SELECT id, name, testament_reference_id FROM book ORDER BY id ASC;")
    books = cur_ara.fetchall()
    conn_ara.close()

    print(f"[*] Total de versículos extraídos: {len(extracted_verses)}")

    if dest_db.exists():
        dest_db.unlink()

    dest = sqlite3.connect(str(dest_db))
    dest.execute(
        "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);"
    )
    dest.execute(
        "INSERT INTO metadata VALUES ('version', 'ARA'), ('type', 'lightweight_references');"
    )
    dest.execute(
        "CREATE TABLE book (id INTEGER PRIMARY KEY, name TEXT, testament_reference_id INTEGER);"
    )
    dest.execute(
        "CREATE TABLE verse (id INTEGER PRIMARY KEY, book_id INTEGER, chapter INTEGER, verse INTEGER, text TEXT);"
    )
    dest.execute(
        "CREATE INDEX idx_verse_lookup ON verse (book_id, chapter, verse);"
    )
    dest.execute(
        "CREATE INDEX idx_verse_text ON verse (text);"
    )

    dest.executemany("INSERT INTO book VALUES (?,?,?);", books)
    dest.executemany("INSERT INTO verse VALUES (?,?,?,?,?);", extracted_verses.values())
    dest.commit()
    dest.execute("VACUUM;")
    dest.close()

    size = dest_db.stat().st_size
    print(f"[+] Sucesso! {dest_db.name} criado: {size / 1024:.1f} KB ({size / (1024*1024):.2f} MB)")


if __name__ == "__main__":
    generate_lightweight_bible()

