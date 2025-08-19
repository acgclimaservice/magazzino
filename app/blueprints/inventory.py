# In app/blueprints/inventory.py
# Sostituisci tutto il contenuto con questo:

from flask import Blueprint, render_template, request
from sqlalchemy import func
from ..extensions import db
from ..models import Articolo, Giacenza, Magazzino

inventory_bp = Blueprint("inventory", __name__)

@inventory_bp.route('/inventory')
def inventory():
    # Parametri filtro
    magazzino_filter = request.args.get('magazzino_id', type=int)
    search_query = request.args.get('search', '').strip()
    only_in_stock = request.args.get('only_in_stock') == '1'
    under_min = request.args.get('under_min') == '1'
    
    # Query base con LEFT JOIN per includere anche articoli senza giacenze
    query = db.session.query(
        Articolo.id,
        Articolo.codice_interno,
        Articolo.descrizione,
        Articolo.last_cost,
        Articolo.qta_scorta_minima,
        Magazzino.codice.label('magazzino_codice'),
        Magazzino.nome.label('magazzino_nome'),
        func.coalesce(Giacenza.quantita, 0).label('giacenza')
    ).outerjoin(Giacenza, Giacenza.articolo_id == Articolo.id)\
     .outerjoin(Magazzino, Magazzino.id == Giacenza.magazzino_id)
    
    # Applica filtri
    if magazzino_filter:
        query = query.filter(Giacenza.magazzino_id == magazzino_filter)
    
    if search_query:
        like_pattern = f"%{search_query}%"
        query = query.filter(
            (Articolo.codice_interno.ilike(like_pattern)) |
            (Articolo.descrizione.ilike(like_pattern))
        )
    
    if only_in_stock:
        query = query.filter(Giacenza.quantita > 0)
    
    if under_min:
        query = query.filter(
            Giacenza.quantita < Articolo.qta_scorta_minima,
            Articolo.qta_scorta_minima > 0
        )
    
    # Ordina per codice interno
    articoli = query.order_by(Articolo.codice_interno).all()
    
    # Lista magazzini per il filtro
    magazzini = Magazzino.query.order_by(Magazzino.codice).all()
    
    return render_template('inventory.html', 
                         articoli=articoli, 
                         magazzini=magazzini,
                         current_filters={
                             'magazzino_id': magazzino_filter,
                             'search': search_query,
                             'only_in_stock': only_in_stock,
                             'under_min': under_min
                         })
