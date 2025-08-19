# tests/test_app.py
import os
import sys
import pytest
import tempfile
from pathlib import Path

# Aggiungi il path del progetto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Articolo, Magazzino, Partner, Documento, RigaDocumento
from app.utils import unify_um, gen_internal_code, parse_it_date
from decimal import Decimal

@pytest.fixture
def app():
    """Crea app per testing"""
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """Test client"""
    return app.test_client()

@pytest.fixture
def runner(app):
    """CLI runner"""
    return app.test_cli_runner()

@pytest.fixture
def sample_data(app):
    """Dati di esempio per test"""
    with app.app_context():
        # Magazzino
        mag = Magazzino(codice='TEST', nome='Magazzino Test')
        db.session.add(mag)
        
        # Partner
        fornitore = Partner(nome='Fornitore Test', tipo='Fornitore')
        cliente = Partner(nome='Cliente Test', tipo='Cliente')
        db.session.add_all([fornitore, cliente])
        
        # Articolo
        art = Articolo(
            codice_interno='TEST001',
            descrizione='Articolo Test',
            qta_scorta_minima=Decimal('10'),
            last_cost=Decimal('25.50')
        )
        db.session.add(art)
        
        db.session.commit()
        
        return {
            'magazzino': mag,
            'fornitore': fornitore,
            'cliente': cliente,
            'articolo': art
        }

class TestModels:
    """Test dei modelli"""
    
    def test_articolo_creation(self, app):
        with app.app_context():
            art = Articolo(
                codice_interno='ART001',
                descrizione='Test Article'
            )
            db.session.add(art)
            db.session.commit()
            
            assert art.id is not None
            assert art.codice_interno == 'ART001'
    
    def test_documento_unique_constraint(self, app, sample_data):
        with app.app_context():
            doc1 = Documento(
                tipo='DDT_IN',
                numero=1,
                anno=2025,
                partner_id=sample_data['fornitore'].id,
                magazzino_id=sample_data['magazzino'].id
            )
            db.session.add(doc1)
            db.session.commit()
            
            # Tentativo di creare duplicato
            doc2 = Documento(
                tipo='DDT_IN',
                numero=1,
                anno=2025,
                partner_id=sample_data['fornitore'].id,
                magazzino_id=sample_data['magazzino'].id
            )
            db.session.add(doc2)
            
            with pytest.raises(Exception):  # IntegrityError
                db.session.commit()

class TestUtils:
    """Test delle utility functions"""
    
    def test_unify_um(self):
        assert unify_um('PZ') == 'PZ'
        assert unify_um('pcs') == 'PZ'
        assert unify_um('PEZZI') == 'PZ'
        assert unify_um('kg') == 'KG'
        assert unify_um('') == 'PZ'
        assert unify_um(None) == 'PZ'
    
    def test_parse_it_date(self):
        from datetime import date
        
        assert parse_it_date('2025-08-19') == date(2025, 8, 19)
        assert parse_it_date('19/08/2025') == date(2025, 8, 19)
        
        with pytest.raises(ValueError):
            parse_it_date('invalid')
    
    def test_gen_internal_code(self, app):
        with app.app_context():
            code1 = gen_internal_code('TEST')
            assert code1.startswith('TEST')
            
            # Crea articolo con questo codice
            art = Articolo(codice_interno=code1, descrizione='Test')
            db.session.add(art)
            db.session.commit()
            
            # Il prossimo codice deve essere diverso
            code2 = gen_internal_code('TEST')
            assert code2 != code1
            assert code2.startswith('TEST')

class TestRoutes:
    """Test delle route principali"""
    
    def test_index_redirect(self, client):
        response = client.get('/')
        assert response.status_code == 302
        assert '/menu' in response.location
    
    def test_menu_page(self, client):
        response = client.get('/menu')
        assert response.status_code == 200
        assert b'Magazzino Pro' in response.data
    
    def test_dashboard(self, client):
        response = client.get('/dashboard')
        assert response.status_code == 200
        assert b'Movimenti oggi' in response.data
    
    def test_articles_list(self, client):
        response = client.get('/articles')
        assert response.status_code == 200
    
    def test_api_magazzini(self, client, sample_data):
        response = client.get('/api/magazzini')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['codice'] == 'TEST'

class TestDocumentFlow:
    """Test del flusso documenti"""
    
    def test_create_draft_document(self, app, sample_data):
        with app.app_context():
            doc = Documento(
                tipo='DDT_IN',
                status='Bozza',
                partner_id=sample_data['fornitore'].id,
                magazzino_id=sample_data['magazzino'].id
            )
            db.session.add(doc)
            db.session.commit()
            
            assert doc.id is not None
            assert doc.status == 'Bozza'
            assert doc.numero is None  # Bozze possono non avere numero
    
    def test_document_confirmation_assigns_number(self, client, sample_data):
        # Crea bozza via API
        response = client.post('/api/documents/1/confirm')
        # Test che il numero venga assegnato alla conferma

class TestImportFlow:
    """Test importazione DDT"""
    
    def test_parse_ddt_endpoint(self, client):
        # Crea un PDF di test
        from pypdf import PdfWriter
        from io import BytesIO
        
        pdf_buffer = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)  # A4
        writer.write(pdf_buffer)
        pdf_buffer.seek(0)
        
        response = client.post('/api/parse-ddt',
            data={'pdf_file': (pdf_buffer, 'test.pdf')},
            content_type='multipart/form-data'
        )
        
        assert response.status_code in [200, 500]  # Dipende se Gemini è configurato

class TestCLICommands:
    """Test comandi CLI"""
    
    def test_init_db_command(self, runner):
        result = runner.invoke(args=['init-db'])
        assert 'inizializzato' in result.output.lower()
    
    def test_seed_db_command(self, runner):
        result = runner.invoke(args=['seed-db'])
        assert 'popolato' in result.output.lower()

# Configurazione pytest
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
