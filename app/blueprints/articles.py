from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..extensions import db
from ..models import Articolo
from ..utils import required, q_dec, money_dec

articles_bp = Blueprint("articles", __name__)

@articles_bp.route('/articles')
def articles():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    articoli = Articolo.query.order_by(Articolo.codice_interno).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('articles.html', articoli=articoli)

@articles_bp.route('/articles/new', methods=['GET', 'POST'])
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
                codice_fornitore=(request.form.get('codice_fornitore') or '').strip(),
                codice_produttore=(request.form.get('codice_produttore') or '').strip(),
                qta_scorta_minima=q_dec(request.form.get('qta_scorta_minima'), allow_zero=True, field='Scorta minima'),
                qta_riordino=q_dec(request.form.get('qta_riordino'), allow_zero=True, field='Q.tà riordino'),
                barcode=(request.form.get('barcode') or '').strip(),
                last_cost=money_dec(request.form.get('last_cost'))
            )
            db.session.add(art)
            db.session.commit()
            flash('Articolo creato con successo!', 'success')
            return redirect(url_for('articles.articles'))
        except Exception as e:
            db.session.rollback()
            flash(f'Errore creazione articolo: {e}', 'error')
    return render_template('article_form.html', title="Nuovo Articolo")

@articles_bp.route('/articles/<int:id>/edit', methods=['GET', 'POST'])
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
            art.codice_fornitore = (request.form.get('codice_fornitore') or '').strip()
            art.codice_produttore = (request.form.get('codice_produttore') or '').strip()
            art.qta_scorta_minima = q_dec(request.form.get('qta_scorta_minima'), allow_zero=True, field='Scorta minima')
            art.qta_riordino = q_dec(request.form.get('qta_riordino'), allow_zero=True, field='Q.tà riordino')
            art.barcode = (request.form.get('barcode') or '').strip()
            art.last_cost = money_dec(request.form.get('last_cost'))
            db.session.commit()
            flash('Articolo aggiornato con successo!', 'success')
            return redirect(url_for('articles.articles'))
        except Exception as e:
            db.session.rollback()
            flash(f'Errore aggiornamento articolo: {e}', 'error')
    return render_template('article_form.html', title="Modifica Articolo", articolo=art)

@articles_bp.route('/articles/<int:id>/delete', methods=['POST'])
def delete_article(id):
    art = Articolo.query.get_or_404(id)
    try:
        giac_tot = sum((g.quantita for g in art.giacenze), Decimal('0.000'))
        if giac_tot != Decimal('0.000'):
            flash('Impossibile eliminare: esiste giacenza residua (totale != 0).', 'error')
            return redirect(url_for('articles.articles'))
        db.session.delete(art)
        db.session.commit()
        flash('Articolo eliminato con successo.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Errore eliminazione articolo: {e}', 'error')
    return redirect(url_for('articles.articles'))
