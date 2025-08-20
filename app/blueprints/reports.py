# Crea file: app/blueprints/reports.py

from flask import Blueprint, render_template, request
from sqlalchemy import func, case, text
from datetime import datetime, date
from ..extensions import db
from ..models import Documento, RigaDocumento, Mastrino, Partner

reports_bp = Blueprint("reports", __name__)

@reports_bp.route('/reports')
def reports_index():
    """Pagina principale dei report"""
    return render_template('reports/index.html')

@reports_bp.route('/reports/mastrini')
def report_mastrini():
    """Report riepilogo per mastrini acquisti e vendite"""
    
    # Parametri filtro
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    tipo_filter = request.args.get('tipo', '')  # 'ACQUISTO', 'RICAVO', o ''
    
    # Query base: raggruppa per mastrino e calcola totali
    query = db.session.query(
        RigaDocumento.mastrino_codice,
        Mastrino.descrizione.label('mastrino_descrizione'),
        Mastrino.tipo.label('mastrino_tipo'),
        func.count(RigaDocumento.id).label('num_righe'),
        func.sum(
            case(
                (Documento.tipo == 'DDT_IN', RigaDocumento.quantita * RigaDocumento.prezzo),
                else_=0
            )
        ).label('totale_acquisti'),
        func.sum(
            case(
                (Documento.tipo == 'DDT_OUT', RigaDocumento.quantita * RigaDocumento.prezzo),
                else_=0
            )
        ).label('totale_vendite'),
        func.sum(
            case(
                (Documento.tipo == 'DDT_IN', RigaDocumento.quantita),
                else_=-RigaDocumento.quantita
            )
        ).label('saldo_quantita')
    ).join(Documento, RigaDocumento.documento_id == Documento.id)\
     .outerjoin(Mastrino, Mastrino.codice == RigaDocumento.mastrino_codice)\
     .filter(Documento.status == 'Confermato')\
     .filter(RigaDocumento.mastrino_codice.isnot(None))
    
    # Applica filtri data
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(Documento.data >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(Documento.data <= date_to_obj)
        except ValueError:
            pass
    
    # Applica filtro tipo mastrino
    if tipo_filter in ('ACQUISTO', 'RICAVO'):
        query = query.filter(Mastrino.tipo == tipo_filter)
    
    # Raggruppa per mastrino e ordina
    results = query.group_by(
        RigaDocumento.mastrino_codice,
        Mastrino.descrizione,
        Mastrino.tipo
    ).order_by(
        Mastrino.tipo.desc(),  # RICAVO prima di ACQUISTO
        RigaDocumento.mastrino_codice
    ).all()
    
    # Calcola totali generali
    totale_acquisti = sum(r.totale_acquisti or 0 for r in results)
    totale_vendite = sum(r.totale_vendite or 0 for r in results)
    margine_totale = totale_vendite - totale_acquisti
    
    return render_template('reports/mastrini.html',
                         results=results,
                         totale_acquisti=totale_acquisti,
                         totale_vendite=totale_vendite,
                         margine_totale=margine_totale,
                         filters={
                             'date_from': date_from,
                             'date_to': date_to,
                             'tipo': tipo_filter
                         })

@reports_bp.route('/reports/movimenti-periodo')
def report_movimenti_periodo():
    """Report movimenti per periodo"""
    # Da implementare in futuro
    return "Report movimenti per periodo - Coming soon!"
