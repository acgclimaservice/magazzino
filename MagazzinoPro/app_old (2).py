import os
from decimal import Decimal, InvalidOperation
from datetime import datetime, date, time, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, UniqueConstraint, CheckConstraint, and_
from sqlalchemy.exc import IntegrityError

# --- CONFIGURAZIONE ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
# In prod imposta SECRET_KEY via env; in dev un fallback stabile (non random)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'magazzino.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- UTILITY / VALIDAZIONI ---
def current_year():
    return date.today().year

def parse_it_date(s: str) -> date:
    s = (s or '').strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError("Formato data non valido. Usa gg/mm/aaaa.")

def q_dec(value: str, scale='0.001', allow_zero=False, field="Quantità") -> Decimal:
    s = (value or '').strip().replace(',', '.')
    try:
        q = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"{field} non valida.")
    if (not allow_zero and q <= 0) or (allow_zero and q < 0):
        raise ValueError(f"{field} deve essere {'≥ 0' if allow_zero else '> 0'}.")
    return q.quantize(Decimal(scale))

def money_dec(value: str) -> Decimal:
    s = (value or '').strip().replace(',', '.')
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

# --- MODELLI ---
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

class Partner(db.Model):  # Cliente o Fornitore
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
    status = db.Column(db.String(20), default='Bozza')  # 'Bozza' o 'Confermato'
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
    data = db.Column(db.DateTime, default=datetime.now)  # locale, allineato a KPI "oggi"
    articolo_id = db.Column(db.Integer, db.ForeignKey('articolo.id'), nullable=False)
    quantita = db.Column(db.Numeric(14, 3), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'carico', 'scarico', 'trasferimento'
    magazzino_partenza_id = db.Column(db.Integer, db.ForeignKey('magazzino.id'))
    magazzino_arrivo_id = db.Column(db.Integer, db.ForeignKey('magazzino.id'))
    documento_id = db.Column(db.Integer, db.ForeignKey('documento.id'))
    articolo = db.relationship('Articolo')
    magazzino_partenza = db.relationship('Magazzino', foreign_keys=[magazzino_partenza_id])
    magazzino_arrivo = db.relationship('Magazzino', foreign_keys=[magazzino_arrivo_id])

# --- HELPER DI DOMINIO ---
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

def next_doc_number(doc_type, year=None) -> int:
    year = year or date.today().year
    last = (Documento.query
            .filter_by(tipo=doc_type, anno=year)
            .order_by(Documento.numero.desc())
            .first())
    return (last.numero + 1) if last else 1

# --- ERROR HANDLERS ---
@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return render_template('errors/500.html'), 500

# --- ROTTE PRINCIPALI ---
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

    # sotto-scorta con HAVING (no N+1), su colonne Numeric
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

# --- ARTICOLI ---
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

# --- MOVIMENTI ---
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

# --- DOCUMENTI ---
@app.route('/documents')
def documents():
    ddt_in = Documento.query.filter_by(tipo='DDT_IN').order_by(Documento.data.desc()).limit(100).all()
    ddt_out = Documento.query.filter_by(tipo='DDT_OUT').order_by(Documento.data.desc()).limit(100).all()
    return render_template('documents.html', ddt_in=ddt_in, ddt_out=ddt_out)

def _assign_number_with_retry(doc: Documento, tries: int = 3):
    """Assegna numero con retry su collisione (race)."""
    for _ in range(tries):
        doc.numero = next_doc_number(doc.tipo, doc.anno)
        try:
            db.session.add(doc)
            db.session.commit()
            return True
        except IntegrityError:
            db.session.rollback()
    return False

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
    if not _assign_number_with_retry(doc):
        flash('Impossibile assegnare numero documento (collisioni ripetute).', 'error')
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
                # tenta assegnazione numero con retry
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
        rows = doc.righe.all()
        if not rows:
            flash('Nessuna riga nel documento.', 'error')
            return redirect(url_for('document_detail', id=id))

        # Timestamp movimenti ancorato alla data documento (00:00)
        mov_time = datetime.combine(doc.data, time.min)

        for r in rows:
            if doc.tipo == 'DDT_OUT':
                if get_giacenza(r.articolo_id, doc.magazzino_id) < r.quantita:
                    flash(f'Giacenza insufficiente per {r.articolo.codice_interno}.', 'error')
                    db.session.rollback()
                    return redirect(url_for('document_detail', id=id))
                update_giacenza(r.articolo_id, doc.magazzino_id, -r.quantita)
                mov = Movimento(articolo_id=r.articolo_id, quantita=r.quantita, tipo='scarico',
                                magazzino_partenza_id=doc.magazzino_id, documento_id=doc.id, data=mov_time)
            else:  # DDT_IN
                update_giacenza(r.articolo_id, doc.magazzino_id, r.quantita)
                r.articolo.last_cost = r.prezzo
                mov = Movimento(articolo_id=r.articolo_id, quantita=r.quantita, tipo='carico',
                                magazzino_arrivo_id=doc.magazzino_id, documento_id=doc.id, data=mov_time)
            db.session.add(mov)

        doc.status = 'Confermato'
        db.session.commit()
        flash('Documento confermato e movimenti generati!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore conferma documento: {e}', 'error')
    return redirect(url_for('document_detail', id=id))

# --- IMPOSTAZIONI ---
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

# --- INVENTARIO ---
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

# --- CLI ---
@app.cli.command('init-db')
def init_db_command():
    """Crea le tabelle e popola i dati iniziali."""
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
    """Crea dati di esempio per test rapidi."""
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
