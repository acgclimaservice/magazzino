import re
from typing import Dict, Any, Tuple

def parse_ddt_with_fallback(raw_text: str) -> Tuple[Dict[str, Any], str, str]:
    """Parser migliorato con fallback più robusto"""
    
    # Estrai fornitore
    fornitore = None
    lines = raw_text.split('\\n')
    for line in lines[:20]:  # Cerca nelle prime 20 righe
        if any(x in line.upper() for x in ['SRL', 'SPA', 'S.R.L.', 'S.P.A.']):
            fornitore = line.strip()
            break
    
    # Pattern più flessibili per le righe
    righe = []
    patterns = [
        # Pattern 1: codice descrizione quantità prezzo
        r'([A-Z0-9]{3,}[\\w\\-/.]*)\\s+(.+?)\\s+(\\d+[,.]?\\d*)\\s+(\\d+[,.]?\\d*)',
        # Pattern 2: solo codice e descrizione
        r'([A-Z0-9]{3,}[\\w\\-/.]*)\\s+(.+?)$',
    ]
    
    for line in lines:
        line = line.strip()
        if len(line) < 10:
            continue
            
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                groups = match.groups()
                riga = {
                    "codice": groups[0] if len(groups) > 0 else "",
                    "descrizione": groups[1] if len(groups) > 1 else "",
                    "quantità": float((groups[2] if len(groups) > 2 else "1").replace(',', '.')),
                    "um": "PZ",
                    "prezzo_unitario": float((groups[3] if len(groups) > 3 else "0").replace(',', '.'))
                }
                
                # Filtra righe non valide
                if riga["descrizione"] and len(riga["descrizione"]) > 3:
                    righe.append(riga)
                    break
    
    # Se non trova righe, crea almeno una riga di default
    if not righe:
        righe = [{
            "codice": "MANUALE001",
            "descrizione": "Articolo da definire manualmente",
            "quantità": 1.0,
            "um": "PZ",
            "prezzo_unitario": 0.0
        }]
    
    return {
        "fornitore": fornitore or "FORNITORE DA INSERIRE",
        "righe": righe
    }, "fallback", f"Trovate {len(righe)} righe"
