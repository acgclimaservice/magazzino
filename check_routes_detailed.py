import os
import re

def find_routes_detailed(filepath):
    routes = []
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Pattern più sofisticato per catturare metodi HTTP
    pattern = r'@\w+\.(route|get|post|put|delete)\s*\(\s*["\']([^"\']+)["\'](?:.*?methods\s*=\s*\[([^\]]+)\])?\s*\)'
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for match in matches:
        decorator = match.group(1)
        url = match.group(2)
        methods = match.group(3) if match.group(3) else None
        
        # Determina i metodi HTTP
        if decorator == 'get':
            http_methods = 'GET'
        elif decorator == 'post':
            http_methods = 'POST'
        elif methods:
            http_methods = methods.replace('"', '').replace("'", "")
        else:
            http_methods = 'GET'
            
        # Trova la funzione successiva
        func_pattern = r'def\s+(\w+)\s*\('
        func_match = re.search(func_pattern, content[match.end():])
        func_name = func_match.group(1) if func_match else 'unknown'
        
        routes.append((url, func_name, http_methods, os.path.basename(filepath)))
    
    return routes

# Analizza tutti i blueprint
blueprint_dir = 'app/blueprints'
all_routes = []

for filename in os.listdir(blueprint_dir):
    if filename.endswith('.py') and filename != '__init__.py':
        filepath = os.path.join(blueprint_dir, filename)
        routes = find_routes_detailed(filepath)
        all_routes.extend(routes)

# Raggruppa per URL
from collections import defaultdict
url_to_routes = defaultdict(list)

for url, func_name, methods, filename in all_routes:
    url_to_routes[url].append((func_name, methods, filename))

print("=== CONTROLLO DETTAGLIATO DUPLICATI ===")
duplicates_found = False

for url, routes in url_to_routes.items():
    if len(routes) > 1:
        print(f"🚨 {url}")
        for func_name, methods, filename in routes:
            print(f"   -> {func_name}() [{methods}] in {filename}")
        
        # Verifica se sono GET/POST complementari
        methods_set = set()
        for _, methods, _ in routes:
            methods_set.update(methods.split(','))
        
        if len(routes) == 2 and 'GET' in methods_set and 'POST' in methods_set:
            print("   ✅ Probabilmente OK: GET/POST della stessa funzionalità")
        else:
            print("   ⚠️  Da verificare: duplicato reale")
        print()
        duplicates_found = True

if not duplicates_found:
    print("🎉 Nessun duplicato trovato!")
