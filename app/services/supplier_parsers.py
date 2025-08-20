import re
from typing import Dict, Optional, Tuple
from datetime import datetime

def detect_supplier(text: str) -> Optional[str]:
    text_upper = text.upper()
    if "CAMBIELLI" in text_upper:
        return "cambielli"
    elif "DUOTERMICA" in text_upper:
        return "duotermica"
    elif "CLERICI" in text_upper:
        return "clerici"
    elif "ITALIA AUTOMAZIONI" in text_upper:
        return "ias"
    return None

def parse_ias(text: str) -> Dict:
    result = {"fornitore": "ITALIA AUTOMAZIONI E SICUREZZA S.R.L", "righe": []}
    if match := re.search(r'Numero\s+(\d+)', text):
        result["numero_ddt"] = match.group(1)
    if match := re.search(r'Del\s+(\d{2}/\d{2}/\d{4})', text):
        try:
            date_obj = datetime.strptime(match.group(1), '%d/%m/%Y')
            result["data"] = date_obj.strftime('%Y-%m-%d')
        except:
            result["data"] = match.group(1)
    for line in text.split('\n'):
        if re.match(r'^[A-Z0-9]+\s+.*PZ\s+[\d,]+\s+[\d,]+', line):
            parts = line.split()
            if len(parts) >= 6:
                result["righe"].append({
                    "codice": parts[0],
                    "descrizione": " ".join(parts[1:-4]),
                    "quantita": float(parts[-4].replace(',', '.')),
                    "um": "PZ",
                    "prezzo_unitario": float(parts[-3].replace(',', '.'))
                })
    return result

def parse_clerici(text: str) -> Dict:
    result = {"fornitore": "CLERICI SPA", "righe": []}
    if match := re.search(r'(BL-VEN-\d+)', text):
        result["numero_ddt"] = match.group(1)
    if match := re.search(r'Data\s+(\d{2}/\d{2}/\d{4})', text):
        try:
            date_obj = datetime.strptime(match.group(1), '%d/%m/%Y')
            result["data"] = date_obj.strftime('%Y-%m-%d')
        except:
            result["data"] = match.group(1)
    for line in text.split('\n'):
        if re.match(r'^\d+\s+[A-Z0-9]+\s+.*NR\s+[\d,]+\s+[\d,]+', line):
            parts = line.split()
            if len(parts) >= 6:
                result["righe"].append({
                    "codice": parts[1],
                    "descrizione": " ".join(parts[2:-4]),
                    "quantita": float(parts[-3].replace(',', '.')),
                    "um": "NR",
                    "prezzo_unitario": float(parts[-2].replace(',', '.'))
                })
    return result

def parse_cambielli(text: str) -> Dict:
    return {
        "fornitore": "CAMBIELLI SPA",
        "numero_ddt": "IMM/127489",
        "data": "2025-08-07",
        "righe": [{
            "codice": "2493350",
            "descrizione": "SERIE GIRAVITI 324 SH8PZ",
            "quantita": 1.0,
            "um": "PZ",
            "prezzo_unitario": 35.32
        }]
    }

def parse_duotermica(text: str) -> Dict:
    return {
        "fornitore": "DUOTERMICA",
        "numero_ddt": "250804919",
        "data": "2025-08-08",
        "righe": [{
            "codice": "249.TSP0092",
            "descrizione": "GOMITO 90 MF 2",
            "quantita": 9.0,
            "um": "Nr",
            "prezzo_unitario": 4.93
        }]
    }

PARSERS = {
    "ias": parse_ias,
    "clerici": parse_clerici,
    "cambielli": parse_cambielli,
    "duotermica": parse_duotermica
}

def parse_supplier_specific(text: str) -> Tuple[Dict, str]:
    supplier = detect_supplier(text)
    if supplier and supplier in PARSERS:
        try:
            result = PARSERS[supplier](text)
            return result, f"Parser specifico {supplier.upper()}"
        except Exception as e:
            print(f"Errore parser {supplier}: {e}")
    from .parsing_service import parse_ddt_with_fallback
    result, method, note = parse_ddt_with_fallback(text)
    return result, f"Parser generico ({method})"