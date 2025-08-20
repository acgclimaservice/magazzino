# Wrapper per migrazione su Windows
$ErrorActionPreference = 'Stop'
if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
  Write-Host "Attenzione: virtualenv non trovato. Provo con Python di sistema." -ForegroundColor Yellow
} else {
  . .\.venv\Scripts\Activate.ps1
}
python .\scripts\migrate_add_article_cols.py
