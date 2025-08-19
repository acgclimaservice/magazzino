from datetime import datetime
from decimal import Decimal
from sqlalchemy import UniqueConstraint, CheckConstraint, Index, func
from .extensions import db

# Modelli

class Articolo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codice_interno = db.Column(db.String(50), unique=True, nullable=False)
    codice_fornitore = db.Column(db.String(50))
    codice_produttore = db.Column(db.String(50))
    descrizione = db.Column(db.String(200), nullable=False)
    fornitore = db.Column(db.String(100))
    produttore = db.Column(db.String(100))
    qta_scorta_minima = db.Column(db.Numeric(14, 3), default=0)
    qta_riordino = db.Column(db.Numeric(14, 3), default=0)
    barcode = db.Column(db.String(100))
    last_cost = db.Column(db.Numeric(10, 2), default=0)
    giacenze = db.relationship('Giacenza', backref='articolo', lazy=True, cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_articolo_codice_fornitore', 'codice_fornitore'),
    )

class Magazzino(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codice = db.Column(db.String(20), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)

class Giacenza(db.Model):
    __table_args__ = (
        UniqueConstraint('articolo_id', 'magazzino_id', name='uq_giacenza_art_mag'),
        CheckConstraint('quantita >= 0', name='ck_giacenza_nonneg'),
    )
    id = db.Column(db.Integer, primary_key=True)
    articolo_id = db.Column(db.Integer, db.ForeignKey('articolo.id'), nullable=False)
    magazzino_id = db.Column(db.Integer, db.ForeignKey('magazzino.id'), nullable=False)
    quantita = db.Column(db.Numeric(14, 3), nullable=False, default=0)
    magazzino = db.relationship('Magazzino')

class Mastrino(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codice = db.Column(db.String(20), unique=True, nullable=False)
    descrizione = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)  # 'ACQUISTO' o 'RICAVO'

class Partner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), unique=True, nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'Cliente' o 'Fornitore'

class Documento(db.Model):
    __table_args__ = (
        UniqueConstraint('tipo', 'anno', 'numero', name='uq_documento_tipo_anno_numero'),
        Index('ix_doc_anno_tipo_num', 'anno', 'tipo', 'numero'),
    )
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)
    
    # --- MODIFICHE APPLICATE QUI ---
    numero = db.Column(db.Integer, nullable=True) # Può essere nullo per le bozze
    anno = db.Column(db.Integer, nullable=True)   # Può essere nullo per le bozze
    data = db.Column(db.Date, nullable=True)      # Può essere nulla per le bozze
    data_creazione = db.Column(db.DateTime, nullable=False, server_default=func.now()) # Data creazione bozza
    riferimento_fornitore = db.Column(db.String(100)) # Es. "DDT 123 del 15/08/2025"
    commessa_id = db.Column(db.String(50)) # COLONNA AGGIUNTA
    # --- FINE MODIFICHE ---

    status = db.Column(db.String(20), default='Bozza', nullable=False)
    partner_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=False)
    magazzino_id = db.Column(db.Integer, db.ForeignKey('magazzino.id'), nullable=False)
    
    partner = db.relationship('Partner')
    magazzino = db.relationship('Magazzino')
    righe = db.relationship('RigaDocumento', backref='documento', lazy='dynamic', cascade="all, delete-orphan")
    allegati = db.relationship('Allegato', backref='documento', lazy=True, cascade="all, delete-orphan")
    movimenti = db.relationship('Movimento', backref='documento', lazy=True)

class RigaDocumento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(db.Integer, db.ForeignKey('documento.id'), nullable=False)
    articolo_id = db.Column(db.Integer, db.ForeignKey('articolo.id'), nullable=False)
    descrizione = db.Column(db.String(200))
    quantita = db.Column(db.Numeric(14, 3), nullable=False)
    prezzo = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    mastrino_codice = db.Column(db.String(20))
    articolo = db.relationship('Articolo')

class Movimento(db.Model):
    __table_args__ = (Index('ix_movimento_data', 'data'),)
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.now)
    articolo_id = db.Column(db.Integer, db.ForeignKey('articolo.id'), nullable=False)
    quantita = db.Column(db.Numeric(14, 3), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    magazzino_partenza_id = db.Column(db.Integer, db.ForeignKey('magazzino.id'))
    magazzino_arrivo_id = db.Column(db.Integer, db.ForeignKey('magazzino.id'))
    documento_id = db.Column(db.Integer, db.ForeignKey('documento.id'))
    articolo = db.relationship('Articolo')
    magazzino_partenza = db.relationship('Magazzino', foreign_keys=[magazzino_partenza_id])
    magazzino_arrivo = db.relationship('Magazzino', foreign_keys=[magazzino_arrivo_id])

class Allegato(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(db.Integer, db.ForeignKey('documento.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    mime = db.Column(db.String(100))
    path = db.Column(db.String(400), nullable=False)
    size = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
