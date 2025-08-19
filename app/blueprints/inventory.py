from flask import Blueprint, render_template, jsonify
from sqlalchemy import func
from ..extensions import db
from ..models import Articolo, Giacenza

inventory_bp = Blueprint("inventory", __name__)

@inventory_bp.route('/inventory')
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

@inventory_bp.route('/api/inventory/<int:article_id>')
def inventory_detail(article_id):
    giacenze = Giacenza.query.filter_by(articolo_id=article_id).all()
    dettaglio = [{'magazzino': g.magazzino.nome, 'quantita': float(g.quantita)} for g in giacenze]
    return jsonify(dettaglio)
