# In app/blueprints/movements.py
# Sostituisci tutto il contenuto con questo:

from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..extensions import db
from ..models import Articolo, Movimento, Magazzino, Documento, Partner
from ..utils import required, q_dec, get_giacenza, update_giacenza

movements_bp = Blueprint("movements", __name__)

@movements_bp.route('/movements', methods=['GET', 'POST'])
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
                id_from = int(request.form['magazzino_from'])
                id_to = int(request.form['magazzino_to'])
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
        return redirect(url_for('movements.movements'))

    page = request.args.get('page', 1, type=int)
    movimenti = Movimento.query.order_by(Movimento.data.desc()).paginate(page=page, per_page=50, error_out=False)
    magazzini = Magazzino.query.all()

    # 🔥 CORREZIONE: Etichetta "Da" migliorata per DDT IN e DDT OUT
    labels_da = {}
    labels_a = {}
    
    try:
        for m in movimenti.items:
            # Colonna "Da" (partenza)
            label_da = ''
            if m.magazzino_partenza:
                label_da = m.magazzino_partenza.codice
            elif m.tipo == 'carico' and getattr(m, 'documento_id', None):
                # Per carichi da DDT_IN, mostra il fornitore
                doc = Documento.query.get(m.documento_id)
                if doc and doc.tipo == 'DDT_IN' and doc.partner:
                    label_da = f"🏪 {doc.partner.nome}"
            
            # 🔥 CORREZIONE: Colonna "A" (arrivo)
            label_a = ''
            if m.magazzino_arrivo:
                label_a = m.magazzino_arrivo.codice
            elif m.tipo == 'scarico' and getattr(m, 'documento_id', None):
                # Per scarichi da DDT_OUT, mostra il cliente
                doc = Documento.query.get(m.documento_id)
                if doc and doc.tipo == 'DDT_OUT' and doc.partner:
                    label_a = f"👤 {doc.partner.nome}"
            
            labels_da[m.id] = label_da
            labels_a[m.id] = label_a
            
    except Exception as e:
        # Fallback in caso di errore
        labels_da = {m.id: (m.magazzino_partenza.codice if m.magazzino_partenza else '') for m in movimenti.items}
        labels_a = {m.id: (m.magazzino_arrivo.codice if m.magazzino_arrivo else '') for m in movimenti.items}

    return render_template('movements.html', 
                         movimenti=movimenti, 
                         magazzini=magazzini, 
                         labels_da=labels_da,
                         labels_a=labels_a)
