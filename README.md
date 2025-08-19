
# Magazzino Pro 1.3 — Stabilization Pack

## Cosa include
- **app.py**: ordine corretto (config → DB → blueprint), nuove rotte `/workstation` e `/import-pdf`.
- **_base.html** e tutti i **template Jinja** coerenti (niente link a `.html`, niente attributi corrotti).
- **Error templates** `templates/errors/404.html`, `templates/errors/500.html`.
- **Workstation AI** integrata (template + `static/js/workstation.js`).
- **JS comuni**: `static/js/app.js` (toast, fetchJson, debounce, formatEuro) e `static/js/database.js`.
- **requirements.txt**, **.env.example**.

## Avvio rapido
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate
pip install -r requirements.txt

# Variabili (PowerShell)
# $env:SECRET_KEY="..." ; $env:GEMINI_API_KEY="..."

flask --app app.py init-db
python app.py
```

Apri: `/menu` → naviga tutte le sezioni. Per la Workstation AI, imposta `GEMINI_API_KEY`.

## Note
- Rimuovi eventuali duplicati `workstation.js` fuori da `static/js`.
- Evita link hard-coded a file `.html`; usa sempre `url_for`.
