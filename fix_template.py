import re

# Leggi il template attuale
with open('app/templates/import_pdf.html', 'r') as f:
    content = f.read()

# Trova la sezione meta-box e aggiungi i campi mancanti
old_meta = r'(<div id="meta-box"[^>]*>.*?<div class="md:col-span-2">.*?</div>)'
new_meta = r'''\\1
    <div>
      <label class="block text-gray-600 mb-1">Numero DDT Fornitore</label>
      <input id="fld-numero-ddt" type="text" class="border rounded-md p-2 w-full" placeholder="N. DDT fornitore">
    </div>
    <div>
      <label class="block text-gray-600 mb-1">Data DDT</label>
      <input id="fld-data-ddt" type="date" class="border rounded-md p-2 w-full">
    </div>'''

content = re.sub(old_meta, new_meta, content, flags=re.DOTALL)

with open('app/templates/import_pdf.html', 'w') as f:
    f.write(content)
    
print("✓ Template aggiornato con numero e data DDT")
