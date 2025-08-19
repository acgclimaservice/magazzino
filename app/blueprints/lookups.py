from flask import Blueprint, jsonify, request
from ..extensions import db
from ..models import Magazzino, Mastrino, Partner

lookups_bp = Blueprint("lookups", __name__)

@lookups_bp.route("/api/magazzini")
def api_magazzini():
    # Ritorna elenco magazzini: id, codice, nome
    rows = Magazzino.query.order_by(Magazzino.codice).all()
    out = [{"id": m.id, "codice": m.codice, "nome": m.nome} for m in rows]
    return jsonify(out)

@lookups_bp.route("/api/mastrini")
def api_mastrini():
    # Ritorna elenco mastrini. Filtra per tipo=ACQUISTO|RICAVO se fornito
    tipo = (request.args.get("tipo") or "").strip().upper()
    q = Mastrino.query
    if tipo in ("ACQUISTO", "RICAVO"):
        q = q.filter(Mastrino.tipo == tipo)
    rows = q.order_by(Mastrino.codice).all()
    out = [{"codice": m.codice, "descrizione": m.descrizione, "tipo": m.tipo} for m in rows]
    return jsonify(out)


@lookups_bp.route("/api/clienti")
def api_clienti():
    # Ritorna elenco clienti: id, nome
    rows = Partner.query.filter_by(tipo='Cliente').order_by(Partner.nome).all()
    out = [{"id": c.id, "nome": c.nome} for c in rows]
    return jsonify(out)
