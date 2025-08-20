from flask import Blueprint, jsonify, request, url_for
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, subqueryload
from decimal import Decimal as D
from datetime import datetime, date
import traceback

from ..extensions import db
from ..models import Documento, RigaDocumento, Movimento, Articolo, Partner, Magazzino
from ..utils import update_giacenza, get_giacenza, next_doc_number, required, q_dec, money_dec, gen_internal_code, supplier_prefix

docops_bp = Blueprint("docops", __name__)


def _safe_float(val, default=0.0):
    if val is None:
        return float(default)
    try:
        return float(val)
    except (ValueError, TypeError):
        return float(default)


def _row_to_front_dict(r: RigaDocumento):
    codice_interno = None
    codice_fornitore = None
    try:
        if r and r.articolo:
            codice_interno = r.articolo.codice_interno
            codice_fornitore = r.articolo.codice_fornitore
    except AttributeError:
        pass

    return {
        "id": r.id,
        "articolo_id": r.articolo_id,
        "codice_interno": codice_interno,
        "codice_fornitore": codice_fornitore,
        "descrizione": r.descrizione or "",
        "quantita": _safe_float(r.quantita, 0),
        "prezzo": _safe_float(r.prezzo, 0),
        "mastrino_codice": r.mastrino_codice,
    }


@docops_bp.get("/api/documents/<int:id>/json")
def api_document_json(id: int):
    try:
        doc = Documento.query.options(
            joinedload(Documento.partner),
            joinedload(Documento.magazzino),
            subqueryload(Documento.righe).joinedload(RigaDocumento.articolo),
            joinedload(Documento.allegati)
        ).get_or_404(id)

        partner_name = doc.partner.nome if doc.partner else ""
        magazzino_info = f"{doc.magazzino.codice} - {doc.magazzino.nome}" if doc.magazzino else ""
        
        rows = doc.righe.all() if hasattr(doc, 'righe') else []
        righe = [_row_to_front_dict(r) for r in rows]

        allegati = []
        if hasattr(doc, 'allegati') and doc.allegati:
            for a in doc.allegati:
                if a and a.id:
                    allegati.append({
                        "id": a.id,
                        "filename": a.filename,
                        "url": url_for('files.download_attachment', allegato_id=a.id)
                    })

        doc_out = {
            "id": doc.id,
            "tipo": doc.tipo,
            "numero": doc.numero,
            "anno": getattr(doc, "anno", None),
            "data": doc.data.isoformat() if doc.data else None,
            "data_creazione": doc.data_creazione.isoformat() if doc.data_creazione else None,
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

    except Exception as e:
        print(f"ERRORE GRAVE in api_document_json per doc ID {id}:")
        traceback.print_exc()
        return jsonify({"ok": False, "error": "Errore interno del server."}), 500


@docops_bp.post("/api/documents/<int:id>/add-line")
def api_add_line(id: int):
    doc = Documento.query.get_or_404(id)
    if doc.status != "Bozza":
        return jsonify({"ok": False, "error": "Puoi aggiungere righe solo alle bozze."}), 400
    
    data = request.get_json()
    try:
        # Dati obbligatori
        descrizione = required(data.get('descrizione'), "Descrizione")
        quantita = q_dec(data.get('quantita', '1'))
        
        # Dati opzionali
        codice_interno = (data.get('codice_interno') or '').strip()
        codice_fornitore = (data.get('codice_fornitore') or '').strip()
        um = (data.get('um') or 'PZ').strip()
        prezzo = money_dec(data.get('prezzo', '0'))
        mastrino_codice = data.get('mastrino_codice')
        articolo_id = data.get('articolo_id')

        articolo = None
        # 1. Cerca per ID se fornito (da autocomplete)
        if articolo_id:
            articolo = Articolo.query.get(int(articolo_id))

        # 2. Se non trovato o non fornito, cerca per codice interno
        if not articolo and codice_interno:
            articolo = Articolo.query.filter_by(codice_interno=codice_interno).first()
        
        # 3. Se ancora non trovato, crea un nuovo articolo
        if not articolo:
            if not codice_interno:
                # Se non viene fornito un codice, ne generiamo uno per evitare duplicati basati su descrizioni
                prefix = supplier_prefix(doc.partner.nome if doc.partner else "MAN")
                codice_interno = gen_internal_code(prefix)

            articolo = Articolo(
                codice_interno=codice_interno,
                codice_fornitore=codice_fornitore,
                descrizione=descrizione,
                fornitore=doc.partner.nome if doc.partner and doc.tipo == "DDT_IN" else None,
                last_cost=prezzo
            )
            db.session.add(articolo)
            db.session.flush() # Ottieni l'ID del nuovo articolo

        # Crea la riga del documento
        descrizione_riga = f"{descrizione} [{um}]" if um else descrizione
        new_line = RigaDocumento(
            documento_id=doc.id,
            articolo_id=articolo.id,
            descrizione=descrizione_riga,
            quantita=quantita,
            prezzo=prezzo,
            mastrino_codice=mastrino_codice
        )
        db.session.add(new_line)
        db.session.commit()
        
        return jsonify({"ok": True, "line": _row_to_front_dict(new_line)})
        
    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@docops_bp.post("/api/documents/<int:id>/confirm")
def api_confirm_document(id: int):
    doc = Documento.query.get_or_404(id)
    if doc.status != "Bozza":
        return jsonify({"ok": True, "status": doc.status, "msg": "Documento già confermato."})

    try:
        rows = doc.righe.order_by(RigaDocumento.id).all()
        if not rows:
            return jsonify({"ok": False, "error": "Nessuna riga nel documento."}), 400

        today = datetime.utcnow().date()
        doc.data = today
        doc.anno = today.year
        doc.numero = next_doc_number(doc.tipo, doc.anno)

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
                    quantita=q,
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
            "codice_fornitore": art.codice_fornitore,
            "descrizione": art.descrizione,
            "last_cost": float(art.last_cost or 0)
        } for art in query
    ]
    return jsonify(results)
