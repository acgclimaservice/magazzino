content = '''  <!-- STEP 2: Editable Meta -->
  <div id="meta-box" class="hidden grid md:grid-cols-3 gap-4 text-sm">
    <div class="md:col-span-2">
      <label class="block text-gray-600 mb-1">Fornitore</label>
      <input id="fld-fornitore" type="text" class="border rounded-md p-2 w-full">
    </div>
    <div>
      <label class="block text-gray-600 mb-1">Numero DDT Fornitore</label>
      <input id="fld-numero-ddt" type="text" class="border rounded-md p-2 w-full" placeholder="N. DDT fornitore">
    </div>
    <div>
      <label class="block text-gray-600 mb-1">Data DDT</label>
      <input id="fld-data-ddt" type="date" class="border rounded-md p-2 w-full">
    </div>
    <div>
      <label class="block text-gray-600 mb-1">Magazzino di Destinazione</label>
      <select id="sel-magazzino" class="border rounded-md p-2 w-full"></select>
    </div>
    <div>
      <label class="block text-gray-600 mb-1">Commessa (Cliente)</label>
      <select id="sel-commessa" class="border rounded-md p-2 w-full"></select>
    </div>
  </div>'''

with open('app/templates/import_pdf.html', 'r') as f:
    template = f.read()

# Sostituisci da "STEP 2" fino alla chiusura del div
import re
pattern = r'<!-- STEP 2: Editable Meta -->.*?</div>\\s*</div>'
template = re.sub(pattern, content, template, flags=re.DOTALL)

with open('app/templates/import_pdf.html', 'w') as f:
    f.write(template)
    
print("✓ Template corretto")
