import os
import sqlite3

def test_database_file_exists():
    """Controlla che il DB locale esista"""
    assert os.path.exists("magazzino.db")

def test_database_connection():
    """Tenta di aprire il DB"""
    conn = sqlite3.connect("magazzino.db")
    conn.execute("SELECT 1")  # query banale
    conn.close()
