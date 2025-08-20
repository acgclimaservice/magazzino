import re

# Leggi il JS
with open('app/static/js/pages/ddt-import.js', 'r') as f:
    content = f.read()

# Aggiungi gestione dei nuovi campi nella funzione di popolamento
old_populate = r'(document\\.getElementById\\(\\'fld-fornitore\\'\\)\\.value = previewState\\.fornitore \\|\\| \\'\\';)'
new_populate = r'''\\1
    
    // Popola numero e data DDT fornitore
    if (previewState.numero) {
        document.getElementById('fld-numero-ddt').value = previewState.numero;
    }
    if (previewState.data) {
        // Converti da YYYY-MM-DD a formato campo date
        document.getElementById('fld-data-ddt').value = previewState.data;
    }'''

content = re.sub(old_populate, new_populate, content)

# Aggiungi i campi al payload di conferma
old_payload = r'(const payload = \\{[^}]*fornitore: fornitore,)'
new_payload = r'''\\1
                numero_ddt_fornitore: document.getElementById('fld-numero-ddt')?.value?.trim(),
                data_ddt_fornitore: document.getElementById('fld-data-ddt')?.value,'''

content = re.sub(old_payload, new_payload, content)

with open('app/static/js/pages/ddt-import.js', 'w') as f:
    f.write(content)
    
print("✓ JavaScript aggiornato")
