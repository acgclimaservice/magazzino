import re

with open('app/services/parsing_service.py', 'r') as f:
    content = f.read()

# Trova la funzione di conversione data nel fallback parser
old_date = r'(data = f"{m\\.group\\(3\\)}-{m\\.group\\(2\\)}-{m\\.group\\(1\\)}")'
new_date = r'''# Mantieni formato DD/MM/YYYY per l'utente
                data = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"'''

content = re.sub(old_date, new_date, content)

with open('app/services/parsing_service.py', 'w') as f:
    f.write(content)
    
print("✓ Parser aggiornato per formato data italiano")
