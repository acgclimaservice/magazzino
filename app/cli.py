from decimal import Decimal
from flask import current_app
from .extensions import db
from .models import Mastrino, Magazzino, Partner, Articolo

def register_cli(app):
    @app.cli.command('init-db')
    def init_db_command():
        """Drop + Create + seed minimi."""
        with app.app_context():
            db.drop_all()
            db.create_all()
            if not Mastrino.query.first():
                for m in [
                    {'codice': '0590001003', 'descrizione': 'ACQUISTO MATERIALE DI CONSUMO', 'tipo': 'ACQUISTO'},
                    {'codice': '0490001003', 'descrizione': 'RICAVI PER VENDITA MATERIALE', 'tipo': 'RICAVO'},
                ]:
                    db.session.add(Mastrino(**m))
            if not Magazzino.query.first():
                for m in [
                    {'codice': 'MAG1', 'nome': 'Magazzino Principale'},
                    {'codice': 'FUR1', 'nome': 'Furgone Mario'}
                ]:
                    db.session.add(Magazzino(**m))
            if not Partner.query.first():
                for p in [
                    {'nome': 'Ferramenta Rossi Srl', 'tipo': 'Fornitore'},
                    {'nome': 'Cliente Prova', 'tipo': 'Cliente'}
                ]:
                    db.session.add(Partner(**p))
            db.session.commit()
            print('Database inizializzato e popolato con dati di default.')

    @app.cli.command('create-sample-data')
    def create_sample_data():
        """Inserisce alcuni articoli di esempio."""
        with app.app_context():
            for art_data in [
                {'codice_interno': 'ART001', 'descrizione': 'Filtro aria condizionata', 'qta_scorta_minima': Decimal('10.000'), 'last_cost': Decimal('15.50')},
                {'codice_interno': 'ART002', 'descrizione': 'Tubo flessibile 2m', 'qta_scorta_minima': Decimal('5.000'), 'last_cost': Decimal('25.00')},
                {'codice_interno': 'ART003', 'descrizione': 'Telecomando universale', 'qta_scorta_minima': Decimal('3.000'), 'last_cost': Decimal('45.00')}
            ]:
                if not Articolo.query.filter_by(codice_interno=art_data['codice_interno']).first():
                    db.session.add(Articolo(**art_data))
            db.session.commit()
            print('Sample data creati.')
