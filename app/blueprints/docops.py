from flask import Blueprint, jsonify, request
from decimal import Decimal as D
from datetime import datetime, date

from ..extensions import db
from ..models import Documento, RigaDocumento, Movimento
from ..utils import update_giacenza, get_giacenza, next_doc_number

docops_bp = Blueprint("docops", __name__)


def _safe_float(val, default=0.0):
    try:
        return float(val)
    except Exception:
        return float(default)


def _row_to_front_dict(r: RigaDocumento):
    um = getattr(r, "um", None)
    if not um and getattr(r, "articolo", None) is not None:
        um = getattr(r.articolo, "um", None)
    if not um:
        um = "PZ"

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
        "um": um,
        "quantita": _safe_float(getattr(r, "quantita", 0)),
        "prezzo": _safe_float(getattr(r, "prezzo", 0)),
        "mastrino_codice": getattr(r, "mastrino_codice", None),
    }


@docops_bp.get("/api/documents/<int:id>/json")
def api_document_json(id: int):
    doc = Documento.query.get_or_404(id)

    partner_name = None
    if getattr(doc, "partner", None) is not None:
        partner_name = getattr(doc.partner, "nome", None) or getattr(doc.partner, "ragione_sociale", None)
    if not partner_name:
        partner_name = getattr(doc, "partner_nome", None)

    try:
        rows = doc.righe.order_by(RigaDocumento.id).all()
    except AttributeError:
        rows = list(getattr(doc, "righe", []) or [])
        rows.sort(key=lambda x: x.id or 0)

    righe = [_row_to_front_dict(r) for r in rows]

    doc_out = {
        "id": doc.id,
        "tipo": doc.tipo,
        "numero": doc.numero,
        "anno": getattr(doc, "anno", None),
        "data": doc.data.isoformat() if getattr(doc, "data", None) else None,
        "status": doc.status,
        "partner": partner_name or "",
        "magazzino_id": getattr(doc, "magazzino_id", None),
        "note": getattr(doc, "note", None),
        "righe": righe,
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

        # --- LOGICA AGGIORNATA: ASSEGNA NUMERO E DATA AL MOMENTO DELLA CONFERMA ---
        today = datetime.utcnow().date()
        doc.data = today
        doc.anno = today.year
        doc.numero = next_doc_number(doc.tipo, doc.anno)
        # --- FINE LOGICA AGGIORNATA ---

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


@docops_bp.post("/api/documents/<int:id>/void")
def api_void_document(id: int):
    doc = Documento.query.get_or_404(id)

    if doc.status != "Bozza":
        return jsonify({"ok": False, "error": "Solo documenti in Bozza possono essere annullati."}), 400

    reason = ""
    if request.is_json:
        reason = (request.json.get("reason") or "").strip()

    try:
        # Elimina le righe associate
        for r in doc.righe:
            db.session.delete(r)
        
        # Elimina gli allegati associati
        for a in doc.allegati:
            db.session.delete(a)
        
        # Elimina il documento stesso
        db.session.delete(doc)
        
        db.session.commit()
        return jsonify({"ok": True, "status": "Eliminato", "msg": "Bozza eliminata definitivamente."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


@docops_bp.post("/api/documents/<int:id>/reverse")
def api_reverse_document(id: int):
    doc = Documento.query.get_or_404(id)

    if doc.status == "Stornato":
        return jsonify({"ok": True, "status": doc.status, "msg": "Documento già stornato."})
    if doc.status != "Confermato":
        return jsonify({"ok": False, "error": "Solo documenti Confermati possono essere stornati."}), 400

    try:
        rows = doc.righe.order_by(RigaDocumento.id).all()

        # Genera movimenti di storno e aggiorna giacenze
        for r in rows:
            q = D(str(getattr(r, "quantita", 0) or 0))
            if q <= 0:
                continue
            
            if doc.tipo == "DDT_IN":
                if get_giacenza(r.articolo_id, doc.magazzino_id) < q:
                    raise ValueError(f"Giacenza insufficiente per stornare l'articolo {r.articolo.codice_interno if r.articolo else 'N/A'}.")
                update_giacenza(r.articolo_id, doc.magazzino_id, -q)
                rev_tipo = "scarico"
            elif doc.tipo == "DDT_OUT":
                update_giacenza(r.articolo_id, doc.magazzino_id, q)
                rev_tipo = "carico"
            else:
                continue

            rev = Movimento(
                data=datetime.utcnow(),
                articolo_id=r.articolo_id,
                quantita=q,
                tipo=f"storno_{rev_tipo}",
                magazzino_partenza_id=doc.magazzino_id if rev_tipo == "scarico" else None,
                magazzino_arrivo_id=doc.magazzino_id if rev_tipo == "carico" else None,
                documento_id=doc.id,
            )
            db.session.add(rev)

        doc.status = "Stornato"
        db.session.commit()
        return jsonify({"ok": True, "status": doc.status})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

def _parse_date_any(s):
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.date()
        except ValueError:
            continue
    return None

@docops_bp.post("/api/documents/<int:id>/update")
def api_update_document(id: int):
    doc = Documento.query.get_or_404(id)
    if doc.status != "Bozza":
        return jsonify({"ok": False, "error": "Solo documenti in Bozza possono essere modificati."}), 400

    payload = request.get_json(silent=True) or {}
    header = payload.get("header") or {}
    rows_in = payload.get("righe") or []

    try:
        # Header parziale
        if "riferimento_fornitore" in header:
            doc.riferimento_fornitore = str(header.get("riferimento_fornitore", "")).strip()
        if "magazzino_id" in header:
            try:
                doc.magazzino_id = int(header.get("magazzino_id"))
            except (ValueError, TypeError):
                pass
        if "partner_id" in header:
            try:
                doc.partner_id = int(header.get("partner_id"))
            except (ValueError, TypeError):
                pass

        # Righe
        for rj in rows_in:
            rid = rj.get("id")
            if not rid:
                continue
            r = RigaDocumento.query.get(rid)
            if not r or r.documento_id != doc.id:
                continue

            if "descrizione" in rj:
                r.descrizione = (rj.get("descrizione") or "").strip()
            if "quantita" in rj:
                try:
                    r.quantita = D(str(rj.get("quantita") or 0))
                except Exception:
                    pass
            if "prezzo" in rj:
                try:
                    r.prezzo = D(str(rj.get("prezzo") or 0))
                except Exception:
                    pass
            if "mastrino_codice" in rj:
                r.mastrino_codice = (rj.get("mastrino_codice") or "").strip() or None

        db.session.commit()
        return api_document_json(id)
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500
