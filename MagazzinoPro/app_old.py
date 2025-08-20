import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime, date

# --- CONFIGURAZIONE ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SECRET_KEY'] = 'una-chiave-segreta-molto-sicura'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'magazzino.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELLI DATABASE ---

class Articolo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codice_interno = db.Column(db.String(50), unique=True, nullable=False)
    descrizione = db.Column(db.String(200), nullable=False)
    fornitore = db.Column(db.String(100))
    produttore = db.Column(db.String(100))
    qta_scorta_minima = db.Column(db.Float, default=0)
    barcode = db.Column(db.String(100))
    last_cost = db.Column(db.Float, default=0)
    giacenze = db.relationship('Giacenza', backref='articolo', lazy=True, cascade="all, delete-orphan")

class Magazzino(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codice = db.Column(db.String(20), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)

class Giacenza(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    articolo_id = db.Column(db.Integer, db.ForeignKey('articolo.id'), nullable=False)
    magazzino_id = db.Column(db.Integer, db.ForeignKey('magazzino.id'), nullable=False)
    quantita = db.Column(db.Float, nullable=False, default=0)
    magazzino = db.relationship('Magazzino')

class Mastrino(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codice = db.Column(db.String(20), unique=True, nullable=False)
    descrizione = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(10), nullable=False) # 'ACQUISTO' o 'RICAVO'

class Partner(db.Model): # Cliente o Fornitore
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), unique=True, nullable=False)
    tipo = db.Column(db.String(20), nullable=False) # 'Cliente' o 'Fornitore'

class Documento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False) # 'DDT_IN' o 'DDT_OUT'
    numero = db.Column(db.Integer, nullable=False)
    data = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='Bozza') # 'Bozza' o 'Confermato'
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
    quantita = db.Column(db.Float, nullable=False)
    prezzo = db.Column(db.Float, nullable=False)
    mastrino_codice = db.Column(db.String(20))
    articolo = db.relationship('Articolo')

class Movimento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    articolo_id = db.Column(db.Integer, db.ForeignKey('articolo.id'), nullable=False)
    quantita = db.Column(db.Float, nullable=False)
    tipo = db.Column(db.String(20), nullable=False) # 'carico', 'scarico', 'trasferimento'
    magazzino_partenza_id = db.Column(db.Integer, db.ForeignKey('magazzino.id'))
    magazzino_arrivo_id = db.Column(db.Integer, db.ForeignKey('magazzino.id'))
    documento_id = db.Column(db.Integer, db.ForeignKey('documento.id'))
    articolo = db.relationship('Articolo')
    magazzino_partenza = db.relationship('Magazzino', foreign_keys=[magazzino_partenza_id])
    magazzino_arrivo = db.relationship('Magazzino', foreign_keys=[magazzino_arrivo_id])


# --- FUNZIONI HELPER ---
def get_giacenza(articolo_id, magazzino_id, session=None):
    db_session = session or db.session
    giacenza = db_session.query(Giacenza).filter_by(articolo_id=articolo_id, magazzino_id=magazzino_id).first()
    return giacenza.quantita if giacenza else 0

def update_giacenza(articolo_id, magazzino_id, quantita_da_muovere, session=None):
    db_session = session or db.session
    giacenza = db_session.query(Giacenza).filter_by(articolo_id=articolo_id, magazzino_id=magazzino_id).first()
    if giacenza:
        giacenza.quantita += quantita_da_muovere
    else:
        giacenza = Giacenza(articolo_id=articolo_id, magazzino_id=magazzino_id, quantita=quantita_da_muovere)
        db_session.add(giacenza)
    return giacenza

# --- ROTTE PRINCIPALI ---
@app.route('/')
def index():
    return redirect(url_for('menu'))

@app.route('/menu')
def menu():
    return render_template('menu.html')

@app.route('/dashboard')
def dashboard():
    today = date.today()
    movimenti_oggi = Movimento.query.filter(func.date(Movimento.data) == today).count()
    documenti_in_bozza = Documento.query.filter_by(status='Bozza').count()
    
    articoli = Articolo.query.all()
    articoli_sotto_scorta = []
    for art in articoli:
        giacenza_totale = sum(g.quantita for g in art.giacenze)
        if giacenza_totale < art.qta_scorta_minima:
            art.giacenza_totale = giacenza_totale
            articoli_sotto_scorta.append(art)
            
    return render_template('dashboard.html', 
                           movimenti_oggi=movimenti_oggi, 
                           documenti_in_bozza=documenti_in_bozza, 
                           articoli_sotto_scorta=articoli_sotto_scorta)

# --- ROTTE ARTICOLI (CRUD) ---
@app.route('/articles')
def articles():
    articoli = Articolo.query.order_by(Articolo.codice_interno).all()
    return render_template('articles.html', articoli=articoli)

@app.route('/articles/new', methods=['GET', 'POST'])
def new_article():
    if request.method == 'POST':
        nuovo_articolo = Articolo(
            codice_interno=request.form['codice_interno'],
            descrizione=request.form['descrizione'],
            fornitore=request.form['fornitore'],
            produttore=request.form['produttore'],
            qta_scorta_minima=float(request.form['qta_scorta_minima'] or 0),
            barcode=request.form['barcode'],
            last_cost=float(request.form['last_cost'] or 0)
        )
        db.session.add(nuovo_articolo)
        db.session.commit()
        flash('Articolo creato con successo!', 'success')
        return redirect(url_for('articles'))
    return render_template('article_form.html', title="Nuovo Articolo")

@app.route('/articles/<int:id>/edit', methods=['GET', 'POST'])
def edit_article(id):
    articolo = Articolo.query.get_or_404(id)
    if request.method == 'POST':
        articolo.codice_interno = request.form['codice_interno']
        articolo.descrizione = request.form['descrizione']
        articolo.fornitore = request.form['fornitore']
        articolo.produttore = request.form['produttore']
        articolo.qta_scorta_minima = float(request.form['qta_scorta_minima'] or 0)
        articolo.barcode = request.form['barcode']
        articolo.last_cost = float(request.form['last_cost'] or 0)
        db.session.commit()
        flash('Articolo aggiornato con successo!', 'success')
        return redirect(url_for('articles'))
    return render_template('article_form.html', title="Modifica Articolo", articolo=articolo)

@app.route('/articles/<int:id>/delete', methods=['POST'])
def delete_article(id):
    articolo = Articolo.query.get_or_404(id)
    db.session.delete(articolo)
    db.session.commit()
    flash('Articolo eliminato con successo.', 'success')
    return redirect(url_for('articles'))

# --- ROTTE MOVIMENTI ---
@app.route('/movements', methods=['GET', 'POST'])
def movements():
    if request.method == 'POST':
        # Logica per movimento manuale
        codice_articolo = request.form['codice_articolo']
        articolo = Articolo.query.filter_by(codice_interno=codice_articolo).first()
        if not articolo:
            flash(f"Articolo '{codice_articolo}' non trovato.", 'error')
            return redirect(url_for('movements'))
        
        quantita = float(request.form['quantita'])
        tipo = request.form['tipo']
        
        if tipo == 'trasferimento':
            mag_partenza_id = int(request.form['magazzino_partenza'])
            mag_arrivo_id = int(request.form['magazzino_arrivo'])
            if mag_partenza_id == mag_arrivo_id:
                flash('Magazzino di partenza e arrivo non possono coincidere.', 'error')
                return redirect(url_for('movements'))
            
            # Scarico da partenza
            update_giacenza(articolo.id, mag_partenza_id, -quantita)
            # Carico ad arrivo
            update_giacenza(articolo.id, mag_arrivo_id, quantita)
        else: # Carico o Scarico
            magazzino_id = int(request.form['magazzino'])
            quantita_mov = quantita if tipo == 'carico' else -quantita
            update_giacenza(articolo.id, magazzino_id, quantita_mov)
        
        db.session.commit()
        flash('Movimento manuale registrato.', 'success')
        return redirect(url_for('movements'))

    movimenti = Movimento.query.order_by(Movimento.data.desc()).all()
    magazzini = Magazzino.query.all()
    return render_template('movements.html', movimenti=movimenti, magazzini=magazzini)
    
# --- ROTTE DOCUMENTI ---
@app.route('/documents')
def documents():
    ddt_in = Documento.query.filter_by(tipo='DDT_IN').order_by(Documento.data.desc()).all()
    ddt_out = Documento.query.filter_by(tipo='DDT_OUT').order_by(Documento.data.desc()).all()
    return render_template('documents.html', ddt_in=ddt_in, ddt_out=ddt_out)

@app.route('/documents/<int:id>')
def document_detail(id):
    doc = Documento.query.get_or_404(id)
    articoli = Articolo.query.order_by(Articolo.codice_interno).all()
    mastrini = Mastrino.query.filter_by(tipo='ACQUISTO' if doc.tipo == 'DDT_IN' else 'RICAVO').all()
    return render_template('document_detail.html', doc=doc, articoli=articoli, mastrini=mastrini)

@app.route('/documents/new/<string:doc_type>')
def new_document(doc_type):
    partners = Partner.query.filter_by(tipo='Fornitore' if doc_type == 'DDT_IN' else 'Cliente').all()
    magazzini = Magazzino.query.all()
    if not partners or not magazzini:
        flash('Crea almeno un magazzino e un fornitore/cliente nelle impostazioni.', 'error')
        return redirect(url_for('documents'))

    # Calcola nuovo numero
    year = date.today().year
    last_doc = Documento.query.filter_by(tipo=doc_type).order_by(Documento.numero.desc()).first()
    new_number = (last_doc.numero + 1) if last_doc else 1
    
    new_doc = Documento(
        tipo=doc_type,
        numero=new_number,
        data=date.today(),
        partner_id=partners[0].id,
        magazzino_id=magazzini[0].id,
    )
    db.session.add(new_doc)
    db.session.commit()
    return redirect(url_for('document_detail', id=new_doc.id))

@app.route('/documents/<int:id>/add_line', methods=['POST'])
def add_document_line(id):
    doc = Documento.query.get_or_404(id)
    if doc.status == 'Confermato':
        flash('Impossibile modificare un documento confermato.', 'error')
        return redirect(url_for('document_detail', id=id))
    
    riga = RigaDocumento(
        documento_id=doc.id,
        articolo_id=int(request.form['articolo_id']),
        quantita=float(request.form['quantita']),
        prezzo=float(request.form['prezzo']),
        mastrino_codice=request.form['mastrino_codice']
    )
    db.session.add(riga)
    db.session.commit()
    flash('Riga aggiunta.', 'success')
    return redirect(url_for('document_detail', id=id))

@app.route('/documents/lines/<int:line_id>/delete', methods=['POST'])
def delete_document_line(line_id):
    riga = RigaDocumento.query.get_or_404(line_id)
    doc_id = riga.documento_id
    if riga.documento.status == 'Confermato':
        flash('Impossibile modificare un documento confermato.', 'error')
        return redirect(url_for('document_detail', id=doc_id))
    
    db.session.delete(riga)
    db.session.commit()
    flash('Riga eliminata.', 'success')
    return redirect(url_for('document_detail', id=doc_id))

@app.route('/documents/<int:id>/confirm', methods=['POST'])
def confirm_document(id):
    doc = Documento.query.get_or_404(id)
    if doc.status != 'Bozza':
        flash('Documento già confermato.', 'error')
        return redirect(url_for('document_detail', id=id))

    for riga in doc.righe:
        if doc.tipo == 'DDT_OUT':
            giacenza = get_giacenza(riga.articolo_id, doc.magazzino_id)
            if giacenza < riga.quantita:
                flash(f'Giacenza insufficiente per {riga.articolo.codice_interno}.', 'error')
                return redirect(url_for('document_detail', id=id))
            
            update_giacenza(riga.articolo_id, doc.magazzino_id, -riga.quantita)
            mov_tipo = 'scarico'
        else: # DDT_IN
            update_giacenza(riga.articolo_id, doc.magazzino_id, riga.quantita)
            mov_tipo = 'carico'
        
        movimento = Movimento(
            articolo_id=riga.articolo_id,
            quantita=riga.quantita,
            tipo=mov_tipo,
            magazzino_arrivo_id=doc.magazzino_id if mov_tipo == 'carico' else None,
            magazzino_partenza_id=doc.magazzino_id if mov_tipo == 'scarico' else None,
            documento_id=doc.id
        )
        db.session.add(movimento)

    doc.status = 'Confermato'
    db.session.commit()
    flash('Documento confermato e movimenti generati!', 'success')
    return redirect(url_for('document_detail', id=id))

# --- ROTTE IMPOSTAZIONI ---
@app.route('/settings')
def settings():
    return render_template('settings.html', 
                           magazzini=Magazzino.query.all(),
                           mastrini_acq=Mastrino.query.filter_by(tipo='ACQUISTO').all(),
                           mastrini_ric=Mastrino.query.filter_by(tipo='RICAVO').all(),
                           partners=Partner.query.all())

@app.route('/settings/add/<string:item_type>', methods=['POST'])
def add_setting(item_type):
    if item_type == 'warehouse':
        new_item = Magazzino(codice=request.form['codice'], nome=request.form['nome'])
        flash('Magazzino aggiunto.', 'success')
    elif item_type == 'partner':
        new_item = Partner(nome=request.form['nome'], tipo=request.form['tipo'])
        flash('Partner aggiunto.', 'success')
    elif item_type == 'mastrino':
        new_item = Mastrino(codice=request.form['codice'], descrizione=request.form['descrizione'], tipo=request.form['tipo'])
        flash('Mastrino aggiunto.', 'success')
    else:
        flash('Tipo non valido.', 'error')
        return redirect(url_for('settings'))
    
    db.session.add(new_item)
    db.session.commit()
    return redirect(url_for('settings'))

# --- ROTTE INVENTARIO ---
@app.route('/inventory')
def inventory():
    articoli = db.session.query(
        Articolo.id,
        Articolo.codice_interno,
        Articolo.descrizione,
        Articolo.last_cost,
        Articolo.qta_scorta_minima,
        func.sum(Giacenza.quantita).label('giacenza_totale')
    ).outerjoin(Giacenza).group_by(Articolo.id).all()
    return render_template('inventory.html', articoli=articoli)

@app.route('/api/inventory/<int:article_id>')
def inventory_detail(article_id):
    giacenze = Giacenza.query.filter_by(articolo_id=article_id).all()
    dettaglio = [{'magazzino': g.magazzino.nome, 'quantita': g.quantita} for g in giacenze]
    return jsonify(dettaglio)

# --- COMANDI CLI ---
@app.cli.command('init-db')
def init_db_command():
    """Crea le tabelle e popola i dati iniziali."""
    db.drop_all()
    db.create_all()
    if not Mastrino.query.first():
        mastrini_data = [
            {'codice': '0590001003', 'descrizione': 'ACQUISTO MATERIALE DI CONSUMO', 'tipo': 'ACQUISTO'},
            {'codice': '0490001003', 'descrizione': 'RICAVI PER VENDITA MATERIALE', 'tipo': 'RICAVO'},
        ]
        for m in mastrini_data: db.session.add(Mastrino(**m))
    if not Magazzino.query.first():
        magazzini_data = [
            {'codice': 'MAG1', 'nome': 'Magazzino Principale'},
            {'codice': 'FUR1', 'nome': 'Furgone Mario'}
        ]
        for m in magazzini_data: db.session.add(Magazzino(**m))
    if not Partner.query.first():
        partners_data = [
            {'nome': 'Ferramenta Rossi Srl', 'tipo': 'Fornitore'},
            {'nome': 'Cliente Prova', 'tipo': 'Cliente'}
        ]
        for p in partners_data: db.session.add(Partner(**p))
    db.session.commit()
    print('Database inizializzato e popolato con dati di default.')

if __name__ == '__main__':
    app.run(debug=True)
