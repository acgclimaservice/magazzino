from datetime import datetime, date, time, timedelta
from flask import Blueprint, render_template, redirect, url_for
from sqlalchemy import func, and_
from ..extensions import db
from ..models import Articolo, Giacenza, Documento, Movimento

core_bp = Blueprint("core", __name__)

@core_bp.route('/favicon.ico')
def favicon():
    return ('', 204)

@core_bp.route('/')
def index():
    return redirect(url_for('core.menu'))

@core_bp.route('/menu')
def menu():
    return render_template('menu.html')

@core_bp.route('/dashboard')
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
