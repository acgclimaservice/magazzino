import sys
sys.path.insert(0, '.')

from app import create_app

app = create_app()

print("=== TUTTE LE ROUTE REGISTRATE ===")
routes = []
for rule in app.url_map.iter_rules():
    routes.append((rule.rule, rule.endpoint, ', '.join(rule.methods)))

# Ordina per URL per facilitare l'identificazione di duplicati
routes.sort(key=lambda x: x[0])

current_url = None
for url, endpoint, methods in routes:
    if url == current_url:
        print(f"🚨 POSSIBILE DUPLICATO: {url} -> {endpoint} [{methods}]")
    else:
        print(f"✅ {url} -> {endpoint} [{methods}]")
    current_url = url

print(f"\n📊 Totale route: {len(routes)}")

# Cerca duplicati esatti di URL
from collections import Counter
url_counts = Counter([route[0] for route in routes])
duplicates = {url: count for url, count in url_counts.items() if count > 1}

if duplicates:
    print("\n🚨 ENDPOINT DUPLICATI TROVATI:")
    for url, count in duplicates.items():
        print(f"  {url} appare {count} volte")
        matching_routes = [r for r in routes if r[0] == url]
        for route in matching_routes:
            print(f"    -> {route[1]} [{route[2]}]")
else:
    print("\n✅ Nessun duplicato trovato!")
