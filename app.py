import os
import json
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime, date, time, timedelta

import requests
from pypdf import PdfReader
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, UniqueConstraint, CheckConstraint, and_
from sqlalchemy.exc import IntegrityError

# .env
from dotenv import load_dotenv
load_dotenv()

# --- CONFIG ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
try:
    app.jinja_env.cache = {}
except Exception:
    pass

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'SQLALCHEMY_DATABASE_URI',
    'sqlite:///' + os.path.join(basedir, 'magazzino.db')
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv("MAX_CONTENT_LENGTH_MB", "20")) * 1024 * 1024

db = SQLAlchemy(app)

# --- API Blueprints opzionali ---
try:
    from api import api_bp, api_public_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(api_public_bp)
except Exception as e:
    print(f"[WARN] API non registrate: {e}")

# --- Utility/Validazioni ---
def current_year():
    return date.today().year

def parse_it_date(s: str) -> date:
    s = (s or '').strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError("Formato data non valido. Usa YYYY-MM-DD o gg/mm/aaaa.")

def q_dec(value: str, scale='0.001', allow_zero=False, field="Quantità") -> Decimal:
    s = (str(value) if value is not None else '').strip().replace(',', '.')
    try:
        q = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"{field} non valida.")
    if (not allow_zero and q <= 0) or (allow_zero and q < 0):
        raise ValueError(f"{field} deve essere {'≥ 0' if allow_zero else '> 0'}.")
    return q.quantize(Decimal(scale))

def money_dec(value: str) -> Decimal:
    s = (str(value) if value is not None else '').strip().replace(',', '.')
    if not s:
        return Decimal('0.00')
    try:
        return Decimal(s).quantize(Decimal('0.01'))
    except InvalidOperation:
        raise ValueError("Importo non valido.")

def required(s: str, name: str) -> str:
    if not s or not str(s).strip():
        raise ValueError(f"{name} è obbligatorio.")
    return str(s).strip()

# --- Modelli ---
class Articolo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codice_interno = db.Column(db.String(50), unique=True, nullable=False)
    descrizione = db.Column(db.String(200), nullable=False)
    fornitore = db.Column(db.String(100))
    produttore = db.Column(db.String(100))
    qta_scorta_minima = db.Column(db.Numeric(14, 3), default=0)
    barcode = db.Column(db.String(100))
    last_cost = db.Column(db.Numeric(10, 2), default=0)
    giacenze = db.relationship('Giacenza', backref='articolo', lazy=True, cascade="all, delete-orphan")

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
        db.Index('ix_doc_anno_tipo_num', 'anno', 'tipo', 'numero'),
    )
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)  # 'DDT_IN' o 'DDT_OUT'
    numero = db.Column(db.Integer, nullable=False)
    anno = db.Column(db.Integer, nullable=False, default=current_year)
    data = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='Bozza')
    partner_id = db.Column(db.Integer, db.ForeignKey('partner.id'), nullable=False)
    magazzino_id = db.Column(db.Integer, db.ForeignKey('magazzino.id'), nullable=False)
    partner = db.relationship('Partner')
    magazzino = db.relationship('Magazzino')
    righe = db.relationship('RigaDocumento', backref='documento', lazy='dynamic', cascade="all, delete-orphan")

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
    __table_args__ = (db.Index('ix_movimento_data', 'data'),)
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.now)
    articolo_id = db.Column(db.Integer, db.ForeignKey('articolo.id'), nullable=False)
    quantita = db.Column(db.Numeric(14, 3), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'carico', 'scarico', 'trasferimento'
    magazzino_partenza_id = db.Column(db.Integer, db.ForeignKey('magazzino.id'))
    magazzino_arrivo_id = db.Column(db.Integer, db.ForeignKey('magazzino.id'))
    documento_id = db.Column(db.Integer, db.ForeignKey('documento.id'))
    articolo = db.relationship('Articolo')
    magazzino_partenza = db.relationship('Magazzino', foreign_keys=[magazzino_partenza_id])
    magazzino_arrivo = db.relationship('Magazzino', foreign_keys=[magazzino_arrivo_id])

# --- Errori & Misc ---
@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.route('/favicon.ico')
def favicon():
    return ('', 204)

# --- Rotte principali ---
@app.route('/')
def index():
    return redirect(url_for('menu'))

@app.route('/menu')
def menu():
    return render_template('menu.html')

@app.route('/dashboard')
def dashboard():
    start = datetime.combine(date.today(), time.min)
    end = start + timedelta(days=1)
    movimenti_oggi = Movimento.query.filter(and_(Movimento.data >= start, Movimento.data < end)).count()
    documenti_in_bozza = Documento.query.filter_by(status='Bozza').count()

    sotto_scorta = (db.session.query(
        Articolo.id,
        Articolo.codice_interno,
        Articolo.descrizione,
        Articolo.qta_scorta_minima,
        func.coalesce(func.sum(Giacenza.quantita), 0).label('giacenza_totale')
    ).outerjoin(Giacenza, Giacenza.articolo_id == Articolo.id)
     .group_by(Articolo.id, Articolo.codice_interno, Articolo.descrizione, Articolo.qta_scorta_minima)
     .having(func.coalesce(func.sum(Giacenza.quantita), 0) < Articolo.qta_scorta_minima)
     .having(Articolo.qta_scorta_minima > 0)
     .order_by(Articolo.codice_interno)
     .limit(50)
     .all())

    return render_template('dashboard.html',
                           movimenti_oggi=movimenti_oggi,
                           documenti_in_bozza=documenti_in_bozza,
                           articoli_sotto_scorta=sotto_scorta)

# --- Articoli ---
@app.route('/articles')
def articles():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    articoli = Articolo.query.order_by(Articolo.codice_interno).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('articles.html', articoli=articoli)

@app.route('/articles/new', methods=['GET', 'POST'])
def new_article():
    if request.method == 'POST':
        try:
            codice = required(request.form.get('codice_interno'), 'Codice interno')
            descr = required(request.form.get('descrizione'), 'Descrizione')
            if Articolo.query.filter_by(codice_interno=codice).first():
                raise ValueError(f"Codice '{codice}' già esistente.")
            art = Articolo(
                codice_interno=codice,
                descrizione=descr,
                fornitore=(request.form.get('fornitore') or '').strip(),
                produttore=(request.form.get('produttore') or '').strip(),
                qta_scorta_minima=q_dec(request.form.get('qta_scorta_minima'), allow_zero=True, field='Scorta minima'),
                barcode=(request.form.get('barcode') or '').strip(),
                last_cost=money_dec(request.form.get('last_cost'))
            )
            db.session.add(art)
            db.session.commit()
            flash('Articolo creato con successo!', 'success')
            return redirect(url_for('articles'))
        except Exception as e:
            db.session.rollback()
            flash(f'Errore creazione articolo: {e}', 'error')
    return render_template('article_form.html', title="Nuovo Articolo")

@app.route('/articles/<int:id>/edit', methods=['GET', 'POST'])
def edit_article(id):
    art = Articolo.query.get_or_404(id)
    if request.method == 'POST':
        try:
            codice = required(request.form.get('codice_interno'), 'Codice interno')
            descr = required(request.form.get('descrizione'), 'Descrizione')
            dup = Articolo.query.filter(Articolo.codice_interno == codice, Articolo.id != id).first()
            if dup:
                raise ValueError(f"Codice '{codice}' già esistente.")
            art.codice_interno = codice
            art.descrizione = descr
            art.fornitore = (request.form.get('fornitore') or '').strip()
            art.produttore = (request.form.get('produttore') or '').strip()
            art.qta_scorta_minima = q_dec(request.form.get('qta_scorta_minima'), allow_zero=True, field='Scorta minima')
            art.barcode = (request.form.get('barcode') or '').strip()
            art.last_cost = money_dec(request.form.get('last_cost'))
            db.session.commit()
            flash('Articolo aggiornato con successo!', 'success')
            return redirect(url_for('articles'))
        except Exception as e:
            db.session.rollback()
            flash(f'Errore aggiornamento articolo: {e}', 'error')
    return render_template('article_form.html', title="Modifica Articolo", articolo=art)

@app.route('/articles/<int:id>/delete', methods=['POST'])
def delete_article(id):
    art = Articolo.query.get_or_404(id)
    try:
        giac_tot = sum((g.quantita for g in art.giacenze), Decimal('0.000'))
        if giac_tot != Decimal('0.000'):
            flash('Impossibile eliminare: esiste giacenza residua (totale != 0).', 'error')
            return redirect(url_for('articles'))
        db.session.delete(art)
        db.session.commit()
        flash('Articolo eliminato con successo.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore eliminazione articolo: {e}', 'error')
    return redirect(url_for('articles'))

# --- Movimenti ---
@app.route('/movements', methods=['GET', 'POST'])
def movements():
    if request.method == 'POST':
        try:
            codice = required(request.form.get('codice_articolo'), 'Codice articolo')
            art = Articolo.query.filter_by(codice_interno=codice).first()
            if not art:
                raise ValueError(f"Articolo '{codice}' non trovato.")
            qty = q_dec(request.form.get('quantita'))
            tipo = request.form.get('tipo')
            if tipo not in ('carico', 'scarico', 'trasferimento'):
                raise ValueError('Tipo movimento non valido.')

            if tipo == 'trasferimento':
                id_from = int(request.form['magazzino_partenza'])
                id_to = int(request.form['magazzino_arrivo'])
                if id_from == id_to:
                    raise ValueError('Magazzino di partenza e arrivo non possono coincidere.')
                if get_giacenza(art.id, id_from) < qty:
                    raise ValueError('Giacenza insufficiente nel magazzino di partenza.')
                update_giacenza(art.id, id_from, -qty)
                update_giacenza(art.id, id_to, qty)
                mov = Movimento(articolo_id=art.id, quantita=qty, tipo='trasferimento',
                                magazzino_partenza_id=id_from, magazzino_arrivo_id=id_to)
            elif tipo == 'scarico':
                id_mag = int(request.form['magazzino'])
                if get_giacenza(art.id, id_mag) < qty:
                    raise ValueError('Giacenza insufficiente per scarico.')
                update_giacenza(art.id, id_mag, -qty)
                mov = Movimento(articolo_id=art.id, quantita=qty, tipo='scarico',
                                magazzino_partenza_id=id_mag)
            else:  # carico
                id_mag = int(request.form['magazzino'])
                update_giacenza(art.id, id_mag, qty)
                mov = Movimento(articolo_id=art.id, quantita=qty, tipo='carico',
                                magazzino_arrivo_id=id_mag)

            db.session.add(mov)
            db.session.commit()
            flash('Movimento manuale registrato.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Errore registrazione movimento: {e}', 'error')
        return redirect(url_for('movements'))

    page = request.args.get('page', 1, type=int)
    movimenti = Movimento.query.order_by(Movimento.data.desc()).paginate(page=page, per_page=50, error_out=False)
    magazzini = Magazzino.query.all()
    return render_template('movements.html', movimenti=movimenti, magazzini=magazzini)

# --- Documenti ---
@app.route('/documents')
def documents():
    ddt_in = Documento.query.filter_by(tipo='DDT_IN').order_by(Documento.data.desc()).limit(100).all()
    ddt_out = Documento.query.filter_by(tipo='DDT_OUT').order_by(Documento.data.desc()).limit(100).all()
    return render_template('documents.html', ddt_in=ddt_in, ddt_out=ddt_out)

def get_giacenza(articolo_id, magazzino_id, session=None) -> Decimal:
    db_session = session or db.session
    g = db_session.query(Giacenza).filter_by(articolo_id=articolo_id, magazzino_id=magazzino_id).first()
    return g.quantita if g else Decimal('0.000')

def update_giacenza(articolo_id, magazzino_id, qty, session=None):
    db_session = session or db.session
    qty = qty if isinstance(qty, Decimal) else Decimal(str(qty))
    qty = qty.quantize(Decimal('0.001'))
    g = db_session.query(Giacenza).filter_by(articolo_id=articolo_id, magazzino_id=magazzino_id).first()
    if g:
        g.quantita = (g.quantita + qty).quantize(Decimal('0.001'))
        if g.quantita < 0:
            raise ValueError("Operazione non valida: giacenza negativa.")
    else:
        if qty < 0:
            raise ValueError("Impossibile creare giacenza negativa.")
        g = Giacenza(articolo_id=articolo_id, magazzino_id=magazzino_id, quantita=qty)
        db_session.add(g)
    return g


def _confirm_and_apply_movements(doc: Documento, session=None):
    """Conferma un documento e genera i movimenti aggiornando le giacenze.
    Riutilizzato da /documents/<id>/confirm e dall'import DDT.
    """
    db_session = session or db.session
    if doc.status != 'Bozza':
        # già confermato: niente da fare
        return

    rows = doc.righe.all()
    if not rows:
        raise ValueError('Nessuna riga nel documento.')

    # usa mezzanotte della data documento per ordinare i movimenti
    mov_time = datetime.combine(doc.data, time.min)

    for r in rows:
        if doc.tipo == 'DDT_OUT':
            # controllo stock sufficiente
            if get_giacenza(r.articolo_id, doc.magazzino_id, session=db_session) < r.quantita:
                raise ValueError(f'Scarico superiore alla giacenza per articolo ID {r.articolo_id}.')
            # aggiorna giacenza e crea movimento di scarico
            update_giacenza(r.articolo_id, doc.magazzino_id, -r.quantita, session=db_session)
            mov = Movimento(
                articolo_id=r.articolo_id,
                quantita=r.quantita,
                tipo='scarico',
                magazzino_partenza_id=doc.magazzino_id,
                documento_id=doc.id,
                data=mov_time
            )
        else:
            # DDT_IN: carico a magazzino, aggiorna last_cost dal prezzo riga
            update_giacenza(r.articolo_id, doc.magazzino_id, r.quantita, session=db_session)
            r.articolo.last_cost = r.prezzo
            mov = Movimento(
                articolo_id=r.articolo_id,
                quantita=r.quantita,
                tipo='carico',
                magazzino_arrivo_id=doc.magazzino_id,
                documento_id=doc.id,
                data=mov_time
            )
        db_session.add(mov)

    doc.status = 'Confermato'
    db_session.commit()
def next_doc_number(doc_type, year=None) -> int:
    year = year or date.today().year
    last = (Documento.query
            .filter_by(tipo=doc_type, anno=year)
            .order_by(Documento.numero.desc())
            .first())
    return (last.numero + 1) if last else 1

@app.route('/documents/new/<string:doc_type>')
def new_document(doc_type):
    if doc_type not in ('DDT_IN', 'DDT_OUT'):
        flash('Tipo documento non valido.', 'error')
        return redirect(url_for('documents'))
    partners = Partner.query.filter_by(tipo='Fornitore' if doc_type == 'DDT_IN' else 'Cliente').all()
    magazzini = Magazzino.query.all()
    if not partners or not magazzini:
        flash('Crea almeno un magazzino e un fornitore/cliente nelle impostazioni.', 'error')
        return redirect(url_for('documents'))
    year = date.today().year
    doc = Documento(tipo=doc_type, anno=year, data=date.today(),
                    partner_id=partners[0].id, magazzino_id=magazzini[0].id)
    for _ in range(3):
        doc.numero = next_doc_number(doc.tipo, doc.anno)
        try:
            db.session.add(doc)
            db.session.commit()
            break
        except IntegrityError:
            db.session.rollback()
    else:
        flash('Impossibile assegnare numero documento.', 'error')
        return redirect(url_for('documents'))
    return redirect(url_for('document_detail', id=doc.id))

@app.route('/documents/<int:id>')
def document_detail(id):
    doc = Documento.query.get_or_404(id)
    articoli = Articolo.query.order_by(Articolo.codice_interno).all()
    mastrini = Mastrino.query.filter_by(tipo='ACQUISTO' if doc.tipo == 'DDT_IN' else 'RICAVO').all()
    partners = Partner.query.filter_by(tipo='Fornitore' if doc.tipo == 'DDT_IN' else 'Cliente').all()
    magazzini = Magazzino.query.all()
    return render_template('document_detail.html', doc=doc, articoli=articoli, mastrini=mastrini,
                           partners=partners, magazzini=magazzini)

@app.route('/documents/<int:id>/update', methods=['POST'])
def update_document_header(id):
    doc = Documento.query.get_or_404(id)
    if doc.status != 'Bozza':
        flash('Impossibile modificare un documento confermato.', 'error')
        return redirect(url_for('document_detail', id=id))
    try:
        dstr = request.form.get('data')
        if dstr:
            new_date = parse_it_date(dstr)
            if new_date.year != doc.anno:
                doc.anno = new_date.year
                for _ in range(3):
                    doc.numero = next_doc_number(doc.tipo, doc.anno)
                    try:
                        doc.data = new_date
                        db.session.commit()
                        break
                    except IntegrityError:
                        db.session.rollback()
                else:
                    raise ValueError("Assegnazione numero fallita per collisione.")
            else:
                doc.data = new_date

        pid = request.form.get('partner_id')
        mid = request.form.get('magazzino_id')
        if pid: doc.partner_id = int(pid)
        if mid: doc.magazzino_id = int(mid)

        db.session.commit()
        flash('Intestazione documento aggiornata.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore aggiornamento documento: {e}', 'error')
    return redirect(url_for('document_detail', id=id))

@app.route('/documents/<int:id>/add_line', methods=['POST'])
def add_document_line(id):
    doc = Documento.query.get_or_404(id)
    if doc.status == 'Confermato':
        flash('Impossibile modificare un documento confermato.', 'error')
        return redirect(url_for('document_detail', id=id))
    try:
        r = RigaDocumento(
            documento_id=doc.id,
            articolo_id=int(request.form['articolo_id']),
            descrizione=(request.form.get('descrizione') or '').strip(),
            quantita=q_dec(request.form.get('quantita')),
            prezzo=money_dec(request.form.get('prezzo')),
            mastrino_codice=(request.form.get('mastrino_codice') or '').strip()
        )
        db.session.add(r)
        db.session.commit()
        flash('Riga aggiunta.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore aggiunta riga: {e}', 'error')
    return redirect(url_for('document_detail', id=id))

@app.route('/documents/lines/<int:line_id>/delete', methods=['POST'])
def delete_document_line(line_id):
    r = RigaDocumento.query.get_or_404(line_id)
    did = r.documento_id
    if r.documento.status == 'Confermato':
        flash('Impossibile modificare un documento confermato.', 'error')
        return redirect(url_for('document_detail', id=did))
    try:
        db.session.delete(r)
        db.session.commit()
        flash('Riga eliminata.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore eliminazione riga: {e}', 'error')
    return redirect(url_for('document_detail', id=did))


@app.route('/documents/<int:id>/confirm', methods=['POST'])
def confirm_document(id):
    doc = Documento.query.get_or_404(id)
    if doc.status != 'Bozza':
        flash('Documento già confermato.', 'error')
        return redirect(url_for('document_detail', id=id))
    try:
        _confirm_and_apply_movements(doc)
        flash('Documento confermato e movimenti generati!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore conferma documento: {e}', 'error')
    return redirect(url_for('document_detail', id=id))

@app.route('/settings')
def settings():
    return render_template('settings.html',
                           magazzini=Magazzino.query.all(),
                           mastrini_acq=Mastrino.query.filter_by(tipo='ACQUISTO').all(),
                           mastrini_ric=Mastrino.query.filter_by(tipo='RICAVO').all(),
                           partners=Partner.query.all())

@app.route('/settings/add/<string:item_type>', methods=['POST'])
def add_setting(item_type):
    try:
        if item_type == 'warehouse':
            codice = required(request.form.get('codice'), 'Codice').upper()
            nome = required(request.form.get('nome'), 'Nome')
            if Magazzino.query.filter_by(codice=codice).first():
                raise ValueError(f"Magazzino '{codice}' già esistente.")
            new_item = Magazzino(codice=codice, nome=nome)
            flash('Magazzino aggiunto.', 'success')
        elif item_type == 'partner':
            nome = required(request.form.get('nome'), 'Nome')
            tipo = request.form.get('tipo')
            if tipo not in ('Cliente', 'Fornitore'):
                raise ValueError('Tipo partner non valido.')
            if Partner.query.filter_by(nome=nome).first():
                raise ValueError(f"Partner '{nome}' già esistente.")
            new_item = Partner(nome=nome, tipo=tipo)
            flash('Partner aggiunto.', 'success')
        elif item_type == 'mastrino':
            codice = required(request.form.get('codice'), 'Codice')
            descr = required(request.form.get('descrizione'), 'Descrizione')
            tipo = request.form.get('tipo')
            if tipo not in ('ACQUISTO', 'RICAVO'):
                raise ValueError('Tipo mastrino non valido.')
            if Mastrino.query.filter_by(codice=codice).first():
                raise ValueError(f"Mastrino '{codice}' già esistente.")
            new_item = Mastrino(codice=codice, descrizione=descr, tipo=tipo)
            flash('Mastrino aggiunto.', 'success')
        else:
            raise ValueError('Tipo elemento non valido.')
        db.session.add(new_item)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Errore impostazioni: {e}', 'error')
    return redirect(url_for('settings'))

# --- Inventario ---
@app.route('/inventory')
def inventory():
    articoli = (db.session.query(
        Articolo.id,
        Articolo.codice_interno,
        Articolo.descrizione,
        Articolo.last_cost,
        Articolo.qta_scorta_minima,
        func.coalesce(func.sum(Giacenza.quantita), 0).label('giacenza_totale')
    ).outerjoin(Giacenza, Giacenza.articolo_id == Articolo.id)
     .group_by(Articolo.id, Articolo.codice_interno, Articolo.descrizione, Articolo.last_cost, Articolo.qta_scorta_minima)
     .order_by(Articolo.codice_interno)
     .all())
    return render_template('inventory.html', articoli=articoli)

@app.route('/api/inventory/<int:article_id>')
def inventory_detail(article_id):
    giacenze = Giacenza.query.filter_by(articolo_id=article_id).all()
    dettaglio = [{'magazzino': g.magazzino.nome, 'quantita': float(g.quantita)} for g in giacenze]
    return jsonify(dettaglio)

# --- Workstation + Import PDF UI ---
@app.route('/workstation')
def workstation():
    return render_template('workstation.html')

@app.route('/import-pdf')
def import_pdf():
    return render_template('import_pdf.html')

# --- Parsing PDF helpers + endpoints ---
def _extract_text_from_pdf(file_storage) -> str:
    reader = PdfReader(file_storage)
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    if len(text.strip()) < 10:
        raise RuntimeError("PDF senza testo estraibile. Serve PDF nativo o OCR.")
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def _coerce_json(text: str) -> dict:
    s = (text or '').strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```$", "", s)
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start:end+1]
    return json.loads(s)

def _call_gemini(prompt: str) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY non configurato")
    model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    r = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        params={"key": api_key},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=30
    )
    r.raise_for_status()
    j = r.json()
    try:
        txt = j["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise RuntimeError(f"Risposta AI inattesa: {j}")
    return _coerce_json(txt)

def _prompt_for(kind: str, text: str) -> str:
    if kind == "ddt":
        schema = """
{
  "numero": "...",
  "data": "YYYY-MM-DD",
  "fornitore": "...",
  "articoli": [
    { "codice": "...", "descrizione": "...", "quantità": 0, "um": "..." }
  ]
}"""
        return f"""Sei un parser. Estrai dal DDT fornitore i campi richiesti e rispondi SOLO con JSON valido conforme allo schema, senza testo extra.
Schema: {schema}

Testo DDT:
{text}
"""
    elif kind == "ticket":
        schema = """
{
  "numero_ticket": "...",
  "data": "YYYY-MM-DD",
  "cliente": "...",
  "indirizzo": "...",
  "attività": "...",
  "materiali": [
    { "codice": "...", "descrizione": "...", "quantità": 0, "um": "..." }
  ]
}"""
        return f"""Estrai dati ticket dal PDF e rispondi SOLO JSON (senza spiegazioni) secondo lo schema:
{schema}

Testo:
{text}
"""
    else:  # materiali
        schema = """
{
  "fornitore": "...",
  "data": "YYYY-MM-DD",
  "righe": [
    { "codice": "...", "descrizione": "...", "quantità": 0, "um": "...", "prezzo_unitario": 0.00 }
  ]
}"""
        return f"""Estrai movimenti materiali dal PDF e rispondi SOLO JSON secondo lo schema:
{schema}

Testo:
{text}
"""

def _parse_generic(kind: str):
    try:
        file = request.files.get("pdf_file")
        if not file:
            return jsonify({"ok": False, "type": kind, "error": "Nessun file ricevuto"}), 400
        raw_text = _extract_text_from_pdf(file)
        prompt = _prompt_for(kind, raw_text)
        data = _call_gemini(prompt)
        return jsonify({"ok": True, "type": kind, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "type": kind, "error": str(e)}), 500

@app.route("/api/parse-ticket", methods=["POST"])
def api_parse_ticket():
    return _parse_generic("ticket")

@app.route("/api/parse-materiali", methods=["POST"])
def api_parse_materiali():
    return _parse_generic("materiali")

@app.route("/api/parse-ddt", methods=["POST"])
def api_parse_ddt():
    return _parse_generic("ddt")

# --- Normalizzazione UM + generazione codice articolo ---
UM_MAP = {
    "PZ": "PZ", "PCS": "PZ", "PEZZO": "PZ", "PEZZI": "PZ", "NR": "PZ", "N": "PZ",
    "M": "M", "MT": "M", "METRO": "M", "METRI": "M",
    "KG": "KG", "KGS": "KG", "KILOGRAMMI": "KG",
    "G": "G", "GR": "G", "GRAMMI": "G",
    "L": "L", "LT": "L", "LITRI": "L",
    "ML": "ML"
}
def unify_um(um: str) -> str:
    if not um:
        return "PZ"
    key = re.sub(r'[^A-Z]', '', um.upper())
    return UM_MAP.get(key, key[:5] or "PZ")

def gen_code_from_descr(descr: str) -> str:
    base = re.sub(r'[^A-Z0-9]', '', (descr or 'AUTO')[:12].upper())
    if not base:
        base = "AUTO"
    code = base
    i = 1
    while Articolo.query.filter_by(codice_interno=code).first():
        i += 1
        code = f"{base[:10]}{i:02d}"
    return code

# --- Preview & Conferma DDT ---
@app.route("/api/import-ddt-preview", methods=["POST"])
def import_ddt_preview():
    try:
        payload = request.get_json()
        if not payload or not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "Nessun dato ricevuto"}), 400
        d = payload.get("data") or {}
        # Supporta sia 'righe' sia 'articoli'
        righe = d.get("righe") or d.get("articoli") or []
        # Normalizza UM lato preview
        for r in righe:
            r["um"] = unify_um(r.get("um"))
        preview = {
            "data": d.get("data"),
            "fornitore": d.get("fornitore"),
            "righe": righe
        }
        if not preview["righe"]:
            return jsonify({"ok": False, "error": "Nessuna riga trovata"}), 400
        return jsonify({"ok": True, "preview": preview})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/magazzini")
def api_magazzini():
    rows = Magazzino.query.order_by(Magazzino.codice).all()
    return jsonify([{"id": m.id, "codice": m.codice, "nome": m.nome} for m in rows])

@app.route("/api/mastrini")
def api_mastrini():
    tipo = (request.args.get("tipo") or "").upper()
    q = Mastrino.query
    if tipo in ("ACQUISTO", "RICAVO"):
        q = q.filter_by(tipo=tipo)
    rows = q.order_by(Mastrino.codice).all()
    return jsonify([{"codice": m.codice, "descrizione": m.descrizione, "tipo": m.tipo} for m in rows])

@app.route("/api/import-ddt-confirm", methods=["POST"])
def import_ddt_confirm():
    try:
        payload = request.get_json(force=True)
        data_str = required(payload.get("data"), "Data")
        fornitore_nome = required(payload.get("fornitore"), "Fornitore")
        mastrino_codice = (payload.get("mastrino_codice") or "").strip()
        righe = payload.get("righe") or []
        if not righe:
            return jsonify({"ok": False, "error": "Nessuna riga fornita"}), 400

        # Data
        doc_date = parse_it_date(data_str)
        anno = doc_date.year

        # Partner (fornitore)
        partner = Partner.query.filter_by(nome=fornitore_nome).first()
        if partner is None:
            partner = Partner(nome=fornitore_nome, tipo='Fornitore')
            db.session.add(partner)
            db.session.flush()
        elif partner.tipo != 'Fornitore':
            partner.tipo = 'Fornitore'

        # Magazzino
        mag_id = payload.get("magazzino_id")
        mag = Magazzino.query.get(int(mag_id)) if mag_id else Magazzino.query.order_by(Magazzino.id).first()
        if not mag:
            return jsonify({"ok": False, "error": "Nessun magazzino configurato"}), 400

        # Mastrino (default se non indicato)
        if not mastrino_codice:
            m = Mastrino.query.filter_by(tipo='ACQUISTO').order_by(Mastrino.codice).first()
            if not m:
                # crea un default minimale (hardening per test)
                m = Mastrino(codice='0590001003', descrizione='ACQUISTO MATERIALE DI CONSUMO', tipo='ACQUISTO')
                db.session.add(m)
                db.session.flush()
            mastrino_codice = m.codice

        # Documento testata
        doc = Documento(tipo='DDT_IN', anno=anno, data=doc_date, partner_id=partner.id, magazzino_id=mag.id, status='Bozza')
        for _ in range(3):
            doc.numero = next_doc_number('DDT_IN', anno)
            try:
                db.session.add(doc)
                db.session.flush()
                break
            except IntegrityError:
                db.session.rollback()
        else:
            return jsonify({"ok": False, "error": "Assegnazione numero documento fallita"}), 500

        # Righe
        for r in righe:
            codice = (r.get('codice') or '').strip()
            descr = (r.get('descrizione') or '').strip() or codice or "Articolo"
            qty_raw = r.get('quantità') if 'quantità' in r else r.get('quantita') if 'quantita' in r else r.get('qty')
            um = unify_um(r.get('um'))
            prezzo_raw = r.get('prezzo_unitario') if 'prezzo_unitario' in r else r.get('prezzo')

            if not codice:
                codice = gen_code_from_descr(descr)

            if qty_raw in (None, ''):
                raise ValueError(f"Quantità mancante per articolo {codice}")

            art = Articolo.query.filter_by(codice_interno=codice).first()
            if art is None:
                art = Articolo(codice_interno=codice, descrizione=descr, last_cost=money_dec(prezzo_raw))
                db.session.add(art)
                db.session.flush()
            else:
                # aggiorna last_cost a quanto rilevato
                art.last_cost = money_dec(prezzo_raw)

            riga = RigaDocumento(
                documento_id=doc.id,
                articolo_id=art.id,
                descrizione=f"{descr} [{um}]",
                quantita=q_dec(qty_raw),
                prezzo=money_dec(prezzo_raw),
                mastrino_codice=mastrino_codice
            )
            db.session.add(riga)

        db.session.commit()
        # Auto-conferma e generazione movimenti per alimentare il magazzino
        _confirm_and_apply_movements(doc)
        return jsonify({"ok": True, "document_id": doc.id, "redirect_url": url_for('document_detail', id=doc.id), "status": doc.status})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

# --- Rotte test: pulizia massiva ---
def _clear_docs_by_type(tipo: str):
    ids = [row.id for row in Documento.query.filter_by(tipo=tipo).all()]
    if not ids:
        return 0
    db.session.query(RigaDocumento).filter(RigaDocumento.documento_id.in_(ids)).delete(synchronize_session=False)
    db.session.query(Movimento).filter(Movimento.documento_id.in_(ids)).delete(synchronize_session=False)
    db.session.query(Documento).filter(Documento.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return len(ids)

@app.route('/test/clear-ddt-in', methods=['POST'])
def clear_ddt_in():
    try:
        n = _clear_docs_by_type('DDT_IN')
        return jsonify({"ok": True, "msg": f"DDT IN eliminati: {n}"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/test/clear-ddt-out', methods=['POST'])
def clear_ddt_out():
    try:
        n = _clear_docs_by_type('DDT_OUT')
        return jsonify({"ok": True, "msg": f"DDT OUT eliminati: {n}"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/test/clear-articles', methods=['POST'])
def clear_articles():
    try:
        db.session.query(RigaDocumento).delete(synchronize_session=False)
        db.session.query(Movimento).delete(synchronize_session=False)
        db.session.query(Giacenza).delete(synchronize_session=False)
        db.session.query(Articolo).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({"ok": True, "msg": "Tutti gli articoli eliminati"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

# --- CLI ---
@app.cli.command('init-db')
def init_db_command():
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
    for art_data in [
        {'codice_interno': 'ART001', 'descrizione': 'Filtro aria condizionata', 'qta_scorta_minima': Decimal('10.000'), 'last_cost': Decimal('15.50')},
        {'codice_interno': 'ART002', 'descrizione': 'Tubo flessibile 2m', 'qta_scorta_minima': Decimal('5.000'), 'last_cost': Decimal('25.00')},
        {'codice_interno': 'ART003', 'descrizione': 'Telecomando universale', 'qta_scorta_minima': Decimal('3.000'), 'last_cost': Decimal('45.00')}
    ]:
        if not Articolo.query.filter_by(codice_interno=art_data['codice_interno']).first():
            db.session.add(Articolo(**art_data))
    db.session.commit()
    print('Sample data creati.')

if __name__ == '__main__':
    app.run(debug=True)


@app.route("/debug/template-path")
def _debug_template_path():
    try:
        t = app.jinja_env.get_or_select_template("document_detail.html")
        return jsonify({"path": getattr(t, "filename", None), "searchpath": list(getattr(app.jinja_loader, "searchpath", []))})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
