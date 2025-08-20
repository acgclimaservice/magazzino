import re
from typing import Dict, Any, Tuple

def extract_basic_info(text: str) -> Dict[str, Any]:
    """Estrazione base con fallback garantito"""
    
    # Trova fornitore
    fornitore = "FORNITORE DA INSERIRE"
    for line in text.split('\\n')[:30]:
        if any(x in line.upper() for x in ['SRL', 'SPA', 'S.R.L', 'S.P.A']):
            fornitore = line.strip()
            break
    
    # Crea almeno una riga
    righe = [{
        "codice": "ART001",
        "descrizione": "Articolo da completare",
        "quantità": 1,
        "um": "PZ",
        "prezzo_unitario": 0
    }]
    
    return {
        "fornitore": fornitore,
        "righe": righe
    }
