#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Migrazione: aggiunge colonna 'commessa_id' (INTEGER, nullable) alla tabella 'documento' su SQLite
# e crea indice opzionale per query future.

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
        return None, "URI SQLite non valido: %s" % uri
    path = m.group("path")
    if path.startswith("/"):
        db_path = path
    else:
        db_path = os.path.join(PROJECT_ROOT, path)
    return db_path, None

def column_exists(cur, table, column):
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    return column in cols

def index_exists(cur, name):
    cur.execute("PRAGMA index_list(documento)")
    idxs = [r[1] for r in cur.fetchall()]
    return name in idxs

def main():
    db_path, err = read_env_sqlite_uri()
    if err:
        print("[ERR]", err); sys.exit(1)
    print("[DB]", db_path)
    if not os.path.exists(db_path):
        print("[ERR] Database non trovato:", db_path); sys.exit(1)
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        if not column_exists(cur, "documento", "commessa_id"):
            sql = "ALTER TABLE documento ADD COLUMN commessa_id INTEGER NULL"
            print("[DDL]", sql)
            cur.execute(sql)
        else:
            print("[OK] Colonna 'commessa_id' già presente.")
        # Indice facoltativo per anno/tipo/commessa
        if not index_exists(cur, "ix_documento_commessa"):
            try:
                cur.execute("CREATE INDEX ix_documento_commessa ON documento(commessa_id)")
                print("[DDL] Creato indice ix_documento_commessa")
            except Exception as e:
                print("[WARN] Impossibile creare indice:", e)
        conn.commit()
        print("[DONE] Migrazione completata con successo.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
