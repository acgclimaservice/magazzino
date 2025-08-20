PATCH PACK 07 (Compat 1.3)

File inclusi:
- app/blueprints/documents.py  → Ordinamento per numero crescente + Nuovo DDT IN manuale + link rapido Nuovo DDT OUT
- app/templates/documents_in.html / documents_out.html → Pulsanti Importa/NUOVI e nota ordinamento
- app/blueprints/movements.py + app/templates/movements.html → Colonna "Da" mostra la sigla fornitore per carichi da DDT IN
- app/templates/document_new_in.html → Form per creare DDT IN vuoto

Da fare a mano (1 passaggio) in app/blueprints/importing.py (se importi DDT DUOTERMICA):
Sostituisci il blocco che prepara qty_raw/qty_dec/unit_price in import_ddt_confirm() con questo snippet:

qty_raw = r.get('quantità') if 'quantità' in r else r.get('quantita') if 'quantita' in r else r.get('qty')
            um = unify_um(r.get('um'))
            qty_dec = _to_decimal(qty_raw) or D('0')
            unit_price = _extract_unit_price(r, qty_dec)

            # Fix fornitore DUOTERMICA: spesso quantità contiene il prezzo unitario
            supplier_name_up = (fornitore_nome or '').strip().upper()
            if 'DUOTERMICA' in supplier_name_up:
                try:
                    if (unit_price is None or unit_price == D('0')) and qty_dec and (qty_dec >= D('10') or (qty_dec * 100) % 1 == 0):
                        unit_price = qty_dec.quantize(D('0.01'))
                        qty_raw = (r.get('pezzi') or r.get('qta') or r.get('qty_real') or '1')
                        qty_dec = _to_decimal(qty_raw) or D('1')
                except Exception:
                    pass

Report mastrini e mapping Acquisto→Vendita: se vuoi li aggiungo in un pack separato (richiede creare 2 tabelline).
