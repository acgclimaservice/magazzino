with open('app.py', 'r') as f:
    content = f.read()

# Cerca e correggi la funzione import_ddt_confirm
old_func = '''@app.route("/api/import-ddt-confirm", methods=["POST"])
def import_ddt_confirm():
    try:
        payload = request.get_json(force=True)
        data_str = required(payload.get("data"), "Data")
        fornitore_nome = required(payload.get("fornitore"), "Fornitore")
        mastrino_codice = (payload.get("mastrino_codice") or "").strip()'''

new_func = '''@app.route("/api/import-ddt-confirm", methods=["POST"])
def import_ddt_confirm():
    try:
        payload = request.get_json(force=True)
        fornitore_nome = required(payload.get("fornitore"), "Fornitore")
        righe = payload.get("righe") or []
        if not righe:
            return jsonify({"ok": False, "error": "Nessuna riga fornita"}), 400'''

content = content.replace(old_func, new_func)

with open('app.py', 'w') as f:
    f.write(content)
    
print("✓ Endpoint corretto")
