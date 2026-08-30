#!/usr/bin/env python3
"""
Script de migração e enriquecimento do banco de dados hinario.db.
Integra os dados ricos do novo banco (letra_json, metadados em JSON, autores, video_url)
às tabelas normalizadas e relacionais necessárias para o app e suas suítes de teste.
"""

import json
import re
import shutil
import sqlite3
from pathlib import Path


def parse_autores(s: str) -> tuple[str, str]:
    """Extrai autor_letra e autor_musica a partir da string de autores."""
    if not s or not s.strip():
        return "", ""
    s_clean = s.strip()

    # Formato combinado: "Letra e Música: ..."
    if re.match(r"^Letra e M[uú]sica:\s*", s_clean, re.IGNORECASE):
        val = re.sub(
            r"^Letra e M[uú]sica:\s*", "", s_clean, flags=re.IGNORECASE
        ).strip()
        return val, val

    # Formato com separador "|"
    if "|" in s_clean:
        parts = [p.strip() for p in s_clean.split("|", 1)]
        letra, musica = "", ""
        for part in parts:
            if re.match(r"^Letra:\s*", part, re.IGNORECASE):
                letra = re.sub(r"^Letra:\s*", "", part, flags=re.IGNORECASE).strip()
            elif re.match(r"^M[uú]sica:\s*", part, re.IGNORECASE):
                musica = re.sub(
                    r"^M[uú]sica:\s*", "", part, flags=re.IGNORECASE
                ).strip()
        if letra or musica:
            return letra, musica

    # Formatos simples
    if re.match(r"^Letra:\s*", s_clean, re.IGNORECASE):
        return re.sub(r"^Letra:\s*", "", s_clean, flags=re.IGNORECASE).strip(), ""

    if re.match(r"^M[uú]sica:\s*", s_clean, re.IGNORECASE):
        return "", re.sub(r"^M[uú]sica:\s*", "", s_clean, flags=re.IGNORECASE).strip()

    return s_clean, s_clean


def json_to_plain_text(letra_json_str: str) -> str:
    """Converte a estrutura letra_json em texto puro com quebras de linha entre estrofes."""
    if not letra_json_str:
        return ""
    try:
        strophes = json.loads(letra_json_str)
        blocks = []
        for s in strophes:
            lines = s.get("strophe", [])
            if lines:
                blocks.append("\n".join(lines))
        return "\n\n".join(blocks)
    except Exception:
        return letra_json_str


def sort_key_numero(numero: str) -> tuple[float, str]:
    """Chave para ordenação numérica correta de números como 1, 587A, 587B."""
    clean = str(numero).strip()
    m = re.match(r"^(\d+)(?:[._-]?([A-Za-z0-9]+))?", clean)
    if m:
        num = float(m.group(1))
        sub = m.group(2) or ""
        sub_val = 0.0
        if sub:
            if sub.isdigit():
                sub_val = float(sub) / 10.0
            else:
                sub_val = (ord(sub[0].upper()) - ord("A") + 1) / 10.0
        return (num + sub_val, clean)
    try:
        return (float(clean), clean)
    except ValueError:
        return (99999.0, clean)


def migrate():
    base_dir = Path(__file__).resolve().parent.parent
    db_new_path = base_dir / "hinario.db"
    db_old_path = base_dir / "hinario_normalizado.db"

    print(f"[*] Iniciando migração para {db_new_path}...")

    if db_new_path.exists():
        backup_path = base_dir / "hinario.db.bak"
        shutil.copy2(db_new_path, backup_path)
        print(f"[+] Backup criado: {backup_path}")

    conn = sqlite3.connect(db_new_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS hino (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT NOT NULL UNIQUE,
            titulo TEXT NOT NULL,
            letra TEXT,
            letra_json TEXT,
            autor_letra TEXT,
            autor_musica TEXT,
            autores TEXT,
            texto_base TEXT,
            categoria TEXT,
            subcategoria TEXT,
            link_video TEXT
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS hino_tema (
            hino_id INTEGER NOT NULL,
            tema_id INTEGER NOT NULL,
            PRIMARY KEY (hino_id, tema_id),
            FOREIGN KEY (hino_id) REFERENCES hino(id) ON DELETE CASCADE,
            FOREIGN KEY (tema_id) REFERENCES tema(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS texto_biblico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referencia TEXT NOT NULL UNIQUE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS hino_texto (
            hino_id INTEGER NOT NULL,
            texto_id INTEGER NOT NULL,
            PRIMARY KEY (hino_id, texto_id),
            FOREIGN KEY (hino_id) REFERENCES hino(id) ON DELETE CASCADE,
            FOREIGN KEY (texto_id) REFERENCES texto_biblico(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS favorito (
            hino_id INTEGER PRIMARY KEY,
            data_favoritado DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hino_id) REFERENCES hino(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hino_id INTEGER NOT NULL,
            data_acesso DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hino_id) REFERENCES hino(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lista_culto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tema_gerador TEXT,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS item_lista_culto (
            lista_id INTEGER NOT NULL,
            hino_id INTEGER NOT NULL,
            ordem_execucao INTEGER NOT NULL,
            PRIMARY KEY (lista_id, hino_id),
            FOREIGN KEY (lista_id) REFERENCES lista_culto(id) ON DELETE CASCADE,
            FOREIGN KEY (hino_id) REFERENCES hino(id) ON DELETE CASCADE
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS preferencias (
            chave TEXT PRIMARY KEY,
            valor TEXT
        );
    """)

    cur.execute("""
        SELECT h.numero, h.titulo, h.letra_json, 
               m.categoria, m.subcategoria, m.texto_base, 
               m.textos_relacionados_json, m.temas_relacionados_json, 
               m.autores, m.video_url
        FROM hinos h
        LEFT JOIN metadados m ON h.numero = m.hino_numero
    """)
    rows = cur.fetchall()
    sorted_rows = sorted(rows, key=lambda r: sort_key_numero(r["numero"]))

    cur.execute("DELETE FROM hino_tema;")
    cur.execute("DELETE FROM hino_texto;")
    cur.execute("DELETE FROM hino;")
    cur.execute("DELETE FROM tema;")
    cur.execute("DELETE FROM texto_biblico;")
    cur.execute("DELETE FROM favorito;")
    cur.execute("DELETE FROM historico;")
    cur.execute("DELETE FROM item_lista_culto;")
    cur.execute("DELETE FROM lista_culto;")
    cur.execute("DELETE FROM preferencias;")
    try:
        cur.execute(
            "DELETE FROM sqlite_sequence WHERE name IN ('hino', 'tema', 'texto_biblico', 'historico', 'lista_culto');"
        )
    except Exception:
        pass

    numero_to_new_id = {}
    tema_name_to_id = {}
    texto_ref_to_id = {}

    for row in sorted_rows:
        num = str(row["numero"]).strip()
        titulo = str(row["titulo"]).strip()
        letra_json_val = row["letra_json"]
        letra_plain = json_to_plain_text(letra_json_val)
        raw_autores = row["autores"] or ""
        autor_letra, autor_musica = parse_autores(raw_autores)
        texto_base = row["texto_base"] or ""
        categoria = row["categoria"] or ""
        subcategoria = row["subcategoria"] or ""
        link_video = row["video_url"] or ""

        cur.execute(
            """
            INSERT INTO hino (
                numero, titulo, letra, letra_json, autor_letra, autor_musica, autores,
                texto_base, categoria, subcategoria, link_video
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                num,
                titulo,
                letra_plain,
                letra_json_val,
                autor_letra,
                autor_musica,
                raw_autores,
                texto_base,
                categoria,
                subcategoria,
                link_video,
            ),
        )
        new_hino_id = cur.lastrowid
        numero_to_new_id[num] = new_hino_id

        temas_json = row["temas_relacionados_json"]
        if temas_json:
            try:
                temas_list = json.loads(temas_json)
                for t_name in temas_list:
                    t_clean = t_name.strip()
                    if not t_clean:
                        continue
                    if t_clean not in tema_name_to_id:
                        cur.execute(
                            "INSERT OR IGNORE INTO tema (nome) VALUES (?)", (t_clean,)
                        )
                        cur.execute("SELECT id FROM tema WHERE nome = ?", (t_clean,))
                        t_id = cur.fetchone()["id"]
                        tema_name_to_id[t_clean] = t_id
                    else:
                        t_id = tema_name_to_id[t_clean]
                    cur.execute(
                        "INSERT OR IGNORE INTO hino_tema (hino_id, tema_id) VALUES (?, ?)",
                        (new_hino_id, t_id),
                    )
            except Exception as e:
                print(f"[!] Erro ao parsear temas do hino {num}: {e}")

        textos_json = row["textos_relacionados_json"]
        if textos_json:
            try:
                textos_list = json.loads(textos_json)
                for ref_str in textos_list:
                    ref_clean = ref_str.strip()
                    if not ref_clean:
                        continue
                    if ref_clean not in texto_ref_to_id:
                        cur.execute(
                            "INSERT OR IGNORE INTO texto_biblico (referencia) VALUES (?)",
                            (ref_clean,),
                        )
                        cur.execute(
                            "SELECT id FROM texto_biblico WHERE referencia = ?",
                            (ref_clean,),
                        )
                        ref_id = cur.fetchone()["id"]
                        texto_ref_to_id[ref_clean] = ref_id
                    else:
                        ref_id = texto_ref_to_id[ref_clean]
                    cur.execute(
                        "INSERT OR IGNORE INTO hino_texto (hino_id, texto_id) VALUES (?, ?)",
                        (new_hino_id, ref_id),
                    )
            except Exception as e:
                print(f"[!] Erro ao parsear textos bíblicos do hino {num}: {e}")

    if db_old_path.exists():
        conn_old = sqlite3.connect(db_old_path)
        conn_old.row_factory = sqlite3.Row
        cur_old = conn_old.cursor()

        old_id_to_num = {}
        try:
            cur_old.execute("SELECT id, numero FROM hino")
            for r in cur_old.fetchall():
                n_clean = str(r["numero"]).replace("_", "").strip()
                old_id_to_num[r["id"]] = n_clean
        except Exception:
            pass

        try:
            cur_old.execute("SELECT hino_id, data_favoritado FROM favorito")
            for fav in cur_old.fetchall():
                old_id = fav["hino_id"]
                num = old_id_to_num.get(old_id)
                if num and num in numero_to_new_id:
                    new_id = numero_to_new_id[num]
                    cur.execute(
                        "INSERT OR IGNORE INTO favorito (hino_id, data_favoritado) VALUES (?, ?)",
                        (new_id, fav["data_favoritado"]),
                    )
        except Exception as e:
            print(f"[!] Erro ao migrar favoritos: {e}")

        try:
            cur_old.execute("SELECT hino_id, data_acesso FROM historico")
            for hist in cur_old.fetchall():
                old_id = hist["hino_id"]
                num = old_id_to_num.get(old_id)
                if num and num in numero_to_new_id:
                    new_id = numero_to_new_id[num]
                    cur.execute(
                        "INSERT INTO historico (hino_id, data_acesso) VALUES (?, ?)",
                        (new_id, hist["data_acesso"]),
                    )
        except Exception as e:
            print(f"[!] Erro ao migrar histórico: {e}")

        try:
            cur_old.execute("SELECT id, tema_gerador, data_criacao FROM lista_culto")
            listas = cur_old.fetchall()
            for l in listas:
                cur.execute(
                    "INSERT INTO lista_culto (tema_gerador, data_criacao) VALUES (?, ?)",
                    (l["tema_gerador"], l["data_criacao"]),
                )
                new_lista_id = cur.lastrowid
                old_lista_id = l["id"]

                cur_old.execute(
                    "SELECT hino_id, ordem_execucao FROM item_lista_culto WHERE lista_id = ? ORDER BY ordem_execucao",
                    (old_lista_id,),
                )
                for item in cur_old.fetchall():
                    old_id = item["hino_id"]
                    num = old_id_to_num.get(old_id)
                    if num and num in numero_to_new_id:
                        new_id = numero_to_new_id[num]
                        cur.execute(
                            "INSERT OR IGNORE INTO item_lista_culto (lista_id, hino_id, ordem_execucao) VALUES (?, ?, ?)",
                            (new_lista_id, new_id, item["ordem_execucao"]),
                        )
        except Exception as e:
            print(f"[!] Erro ao migrar listas de culto: {e}")

        try:
            cur_old.execute("SELECT chave, valor FROM preferencias")
            for p in cur_old.fetchall():
                cur.execute(
                    "INSERT OR REPLACE INTO preferencias (chave, valor) VALUES (?, ?)",
                    (p["chave"], p["valor"]),
                )
        except Exception as e:
            print(f"[!] Erro ao migrar preferências: {e}")

        conn_old.close()

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_hino_numero ON hino(numero);",
        "CREATE INDEX IF NOT EXISTS idx_hino_titulo ON hino(titulo);",
        "CREATE INDEX IF NOT EXISTS idx_hino_categoria ON hino(categoria);",
        "CREATE INDEX IF NOT EXISTS idx_hino_subcategoria ON hino(subcategoria);",
        "CREATE INDEX IF NOT EXISTS idx_hino_tema_hino ON hino_tema(hino_id);",
        "CREATE INDEX IF NOT EXISTS idx_hino_tema_tema ON hino_tema(tema_id);",
        "CREATE INDEX IF NOT EXISTS idx_hino_texto_hino ON hino_texto(hino_id);",
        "CREATE INDEX IF NOT EXISTS idx_favorito_data ON favorito(data_favoritado DESC);",
        "CREATE INDEX IF NOT EXISTS idx_historico_hino_data ON historico(hino_id, data_acesso DESC);",
    ]
    for idx_stmt in indexes:
        cur.execute(idx_stmt)

    cur.execute("DROP TABLE IF EXISTS hino_fts;")
    cur.execute("""
        CREATE VIRTUAL TABLE hino_fts USING fts5(
            numero, titulo, letra, categoria, subcategoria, texto_base, autor_letra, autor_musica, temas, textos,
            tokenize="unicode61 remove_diacritics 2"
        );
    """)

    cur.execute("""
        INSERT INTO hino_fts(rowid, numero, titulo, letra, categoria, subcategoria, texto_base, autor_letra, autor_musica, temas, textos)
        SELECT 
            h.id, 
            COALESCE(h.numero, ""), 
            COALESCE(h.titulo, ""), 
            COALESCE(h.letra, ""), 
            COALESCE(h.categoria, ""), 
            COALESCE(h.subcategoria, ""), 
            COALESCE(h.texto_base, ""), 
            COALESCE(h.autor_letra, ""), 
            COALESCE(h.autor_musica, ""),
            COALESCE((SELECT GROUP_CONCAT(t.nome, " ") FROM hino_tema ht JOIN tema t ON ht.tema_id = t.id WHERE ht.hino_id = h.id), ""),
            COALESCE((SELECT GROUP_CONCAT(tb.referencia, " ") FROM hino_texto htx JOIN texto_biblico tb ON htx.texto_id = tb.id WHERE htx.hino_id = h.id), "")
        FROM hino h;
    """)

    conn.commit()
    conn.close()
    print("[✓] Migração concluída com sucesso!")


if __name__ == "__main__":
    migrate()
