
from app import db
from sqlalchemy import text

with db.engine.connect() as con:
    con.execute(text("""
    CREATE TABLE IF NOT EXISTS mastrino_links(
      id INTEGER PRIMARY KEY,
      category TEXT,
      purchase_code TEXT NOT NULL UNIQUE,
      sale_code TEXT NOT NULL
    );"""))
    con.execute(text("""
    CREATE TABLE IF NOT EXISTS mastrino_overrides(
      id INTEGER PRIMARY KEY,
      article_code TEXT NOT NULL,
      purchase_code TEXT,
      sale_code TEXT NOT NULL,
      reason TEXT,
      created_at TEXT
    );"""))
    con.execute(text("""
    CREATE TABLE IF NOT EXISTS stock_moves(
      id INTEGER PRIMARY KEY,
      document_id INTEGER NOT NULL,
      document_type TEXT NOT NULL,
      date TEXT NOT NULL,
      sku TEXT NOT NULL,
      qty NUMERIC NOT NULL,
      uom TEXT,
      wh_from TEXT,
      wh_to TEXT,
      source_label TEXT,
      note TEXT
    );"""))
    try:
        con.execute(text("ALTER TABLE document ADD COLUMN attachment_path TEXT;"))
    except Exception:
        pass
print("DB Patch 06: OK")
