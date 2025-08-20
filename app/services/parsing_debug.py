import json
from flask import current_app

def debug_parse_result(raw_text, parsed_data):
    """Debug helper per capire cosa viene estratto"""
    debug_info = {
        "text_length": len(raw_text),
        "first_500_chars": raw_text[:500],
        "parsed_fornitore": parsed_data.get("fornitore"),
        "parsed_righe_count": len(parsed_data.get("righe", [])),
        "parsed_data": parsed_data
    }
    
    # Salva debug info
    with open('/tmp/ddt_debug.json', 'w') as f:
        json.dump(debug_info, f, indent=2, default=str)
    
    return debug_info
