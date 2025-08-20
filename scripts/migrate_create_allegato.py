#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Crea tabella 'allegato' se non esiste (solo SQLite).

import os, re, sqlite3, sys, datetime

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
        if not table_exists(cur, "allegato"):
            ddl = """
            CREATE TABLE allegato (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              documento_id INTEGER NOT NULL REFERENCES documento(id),
              filename VARCHAR(255) NOT NULL,
              mime VARCHAR(100),
              path VARCHAR(400) NOT NULL,
              size INTEGER DEFAULT 0,
              created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
            print("[DDL] Crea tabella allegato")
            cur.executescript(ddl)
            # index su documento_id
            cur.execute("CREATE INDEX IF NOT EXISTS ix_allegato_documento_id ON allegato(documento_id);")
            conn.commit()
            print("[DONE] Tabella 'allegato' creata.")
        else:
            print("[OK] Tabella 'allegato' già presente.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
