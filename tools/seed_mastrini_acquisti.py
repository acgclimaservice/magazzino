# tools/seed_mastrini_acquisti.py
# Uso: py tools\seed_mastrini_acquisti.py
from app import create_app
from app.extensions import db
from app.models import Mastrino

ENTRIES = [('0575002000', 'ACQUISTI MANUTENZIONE ORDINARIA COME DA CONTRATTO CONDOMINI'), ('0575002001', 'ACQUISTI MANUTENZIONE ORDINARIA COME DA CONTRATTO IMPRESE'), ('0575002002', 'ACQUISTI MANUTENZIONE ORDINARIA COME DA CONTRATTO PRIVATI'), ('0575001003', 'ACQUISTI AFFIDAMENTO (GUAZZOTTI ENERGIA)'), ('0575003000', 'ACQUISTI MANUTENZIONE STRAORDINARIA'), ('0585001000', 'ACQUISTI DA LAVORI E INTERVENTI CONDOMINI (PREVENTIVO)'), ('0585001001', 'ACQUISTI DA LAVORI PRIVATI (PREVENTIVO)'), ('0585001002', 'ACQUISTI DA LAVORI IMPRESE (PREVENTIVO)'), ('0585001004', 'ACQUISTI DA LAVORI E INTERVENTI ENTI (PREVENTIVO)'), ('0590001001', 'ACQUISTI DA INTERVENTI CONDOMINI ( ES ROTTURE, PERDITE)'), ('0590001002', 'ACQUISTI DA INTERVENTI PRIVATI (ES. ROTTURE, PERDITE)'), ('0590001003', 'ACQUISTI PER VENDITA MATERIALE'), ('0585002000', 'ACQUISTI PER RIQUALIFICAZIONI')]

def main():
    app = create_app()
    with app.app_context():
        created, skipped = 0, 0
        for codice, descrizione in ENTRIES:
            m = Mastrino.query.filter_by(codice=codice).first()
            if m:
                skipped += 1
                continue
            m = Mastrino(codice=codice, descrizione=descrizione, tipo='ACQUISTO')
            db.session.add(m)
            created += 1
        db.session.commit()
        print(f"Creati: {created}, già presenti: {skipped}")

if __name__ == "__main__":
    main()
