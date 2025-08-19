#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Script di migrazione per aggiungere colonne a 'articolo' su SQLite e creare indice.
# Colonne:
# - codice_fornitore VARCHAR(50)
# - codice_produttore VARCHAR(50)
# - qta_riordino NUMERIC(14,3) DEFAULT 0

import os, re, sqlite3, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(ROOT, os.pardir))

def read_env_sqlite_uri():
    env_path = os.path.join(PROJECT_ROOT, ".env")
    uri = None
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("SQLALCHEMY_DATABASE_URI"):
                    try:
                        _, val = line.split("=", 1)
                        uri = val.strip()
                    except ValueError:
                        pass
                    break
    if not uri:
        uri = "sqlite:///magazzino.db"
    if not uri.lower().startswith("sqlite"):
        return None, "Solo SQLite supportato da questo script. URI attuale: %s" % uri
    m = re.match(r"sqlite:(?P<slashes>/{2,})(?P<path>.*)", uri, flags=re.I)
    if not m:
        return None, "URI SQLite non riconosciuto: %s" % uri
    path = m.group("path")
    if m.group("slashes") == "////":  # absolute
        db_path = "/" + path if not path.startswith("/") else path
    else:  # '///' relative to project root
        db_path = os.path.join(PROJECT_ROOT, path)
    db_path = os.path.normpath(db_path)
    return db_path, None

def table_exists(cur, name):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (name,))
    return cur.fetchone() is not None

def column_names(cur, table):
    cur.execute(f"PRAGMA table_info({table});")
    return [row[1] for row in cur.fetchall()]

def index_names(cur, table):
    cur.execute(f"PRAGMA index_list({table});")
    return [row[1] for row in cur.fetchall()]

def main():
    db_path, err = read_env_sqlite_uri()
    if err:
        print("[ERRORE]", err)
        sys.exit(2)
    print("[INFO] Database:", db_path)
    if not os.path.exists(db_path):
        print("[WARN] DB non trovato. Nulla da migrare.")
        sys.exit(0)

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        if not table_exists(cur, "articolo"):
            print("[WARN] Tabella 'articolo' non presente. Nulla da migrare.")
            return

        cols = column_names(cur, "articolo")
        planned = [
            ("codice_fornitore", "VARCHAR(50)"),
            ("codice_produttore", "VARCHAR(50)"),
            ("qta_riordino", "NUMERIC(14,3) DEFAULT 0")
        ]
        for col, ddl in planned:
            if col not in cols:
                sql = f"ALTER TABLE articolo ADD COLUMN {col} {ddl};"
                print("[DDL]", sql)
                cur.execute(sql)
            else:
                print(f"[OK] Colonna già presente: {col}")

        # indice su codice_fornitore
        idxs = index_names(cur, "articolo")
        if "ix_articolo_codice_fornitore" not in idxs and "idx_articolo_codice_fornitore" not in idxs:
            sql = "CREATE INDEX IF NOT EXISTS ix_articolo_codice_fornitore ON articolo(codice_fornitore);"
            print("[DDL]", sql)
            cur.execute(sql)
        else:
            print("[OK] Indice già presente su codice_fornitore")

        conn.commit()
        print("[DONE] Migrazione completata con successo.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
