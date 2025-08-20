# Leggi il file JS
with open('app/static/js/pages/ddt-import.js', 'r') as f:
    content = f.read()

# Trova e sostituisci la riga del fornitore
old_line = "document.getElementById('fld-fornitore').value = previewState.fornitore || '';"
new_block = """document.getElementById('fld-fornitore').value = previewState.fornitore || '';
    
    // Popola numero e data DDT fornitore
    if (previewState.numero) {
        document.getElementById('fld-numero-ddt').value = previewState.numero;
    }
    if (previewState.data) {
        document.getElementById('fld-data-ddt').value = previewState.data;
    }"""

content = content.replace(old_line, new_block)

# Aggiungi campi al payload
old_payload = "fornitore: fornitore,"
new_payload = """fornitore: fornitore,
                numero_ddt_fornitore: document.getElementById('fld-numero-ddt')?.value?.trim(),
                data_ddt_fornitore: document.getElementById('fld-data-ddt')?.value,"""

content = content.replace(old_payload, new_payload)

with open('app/static/js/pages/ddt-import.js', 'w') as f:
    f.write(content)
    
print("✓ JavaScript corretto")
