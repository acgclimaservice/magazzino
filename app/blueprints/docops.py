from flask import Blueprint, jsonify, request, url_for
from sqlalchemy import or_
from decimal import Decimal as D
from datetime import datetime, date

from ..extensions import db
from ..models import Documento, RigaDocumento, Movimento, Articolo, Partner, Magazzino
from ..utils import update_giacenza, get_giacenza, next_doc_number, required, q_dec, money_dec

docops_bp = Blueprint("docops", __name__)


def _safe_float(val, default=0.0):
    try:
        return float(val)
    except Exception:
        return float(default)


def _row_to_front_dict(r: RigaDocumento):
    codice_interno = None
    codice_fornitore = None
    if getattr(r, "articolo", None) is not None:
        codice_interno = getattr(r.articolo, "codice_interno", None)
        codice_fornitore = getattr(r.articolo, "codice_fornitore", None)

    return {
        "id": r.id,
        "articolo_id": r.articolo_id,
        "codice_interno": codice_interno,
        "codice_fornitore": codice_fornitore,
        "descrizione": getattr(r, "descrizione", "") or "",
        "quantita": _safe_float(getattr(r, "quantita", 0)),
        "prezzo": _safe_float(getattr(r, "prezzo", 0)),
        "mastrino_codice": getattr(r, "mastrino_codice", None),
    }


@docops_bp.get("/api/documents/<int:id>/json")
def api_document_json(id: int):
    doc = Documento.query.get_or_404(id)

    partner_name = doc.partner.nome if doc.partner else ""
    magazzino_info = f"{doc.magazzino.codice} - {doc.magazzino.nome}" if doc.magazzino else ""

    rows = doc.righe.order_by(RigaDocumento.id).all()
    righe = [_row_to_front_dict(r) for r in rows]

    allegati = []
    for a in doc.allegati:
        allegati.append({
            "id": a.id,
            "filename": a.filename,
            "url": url_for('files.download_file', id=a.id)
        })

    doc_out = {
        "id": doc.id,
        "tipo": doc.tipo,
        "numero": doc.numero,
        "anno": getattr(doc, "anno", None),
        "data": doc.data.isoformat() if getattr(doc, "data", None) else None,
        "data_creazione": doc.data_creazione.isoformat() if getattr(doc, "data_creazione", None) else None,
        "status": doc.status,
        "partner_id": doc.partner_id,
        "partner_nome": partner_name,
        "magazzino_id": getattr(doc, "magazzino_id", None),
        "magazzino_info": magazzino_info,
        "note": getattr(doc, "note", None),
        "righe": righe,
        "allegati": allegati
    }

    return jsonify({"ok": True, "doc": doc_out})


@docops_bp.post("/api/documents/<int:id>/confirm")
def api_confirm_document(id: int):
    doc = Documento.query.get_or_404(id)
    if doc.status != "Bozza":
        return jsonify({"ok": True, "status": doc.status, "msg": "Documento già confermato."})

    try:
        rows = doc.righe.order_by(RigaDocumento.id).all()
        if not rows:
            return jsonify({"ok": False, "error": "Nessuna riga nel documento."}), 400

        # Assegna numero e data al momento della conferma
        today = datetime.utcnow().date()
        doc.data = today
        doc.anno = today.year
        doc.numero = next_doc_number(doc.tipo, doc.anno)

        # Aggiornamento giacenze e generazione movimenti
        for r in rows:
            q = D(str(getattr(r, "quantita", 0) or 0))
            if q <= 0:
                continue
            
            if doc.tipo == "DDT_IN":
                update_giacenza(r.articolo_id, doc.magazzino_id, q)
                mv = Movimento(
                    data=doc.data,
                    articolo_id=r.articolo_id,
                    quantita=q,
                    tipo="carico",
                    magazzino_arrivo_id=doc.magazzino_id,
                    documento_id=doc.id,
                )
            elif doc.tipo == "DDT_OUT":
                if get_giacenza(r.articolo_id, doc.magazzino_id) < q:
                    raise ValueError(f"Giacenza insufficiente per l'articolo {r.articolo.codice_interno if r.articolo else 'N/A'}.")
                update_giacenza(r.articolo_id, doc.magazzino_id, -q)
                mv = Movimento(
                    data=doc.data,
                    articolo_id=r.articolo_id,
                    quantita=q, # La quantità nei movimenti è sempre positiva
                    tipo="scarico",
                    magazzino_partenza_id=doc.magazzino_id,
                    documento_id=doc.id,
                )
            else:
                raise ValueError("Tipo documento non gestito.")
            db.session.add(mv)

        doc.status = "Confermato"
        db.session.commit()
        return jsonify({"ok": True, "status": doc.status})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


@docops_bp.post("/api/documents/<int:id>/delete-draft")
def api_delete_draft(id: int):
    doc = Documento.query.get_or_404(id)
    if doc.status != "Bozza":
        return jsonify({"ok": False, "error": "Solo le bozze possono essere eliminate."}), 400
    try:
        db.session.delete(doc)
        db.session.commit()
        return jsonify({"ok": True, "msg": "Bozza eliminata."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


@docops_bp.post("/api/documents/<int:id>/add-line")
def api_add_line(id: int):
    doc = Documento.query.get_or_404(id)
    if doc.status != "Bozza":
        return jsonify({"ok": False, "error": "Puoi aggiungere righe solo alle bozze."}), 400
    
    data = request.get_json()
    try:
        art = Articolo.query.get(int(data['articolo_id']))
        if not art:
            return jsonify({"ok": False, "error": "Articolo non trovato."}), 404

        new_line = RigaDocumento(
            documento_id=doc.id,
            articolo_id=art.id,
            descrizione=art.descrizione,
            quantita=q_dec(data.get('quantita', '1')),
            prezzo=money_dec(data.get('prezzo', '0')),
            mastrino_codice=data.get('mastrino_codice')
        )
        db.session.add(new_line)
        db.session.commit()
        return jsonify({"ok": True, "line": _row_to_front_dict(new_line)})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


@docops_bp.post("/api/documents/lines/<int:line_id>/delete")
def api_delete_line(line_id: int):
    line = RigaDocumento.query.get_or_404(line_id)
    if line.documento.status != "Bozza":
        return jsonify({"ok": False, "error": "Puoi eliminare righe solo dalle bozze."}), 400
    try:
        db.session.delete(line)
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

@docops_bp.get("/api/articles/search")
def api_articles_search():
    q = request.args.get("q", "").strip()
    limit = request.args.get("limit", 10, type=int)
    
    if not q:
        return jsonify([])

    query = Articolo.query.filter(
        or_(
            Articolo.codice_interno.ilike(f"%{q}%"),
            Articolo.descrizione.ilike(f"%{q}%"),
            Articolo.codice_fornitore.ilike(f"%{q}%")
        )
    ).limit(limit).all()

    results = [
        {
            "id": art.id,
            "codice_interno": art.codice_interno,
            "descrizione": art.descrizione,
            "last_cost": float(art.last_cost or 0)
        } for art in query
    ]
    return jsonify(results)
