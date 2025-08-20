from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..extensions import db
from ..models import Magazzino, Mastrino, Partner
from ..utils import required

settings_bp = Blueprint("settings", __name__)

@settings_bp.route('/settings')
def settings():
    return render_template('settings.html',
                           magazzini=Magazzino.query.all(),
                           mastrini_acq=Mastrino.query.filter_by(tipo='ACQUISTO').all(),
                           mastrini_ric=Mastrino.query.filter_by(tipo='RICAVO').all(),
                           partners=Partner.query.all())

@settings_bp.route('/settings/add/<string:item_type>', methods=['POST'])
def add_setting(item_type):
    try:
        if item_type == 'warehouse':
            codice = required(request.form.get('codice'), 'Codice').upper()
            nome = required(request.form.get('nome'), 'Nome')
            if Magazzino.query.filter_by(codice=codice).first():
                raise ValueError(f"Magazzino '{codice}' già esistente.")
            new_item = Magazzino(codice=codice, nome=nome)
            msg = 'Magazzino aggiunto.'
        elif item_type == 'partner':
            nome = required(request.form.get('nome'), 'Nome')
            tipo = request.form.get('tipo')
            if tipo not in ('Cliente', 'Fornitore'):
                raise ValueError('Tipo partner non valido.')
            if Partner.query.filter_by(nome=nome).first():
                raise ValueError(f"Partner '{nome}' già esistente.")
            new_item = Partner(nome=nome, tipo=tipo)
            msg = 'Partner aggiunto.'
        elif item_type == 'mastrino':
            codice = required(request.form.get('codice'), 'Codice')
            descr = required(request.form.get('descrizione'), 'Descrizione')
            tipo = request.form.get('tipo')
            if tipo not in ('ACQUISTO', 'RICAVO'):
                raise ValueError('Tipo mastrino non valido.')
            if Mastrino.query.filter_by(codice=codice).first():
                raise ValueError(f"Mastrino '{codice}' già esistente.")
            new_item = Mastrino(codice=codice, descrizione=descr, tipo=tipo)
            msg = 'Mastrino aggiunto.'
        else:
            raise ValueError('Tipo elemento non valido.')
        db.session.add(new_item)
        db.session.commit()
        flash(msg, 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore impostazioni: {e}', 'error')
    return redirect(url_for('settings.settings'))


@settings_bp.route('/settings/partners/import', methods=['POST'])
def import_partners():
    from sqlalchemy import func as _func
    import csv, io
    f = request.files.get('file')
    default_tipo = (request.form.get('default_tipo') or '').strip().capitalize()
    if default_tipo not in ('Cliente','Fornitore'):
        default_tipo = 'Cliente'
    if not f:
        flash('Seleziona un file CSV.', 'error')
        return redirect(url_for('settings.settings'))
    try:
        # read CSV (UTF-8 or latin-1 fallback)
        raw = f.read()
        try:
            txt = raw.decode('utf-8')
        except UnicodeDecodeError:
            txt = raw.decode('latin-1')
        reader = csv.DictReader(io.StringIO(txt), delimiter=';')
        created = 0
        updated = 0
        for row in reader:
            nome = (row.get('nome') or row.get('ragione_sociale') or '').strip()
            tipo = (row.get('tipo') or default_tipo).strip().capitalize()
            if not nome:
                continue
            if tipo not in ('Cliente','Fornitore'):
                tipo = default_tipo
            p = Partner.query.filter(_func.lower(Partner.nome) == nome.lower()).first()
            if p:
                if p.tipo != tipo:
                    p.tipo = tipo
                    updated += 1
            else:
                db.session.add(Partner(nome=nome, tipo=tipo))
                created += 1
        db.session.commit()
        flash(f'Import partner completato. Inseriti: {created}, aggiornati: {updated}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore import partner: {e}', 'error')
    return redirect(url_for('settings.settings'))


@settings_bp.post('/settings/mastrini/ricavi/seed')
def seed_mastrini_ricavi():
    ENTRIES = [('0475002000', 'RICAVI MANUTENZIONE ORDINARIA COME DA CONTRATTO CONDOMINI'), ('0475002001', 'RICAVI MANUTENZIONE ORDINARIA COME DA CONTRATTO IMPRESE'), ('0475002002', 'RICAVI MANUTENZIONE ORDINARIA COME DA CONTRATTO PRIVATI'), ('0475001003', 'RICAVI AFFIDAMENTO (GUAZZOTTI ENERGIA)'), ('0475003000', 'RICAVI MANUTENZIONE STRAORDINARIA'), ('0485001000', 'RICAVI DA LAVORI E INTERVENTI CONDOMINI (PREVENTIVO)'), ('0485001001', 'RICAVI DA LAVORI PRIVATI (PREVENTIVO)'), ('0485001002', 'RICAVI DA LAVORI IMPRESE (PREVENTIVO)'), ('0485001004', 'RICAVI DA LAVORI E INTERVENTI ENTI (PREVENTIVO)'), ('0490001001', 'RICAVI DA INTERVENTI CONDOMINI ( ES ROTTURE, PERDITE)'), ('0490001002', 'RICAVI DA INTERVENTI PRIVATI (ES. ROTTURE, PERDITE)'), ('0490001003', 'RICAVI PER VENDITA MATERIALE'), ('0485002000', 'RICAVI PER RIQUALIFICAZIONI')]
    created, skipped = 0, 0
    try:
        for code, descr in ENTRIES:
            m = Mastrino.query.filter_by(codice=code).first()
            if m:
                if m.tipo != 'RICAVO': m.tipo = 'RICAVO'
                if not m.descrizione: m.descrizione = descr
                skipped += 1
                continue
            db.session.add(Mastrino(codice=code, descrizione=descr, tipo='RICAVO'))
            created += 1
        db.session.commit()
        flash(f'Mastrini RICAVO: inseriti {created}, già presenti {skipped}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore inserimento mastrini RICAVO: {e}', 'error')
    return redirect(url_for('settings.settings'))


@settings_bp.post('/settings/mastrini/ricavi/add')
def add_mastrino_ricavo():
    code = (request.form.get('codice') or '').strip()
    descr = (request.form.get('descrizione') or '').strip()
    if not code or not descr:
        flash('Codice e descrizione sono obbligatori.', 'error')
        return redirect(url_for('settings.settings'))
    # harden: solo numeri / max 20 char
    if len(code) > 20:
        flash('Codice troppo lungo (max 20).', 'error')
        return redirect(url_for('settings.settings'))
    try:
        existing = Mastrino.query.filter_by(codice=code).first()
        if existing:
            existing.tipo = 'RICAVO'
            if not existing.descrizione:
                existing.descrizione = descr
            db.session.commit()
            flash('Mastrino aggiornato (era già presente).', 'success')
            return redirect(url_for('settings.settings'))
        m = Mastrino(codice=code, descrizione=descr, tipo='RICAVO')
        db.session.add(m)
        db.session.commit()
        flash('Mastrino RICAVO inserito.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore inserimento mastrino: {e}', 'error')
    return redirect(url_for('settings.settings'))


@settings_bp.app_context_processor
def inject_mastrini_lists():
    try:
        acq = Mastrino.query.filter_by(tipo='ACQUISTO').order_by(Mastrino.codice.asc()).all()
    except Exception:
        acq = []
    try:
        ric = Mastrino.query.filter_by(tipo='RICAVO').order_by(Mastrino.codice.asc()).all()
    except Exception:
        ric = []
    return dict(mastrini_acq=acq, mastrini_ric=ric)
