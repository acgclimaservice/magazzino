# Migrazione DB — Aggiunta colonne Articolo
Errore rilevato: `no such column: articolo.codice_fornitore`.
Significa che il DB SQLite esistente non ha ancora le nuove colonne introdotte nel codice.

## Uso rapido (Windows / PowerShell)
1. **Chiudi l'app Flask** (se in esecuzione).
2. **Backup** del DB (fortemente consigliato):
   ```powershell
   Copy-Item magazzino.db magazzino.bak
   ```
3. **Esegui la migrazione**:
   ```powershell
   python .\scripts\migrate_add_article_cols.py
   ```
   Lo script:
   - legge `SQLALCHEMY_DATABASE_URI` dal `.env` (se presente) oppure usa `sqlite:///magazzino.db`
   - aggiunge le colonne mancanti:
     - `codice_fornitore VARCHAR(50)`
     - `codice_produttore VARCHAR(50)`
     - `qta_riordino NUMERIC(14,3) DEFAULT 0`
   - crea l'indice `ix_articolo_codice_fornitore` se assente

4. **Riavvia l'app**:
   ```powershell
   python run.py
   ```

## Piano B (distruttivo) — solo test
Se sei in un ambiente di test e puoi perdere i dati:
```powershell
flask --app run.py init-db
```
Questo ricrea lo schema da zero.

## Note
- Lo script funziona **solo con SQLite** (URI `sqlite:///...`). Se usi Postgres/MySQL, fermati e dimmelo: preparo migration dedicata.
