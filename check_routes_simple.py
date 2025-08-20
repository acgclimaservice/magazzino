#!/usr/bin/env python3

# Controllo manuale degli endpoint senza importare l'app
import os
import re

def find_routes_in_file(filepath):
    """Trova tutti gli endpoint definiti in un file"""
    routes = []
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines, 1):
        # Cerca decoratori di route
        if re.search(r'@\w+\.(route|get|post|put|delete)', line):
            # Estrai l'URL
            url_match = re.search(r'["\']([^"\']+)["\']', line)
            if url_match:
                url = url_match.group(1)
                # Cerca il nome della funzione nella riga successiva
                if i < len(lines):
                    func_match = re.search(r'def (\w+)', lines[i])
                    if func_match:
                        func_name = func_match.group(1)
                        routes.append((url, func_name, os.path.basename(filepath)))
    return routes

# Scannerizza tutti i file blueprint
blueprint_dir = 'app/blueprints'
all_routes = []

for filename in os.listdir(blueprint_dir):
    if filename.endswith('.py') and filename != '__init__.py':
        filepath = os.path.join(blueprint_dir, filename)
        routes = find_routes_in_file(filepath)
        all_routes.extend(routes)

# Ordina per URL
all_routes.sort()

# Trova duplicati
from collections import defaultdict
url_to_routes = defaultdict(list)

for url, func_name, filename in all_routes:
    url_to_routes[url].append((func_name, filename))

print("=== CONTROLLO ENDPOINT DUPLICATI ===")
print(f"Totale endpoint trovati: {len(all_routes)}")
print()

duplicates_found = False
for url, routes in url_to_routes.items():
    if len(routes) > 1:
        print(f"🚨 DUPLICATO: {url}")
        for func_name, filename in routes:
            print(f"   -> {func_name}() in {filename}")
        print()
        duplicates_found = True
    else:
        func_name, filename = routes[0]
        print(f"✅ {url} -> {func_name}() in {filename}")

if not duplicates_found:
    print("\n🎉 Nessun duplicato trovato!")
else:
    print("\n🔧 Per maggiori dettagli su un duplicato:")
    print("   grep -rn 'ENDPOINT_URL' app/blueprints/")
