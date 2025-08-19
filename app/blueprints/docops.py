from flask import Blueprint, jsonify, request
from decimal import Decimal as D

import re as _re_num

def _to_decimal_nls(val):
    """Parse numeri in formato IT/EN:
    - '1.234,56' -> 1234.56
    - '1,234.56' -> 1234.56
    - '35,2'     -> 35.2
    - '35.2'     -> 35.2
    Ignora spazi e separatori di migliaia.
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    # rimuovi spazi
    s = _re_num.sub(r"\s+", "", s)
    if ',' in s and '.' in s:
        # decimal = ultimo separatore fra , e .
        dec = ',' if s.rfind(',') > s.rfind('.') else '.'
        thou = '.' if dec == ',' else ','
        s = s.replace(thou, '')
        s = s.replace(dec, '.')
    else:
        # assume la virgola come decimale
        s = s.replace(',', '.')
    return D(s)

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
    if doc.status == "Annullato":
        return jsonify({"ok": False, "error": "Documento annullato: non confermabile."}), 400
    if doc.status == "Confermato":
        return jsonify({"ok": True, "status": doc.status})

    try:
        rows = doc.righe.order_by(RigaDocumento.id).all()
        if not rows:
            return jsonify({"ok": False, "error": "Nessuna riga nel documento."}), 400

        # Aggiornamento giacenze + generazione movimenti
        for r in rows:
            q = D(str(getattr(r, "quantita", 0) or 0))
            if q <= 0:
                continue
            if doc.tipo == "DDT_IN":
                # Carico a magazzino
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
                # Scarico da magazzino con controllo stock
                if get_giacenza(r.articolo_id, doc.magazzino_id) < q:
                    raise ValueError("Giacenza insufficiente per lo scarico.")
                update_giacenza(r.articolo_id, doc.magazzino_id, -q)
                mv = Movimento(
                    data=doc.data,
                    articolo_id=r.articolo_id,
                    quantita=-q,
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

    def _as_D(x):
        try:
            return D(str(x))
        except Exception:
            return D("0")

    try:
        try:
            rows = doc.righe.order_by(RigaDocumento.id).all()
        except AttributeError:
            rows = list(getattr(doc, "righe", []) or [])

        if doc.tipo == "DDT_IN":
            for r in rows:
                q = _as_D(getattr(r, "quantita", 0))
                mv = Movimento(
                    data=doc.data,
                    articolo_id=r.articolo_id,
                    quantita=q,
                    tipo="carico",
                    magazzino_arrivo_id=doc.magazzino_id,
                    documento_id=doc.id,
                )
                db.session.add(mv)
        elif doc.tipo == "DDT_OUT":
            for r in rows:
                q = _as_D(getattr(r, "quantita", 0))
                mv = Movimento(
                    data=doc.data,
                    articolo_id=r.articolo_id,
                    quantita=-q,
                    tipo="scarico",
                    magazzino_partenza_id=doc.magazzino_id,
                    documento_id=doc.id,
                )
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
        try:
            rows = doc.righe.all()
        except AttributeError:
            rows = list(getattr(doc, "righe", []) or [])
        for r in rows:
            db.session.delete(r)

        try:
            allegati = list(getattr(doc, "allegati", []) or [])
            for a in allegati:
                db.session.delete(a)
        except Exception:
            pass

        try:
            movs = list(Movimento.query.filter_by(documento_id=doc.id).all())
            for m in movs:
                db.session.delete(m)
        except Exception:
            pass

        doc.status = "Annullato"
        default_msg = "documento eliminato volontariamente"
        msg = reason or default_msg
        try:
            existing = getattr(doc, "note", None) or ""
            stamp = datetime.utcnow().isoformat(timespec="seconds")
            setattr(doc, "note", (existing + f" [VOID {stamp}] {msg}").strip())
        except Exception:
            pass

        db.session.commit()
        return jsonify({"ok": True, "status": doc.status, "msg": msg})
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
        try:
            rows = doc.righe.order_by(RigaDocumento.id).all()
        except AttributeError:
            rows = list(getattr(doc, "righe", []) or [])
            rows.sort(key=lambda x: x.id or 0)

        # Genera movimenti di storno + aggiorna giacenze
        for r in rows:
            q = D(str(getattr(r, "quantita", 0) or 0))
            if q <= 0:
                continue
            if doc.tipo == "DDT_IN":
                # Storno di un carico: scarico giacenza
                if get_giacenza(r.articolo_id, doc.magazzino_id) < q:
                    raise ValueError("Giacenza insufficiente per lo storno.")
                update_giacenza(r.articolo_id, doc.magazzino_id, -q)
                rev = Movimento(
                    data=doc.data,
                    articolo_id=r.articolo_id,
                    quantita=-q,
                    tipo="scarico",
                    magazzino_partenza_id=doc.magazzino_id,
                    documento_id=doc.id,
                )
            else:  # DDT_OUT
                # Storno di uno scarico: ripristino giacenza
                update_giacenza(r.articolo_id, doc.magazzino_id, q)
                rev = Movimento(
                    data=doc.data,
                    articolo_id=r.articolo_id,
                    quantita=q,
                    tipo="carico",
                    magazzino_arrivo_id=doc.magazzino_id,
                    documento_id=doc.id,
                )
            db.session.add(rev)

        doc.status = "Stornato"
        try:
            existing = getattr(doc, "note", None) or ""
            stamp = datetime.utcnow().isoformat(timespec="seconds")
            setattr(doc, "note", (existing + f" [REVERSE {stamp}] documento stornato").strip())
        except Exception:
            pass

        db.session.commit()
        return jsonify({"ok": True, "status": doc.status})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


# --------- NEW: Update Bozza (inline edit) ---------
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
    """
    Aggiorna un documento in Bozza: header (parziale) + righe (descrizione, quantita, prezzo, mastrino_codice).
    Body atteso:
    {
      "header": { "data": "07/08/2025" | "2025-08-07", "magazzino_id": 1, "partner_nome": "..." },
      "righe": [ { "id": 10, "descrizione": "...", "quantita": 2, "prezzo": 12.5, "mastrino_codice": "ACQ" }, ... ]
    }
    """
    doc = Documento.query.get_or_404(id)
    if doc.status != "Bozza":
        return jsonify({"ok": False, "error": "Solo documenti in Bozza possono essere modificati."}), 400

    payload = request.get_json(silent=True) or {}
    header = payload.get("header") or {}
    rows_in = payload.get("righe") or []

    try:
        # Header parziale
        if "data" in header:
            d = _parse_date_any(header.get("data"))
            if isinstance(d, date):
                doc.data = d
        if "magazzino_id" in header:
            try:
                doc.magazzino_id = int(header.get("magazzino_id"))
            except Exception:
                pass
        if "partner_id" in header:
            try:
                doc.partner_id = int(header.get("partner_id"))
            except Exception:
                pass
        if "commessa_id" in header:
            try:
                doc.commessa_id = int(header.get("commessa_id"))
            except Exception:
                pass
        # Campo partner_nome opzionale
        for k in ("partner_nome", "fornitore", "cliente", "partner"):
            if k in header:
                try:
                    setattr(doc, "partner_nome", str(header.get(k)))
                    break
                except Exception:
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
            if "um" in rj:
                r.um = (rj.get("um") or "").strip() or r.um
            if "quantita" in rj:
                try:
                    r.quantita = _to_decimal_nls(rj.get("quantita")) or D('0')
                except Exception:
                    pass
            if "prezzo" in rj:
                try:
                    r.prezzo = _to_decimal_nls(rj.get("prezzo")) or D('0')
                except Exception:
                    pass
            if "mastrino_codice" in rj:
                r.mastrino_codice = (rj.get("mastrino_codice") or "").strip() or None

        db.session.commit()

        # Ritorna lo stato aggiornato
        return api_document_json(id)
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


@docops_bp.post("/api/documents/<int:id>/convert-to-out")
def api_convert_to_out(id: int):
    """Crea un nuovo DDT_OUT copiando i dati dal DDT_IN di origine.
    Regole:
    - Copia tutte le righe (articolo, descrizione, quantita, prezzo, mastrino_codice)
    - Anno e data come il documento sorgente
    - Magazzino uguale al sorgente
    - partner_id: se il DDT IN ha commessa valorizzata, usa quella; altrimenti usa il partner originale
    - Stato iniziale: Bozza
    """
    doc = Documento.query.get_or_404(id)
    if doc.tipo != "DDT_IN":
        return jsonify({"ok": False, "error": "Solo i DDT IN possono essere trasformati."}), 400

    try:
        anno = getattr(doc, "anno", None) or date.today().year
        data = getattr(doc, "data", None) or date.today()

        # partner: commessa se presente, altrimenti fornitore originale
        partner_id = getattr(doc, "commessa_id", None) or getattr(doc, "partner_id", None)
        magazzino_id = getattr(doc, "magazzino_id", None)

        new_doc = Documento(
            tipo="DDT_OUT",
            numero=next_doc_number("DDT_OUT", anno),
            anno=anno,
            data=data,
            status="Bozza",
            partner_id=partner_id,
            magazzino_id=magazzino_id,
        )

        # mantieni eventuale commessa per tracciabilità
        try:
            new_doc.commessa_id = getattr(doc, "commessa_id", None)
        except Exception:
            pass

        db.session.add(new_doc)
        db.session.flush()  # per avere new_doc.id

        # copia righe
        try:
            rows = doc.righe.order_by(RigaDocumento.id).all()
        except Exception:
            rows = list(getattr(doc, "righe", []) or [])
            rows.sort(key=lambda x: x.id or 0)

        for r in rows:
            nr = RigaDocumento(
                documento_id=new_doc.id,
                articolo_id=getattr(r, "articolo_id", None),
                descrizione=getattr(r, "descrizione", None),
                quantita=getattr(r, "quantita", 0),
                prezzo=getattr(r, "prezzo", 0),
                mastrino_codice=getattr(r, "mastrino_codice", None),
            )
            db.session.add(nr)

        db.session.commit()
        # risposta
        from flask import url_for
        return jsonify({"ok": True, "id": new_doc.id, "url": url_for("documents.document_detail", id=new_doc.id) + "?edit=1"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500