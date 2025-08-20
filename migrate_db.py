import sqlite3
import os

db_path = 'magazzino.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Aggiungi colonne mancanti
    columns = [
        ('codice_fornitore', 'VARCHAR(50)'),
        ('codice_produttore', 'VARCHAR(50)'),
        ('qta_riordino', 'NUMERIC(14,3) DEFAULT 0')
    ]
    
    for col_name, col_type in columns:
        try:
            cursor.execute(f'ALTER TABLE articolo ADD COLUMN {col_name} {col_type}')
            print(f"✓ Aggiunta colonna {col_name}")
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e):
                print(f"- Colonna {col_name} già presente")
            else:
                raise
    
    cursor.execute('CREATE INDEX IF NOT EXISTS ix_articolo_codice_fornitore ON articolo (codice_fornitore)')
    conn.commit()
    print("✅ Migrazione completata!")
    
except Exception as e:
    print(f"❌ Errore: {e}")
    conn.rollback()
finally:
    conn.close()
