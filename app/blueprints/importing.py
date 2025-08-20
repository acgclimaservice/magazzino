from ..services.parsing_service import parse_ddt_with_fallback
from ..services.supplier_parsers import parse_supplier_specific
from flask import Blueprint, render_template, request, jsonify, url_for, current_app, send_from_directory, abort
from sqlalchemy.exc import IntegrityError
from decimal import Decimal, InvalidOperation
from werkzeug.utils import safe_join
from ..extensions import db
from ..models import Articolo, Magazzino, Partner, Documento, RigaDocumento, Movimento, Mastrino, Allegato
from ..utils import parse_it_date, q_dec, money_dec, next_doc_number, unify_um, supplier_prefix, gen_internal_code
from ..services.parsing_service import extract_text_from_pdf, build_prompt, call_gemini, parse_ddt_with_fallback, parse_ddt_duotermica
from ..services.supplier_parsers import parse_supplier_specific
from ..services.file_service import save_upload, move_upload_to_document
import os, re

importing_bp = Blueprint("importing", __name__)

# ===== UI =====
@importing_bp.route('/workstation')
def workstation():
    return render_template('workstation.html')

@importing_bp.route('/import-pdf')
def import_pdf():
    return render_template('import/ddt.html')

@importing_bp.route('/ddt-out/new')
def ddt_out_new():
    return render_template('ddt_out_new.html')

# ===== Helpers =====
def _to_decimal(x):
    if x is None:
        return None
    if isinstance(x, (int, float, Decimal)):
        try:
            return Decimal(str(x))
        except Exception:
            return None
    s = str(x).strip().replace('â‚¬','').replace('\\xa0','').replace(' ', '').replace(',', '.')
    m = re.search(r'[-+]?\\d+(?:\\.\\d+)?', s)
    if not m:
        return None
    try:
        return Decimal(m.group(0))
    except InvalidOperation:
        return None

def _extract_unit_price(row, qty_dec: Decimal | None):
    for k in ['prezzo_unitario', 'prezzo', 'unit_price', 'importo_unitario']:
        v = row.get(k)
        val = _to_decimal(v)
        if val is not None:
            return val
    for k in ['totale_riga', 'totale', 'importo', 'importo_riga']:
        v = row.get(k)
        tot = _to_decimal(v)
        if tot is not None and qty_dec and qty_dec != 0:
            try:
                return (tot / qty_dec).quantize(Decimal('0.01'))
            except Exception:
                pass
    return Decimal('0.00')

def _default_acquisto_mastrino():
    m = Mastrino.query.filter_by(tipo='ACQUISTO').order_by(Mastrino.codice).first()
    if m:
        return m.codice
    m = Mastrino(codice='0590001003', descrizione='ACQUISTO MATERIALE DI CONSUMO', tipo='ACQUISTO')
    db.session.add(m)
    db.session.flush()
    return m.codice

def _default_ricavo_mastrino():
    m = Mastrino.query.filter_by(tipo='RICAVO').order_by(Mastrino.codice).first()
    if m:
        return m.codice
    m = Mastrino(codice='0700001000', descrizione='RICAVI MERCI', tipo='RICAVO')
    db.session.add(m)
    db.session.flush()
    return m.codice

# ===== Parsing generico (LLM / Fallback) =====
def _parse_generic(kind: str):
    try:
        file = request.files.get("pdf_file")
        if not file:
            return jsonify({"ok": False, "type": kind, "error": "Nessun file ricevuto"}), 400
        file.stream.seek(0)
        raw_text = extract_text_from_pdf(file)
        file.stream.seek(0)
        data = call_gemini(build_prompt(kind, raw_text))
        return jsonify({"ok": True, "type": kind, "data": data})
    except Exception as e:
        current_app.logger.exception("Errore in _parse_generic(%s)", kind)
        return jsonify({"ok": False, "type": kind, "error": str(e)}), 500

@importing_bp.route("/api/parse-ticket", methods=["POST"])
def api_parse_ticket():
    return _parse_generic("ticket")

@importing_bp.route("/api/parse-materiali", methods=["POST"])
def api_parse_materiali():
    return _parse_generic("materiali")

@importing_bp.route("/api/parse-ddt", methods=["POST"])
def api_parse_ddt():
    """Parse DDT + salva PDF originale per allegarlo in conferma.
       Se l'LLM va in timeout, usa parser locale di fallback e continua."""
    try:
        file = request.files.get("pdf_file")
        if not file:
            return jsonify({"ok": False, "type": "ddt", "error": "Nessun file ricevuto"}), 400
        file.stream.seek(0)
        raw_text = extract_text_from_pdf(file)
        file.stream.seek(0)
        rel_path, abs_path = save_upload(file, category="incoming_ddt")

        data, method = parse_supplier_specific(raw_text)
        note = method

        resp = {"ok": True, "type": "ddt", "data": data, "uploaded_file": rel_path, "method": method}
        if note:
            resp["note"] = note
        return jsonify(resp)
    except Exception as e:
        current_app.logger.exception("Errore in api_parse_ddt")
        return jsonify({"ok": False, "type": "ddt", "error": str(e)}), 500

# ===== Preview DDT IN =====
@importing_bp.route("/api/import-ddt-preview", methods=["POST"])
def import_ddt_preview():
    try:
        payload = request.get_json()
        if not payload or not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "Nessun dato ricevuto"}), 400
        d = payload.get("data") or {}
        righe = d.get("righe") or d.get("articoli") or []
        
        vendor = ((d.get("fornitore") or "") or "").upper()
        if "DUOTERMICA" in vendor:
            rel = (payload.get("uploaded_file") or "").lstrip("/\\")
            if rel:
                try:
                    import os
                    abs_path = os.path.join(current_app.root_path, rel)
                    raw = extract_text_from_pdf(abs_path)
                    vparsed = parse_ddt_duotermica(raw) or {}
                    vrows = vparsed.get("righe") or []
                    if vrows:
                        righe = vrows
                except Exception as e:
                    current_app.logger.warning(f"DUOTERMICA preview override fallito: {e}")
        
        for r in righe:
            r["um"] = unify_um(r.get("um"))
        preview = {
            "fornitore": d.get("fornitore"),
            "righe": righe,
            "uploaded_file": payload.get("uploaded_file")
        }
        if not preview["righe"]:
            return jsonify({"ok": False, "error": "Nessuna riga trovata"}), 400
        return jsonify({"ok": True, "preview": preview})
    except Exception as e:
        current_app.logger.exception("Errore in import_ddt_preview")
        return jsonify({"ok": False, "error": str(e)}), 500

# ===== Conferma DDT IN =====
@importing_bp.route("/api/import-ddt-confirm", methods=["POST"])
def import_ddt_confirm():
    try:
        payload = request.get_json(force=True)
        fornitore_nome = payload.get("fornitore")
        righe = payload.get("righe") or []
        rel_upload = payload.get("uploaded_file")
        
        if not fornitore_nome or not righe:
            return jsonify({"ok": False, "error": "Dati insufficienti (fornitore, righe)"}), 400

        # Partner
        partner = Partner.query.filter_by(nome=fornitore_nome).first()
        if partner is None:
            partner = Partner(nome=fornitore_nome, tipo='Fornitore')
            db.session.add(partner)
            db.session.flush()
        elif partner.tipo != 'Fornitore':
            partner.tipo = 'Fornitore'

        # Magazzino
        mag_id = payload.get("magazzino_id")
        mag = Magazzino.query.get(int(mag_id)) if mag_id else Magazzino.query.order_by(Magazzino.id).first()
        if not mag:
            return jsonify({"ok": False, "error": "Nessun magazzino configurato"}), 400

        mastrino_default = _default_acquisto_mastrino()

        # Documento
        commessa_id = payload.get('commessa_id')
        try:
            commessa_id = int(commessa_id) if commessa_id not in (None, '', 'null') else None
        except Exception:
            commessa_id = None
        doc = Documento(
            tipo='DDT_IN', 
            partner_id=partner.id, 
            magazzino_id=mag.id, 
            commessa_id=commessa_id, 
            status='Bozza'
        )
        # Salva riferimento DDT fornitore
        db.session.flush()

        # Righe
        pref = supplier_prefix(fornitore_nome)
        for r in righe:
            sup_code = (r.get('codice') or '').strip()
            descr = (r.get('descrizione') or '').strip() or sup_code or "Articolo"
            
            qty_raw = r.get('quantità') or r.get('quantitÃ ') or r.get('quantita') or r.get('qty')
            
            um = unify_um(r.get('um'))
            qty_dec = _to_decimal(qty_raw) or Decimal('0')
            unit_price = _extract_unit_price(r, qty_dec)
            
            if qty_raw in (None, ''):
                raise ValueError(f"Quantità mancante per riga con codice fornitore '{sup_code or 'N/A'}'")

            mastrino_row = (r.get('mastrino_codice') or '').strip() or mastrino_default

            art = None
            if sup_code:
                art = Articolo.query.filter_by(codice_fornitore=sup_code, fornitore=fornitore_nome).first()
            if not art:
                art = Articolo.query.filter_by(codice_interno=sup_code).first()

            if art is None:
                internal = gen_internal_code(pref, supplier_code=sup_code or None)
                art = Articolo(
                    codice_interno=internal,
                    codice_fornitore=sup_code or None,
                    descrizione=descr,
                    fornitore=fornitore_nome,
                    last_cost=(unit_price.quantize(Decimal('0.01')) if unit_price is not None else Decimal('0.00'))
                )
                db.session.add(art)
                db.session.flush()
            else:
                if sup_code and not art.codice_fornitore:
                    art.codice_fornitore = sup_code
                if not art.fornitore:
                    art.fornitore = fornitore_nome
                art.last_cost = (unit_price.quantize(Decimal('0.01')) if unit_price is not None else Decimal('0.00'))

            riga = RigaDocumento(
                documento_id=doc.id,
                articolo_id=art.id,
                descrizione=f"{descr} [{um}]",
                quantita=q_dec(str(qty_raw)),
                prezzo=unit_price.quantize(Decimal('0.01')) if unit_price is not None else Decimal('0.00'),
                mastrino_codice=mastrino_row
            )
            db.session.add(riga)

        if rel_upload:
            try:
                new_rel, new_abs = move_upload_to_document(rel_upload, doc.id)
                allegato = Allegato(
                    documento_id=doc.id,
                    filename=os.path.basename(new_abs),
                    mime='application/pdf',
                    path=new_rel,
                    size=os.path.getsize(new_abs) if os.path.exists(new_abs) else 0
                )
                db.session.add(allegato)
            except Exception:
                pass

        db.session.commit()
        return jsonify({"ok": True, "document_id": doc.id, "redirect_url": url_for('documents.document_detail', id=doc.id)})
    except Exception as e:
        current_app.logger.exception("Errore in import_ddt_confirm")
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

# ===== Creazione DDT OUT (nuovo flusso manuale) =====
@importing_bp.route("/api/ddt-out/create", methods=["POST"])
def api_ddt_out_create():
    try:
        payload = request.get_json(force=True)
        cliente_nome = payload.get("cliente")
        mag_id = payload.get("magazzino_id")
        righe = payload.get("righe") or []
        if not cliente_nome or not mag_id or not righe:
            return jsonify({"ok": False, "error": "Dati insufficienti (cliente, magazzino, righe)"}), 400

        partner = Partner.query.filter_by(nome=cliente_nome).first()
        if partner is None:
            partner = Partner(nome=cliente_nome, tipo='Cliente')
            db.session.add(partner)
            db.session.flush()
        elif partner.tipo != 'Cliente':
            partner.tipo = 'Cliente'

        mag = Magazzino.query.get(int(mag_id))
        if not mag:
            return jsonify({"ok": False, "error": "Magazzino non trovato"}), 400

        doc = Documento(tipo='DDT_OUT', partner_id=partner.id, magazzino_id=mag.id, status='Bozza')
        # Salva riferimento DDT fornitore
        if parsed.get('numero_ddt') and parsed.get('data'):
            doc.riferimento_fornitore = f"DDT {parsed.get('numero_ddt')} del {parsed.get('data')}"
        db.session.add(doc)
        db.session.flush()
        
        default_m = _default_ricavo_mastrino()
        errors = []
        for idx, r in enumerate(righe, start=1):
            try:
                codice = (r.get('codice') or '').strip()
                descr = (r.get('descrizione') or '').strip() or codice or 'Articolo'
                
                qty_raw = r.get('quantità') or r.get('quantitÃ ') or r.get('quantita') or r.get('qty')
                
                if qty_raw in (None, ''):
                    raise ValueError("Quantità mancante")

                um = unify_um(r.get('um'))
                qty_dec = q_dec(str(qty_raw), field="Quantità")
                price = _extract_unit_price(r, qty_dec)

                mastrino_row = (r.get('mastrino_codice') or '').strip() or default_m
                m = Mastrino.query.filter_by(codice=mastrino_row).first()
                if not m:
                    mastrino_row = default_m

                art = None
                if codice:
                    art = Articolo.query.filter_by(codice_interno=codice).first()
                if art is None:
                    internal = gen_internal_code('OUT', supplier_code=codice or None)
                    art = Articolo(codice_interno=internal, descrizione=descr)
                    db.session.add(art)
                    db.session.flush()

                riga = RigaDocumento(
                    documento_id=doc.id,
                    articolo_id=art.id,
                    descrizione=descr,
                    quantita=qty_dec,
                    prezzo=price,
                    mastrino_codice=mastrino_row
                )
                db.session.add(riga)

            except Exception as e:
                errors.append(f"Riga {idx}: {str(e)}")

        if errors:
            raise ValueError(" ; ".join(errors))

        db.session.commit()
        return jsonify({"ok": True, "document_id": doc.id, "redirect_url": url_for('documents.document_detail', id=doc.id)})
    except Exception as e:
        current_app.logger.exception("Errore in api_ddt_out_create")
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

# ===== Rotte di test (clear) =====
def _clear_docs_by_type(tipo: str):
    ids = [row.id for row in Documento.query.filter_by(tipo=tipo).all()]
    if not ids:
        return 0
    db.session.query(RigaDocumento).filter(RigaDocumento.documento_id.in_(ids)).delete(synchronize_session=False)
    db.session.query(Movimento).filter(Movimento.documento_id.in_(ids)).delete(synchronize_session=False)
    db.session.query(Allegato).filter(Allegato.documento_id.in_(ids)).delete(synchronize_session=False)
    db.session.query(Documento).filter(Documento.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return len(ids)

@importing_bp.route('/test/clear-ddt-in', methods=['POST'])
def clear_ddt_in():
    try:
        n = _clear_docs_by_type('DDT_IN')
        return jsonify({"ok": True, "msg": f"DDT IN eliminati: {n}"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

@importing_bp.route('/test/clear-ddt-out', methods=['POST'])
def clear_ddt_out():
    try:
        n = _clear_docs_by_type('DDT_OUT')
        return jsonify({"ok": True, "msg": f"DDT OUT eliminati: {n}"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

@importing_bp.route('/test/clear-articles', methods=['POST'])
def clear_articles():
    try:
        from ..models import Giacenza
        db.session.query(RigaDocumento).delete(synchronize_session=False)
        db.session.query(Movimento).delete(synchronize_session=False)
        db.session.query(Allegato).delete(synchronize_session=False)
        db.session.query(Giacenza).delete(synchronize_session=False)
        db.session.query(Articolo).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({"ok": True, "msg": "Tutti gli articoli eliminati"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

# ===== FUNZIONE DI RICERCA CORRETTA =====
@importing_bp.route("/api/inventory/search", methods=["GET"])
def api_inventory_search():
    try:
        from ..models import Giacenza, Articolo
        from sqlalchemy import or_
    except Exception as e:
        current_app.logger.exception("Import error in api_inventory_search")
        return jsonify({"ok": False, "error": f"import error: {e}"}), 500

    try:
        mag_id = request.args.get("magazzino_id", type=int)
        q = (request.args.get("q") or "").strip()
        limit = min(max(request.args.get("limit", 25, type=int), 1), 100)
        
        if not mag_id:
             default_mag = Magazzino.query.order_by(Magazzino.id).first()
             if default_mag:
                 mag_id = default_mag.id
             else:
                 return jsonify({"ok": False, "error": "Nessun magazzino configurato"}), 400

        # NUOVA LOGICA: Cerca in tutto il catalogo Articoli e collega opzionalmente la Giacenza
        qry = db.session.query(Articolo, Giacenza.quantita)\
            .outerjoin(Giacenza, (Giacenza.articolo_id == Articolo.id) & (Giacenza.magazzino_id == mag_id))

        if q:
            toks = [t for t in q.split() if t]
            for t in toks:
                like = f"%{t}%"
                qry = qry.filter(
                    or_(Articolo.codice_interno.ilike(like),
                        Articolo.codice_fornitore.ilike(like),
                        Articolo.descrizione.ilike(like))
                )

        rows = qry.order_by(Articolo.descrizione.asc()).limit(limit).all()
        out = []
        for a, g_quantita in rows:
            try:
                qty = float(g_quantita) if g_quantita is not None else 0.0
            except Exception:
                qty = 0.0
            
            out.append({
                "articolo_id": a.id,
                "codice_interno": a.codice_interno,
                "codice_fornitore": a.codice_fornitore,
                "descrizione": a.descrizione,
                "giacenza": qty,
                "last_cost": float(a.last_cost) if a.last_cost is not None else 0.0
            })
        return jsonify(out)
    except Exception as e:
        current_app.logger.exception("Errore in api_inventory_search")
        return jsonify({"ok": False, "error": str(e)}), 500

# ===== GESTIONE DOWNLOAD ALLEGATI =====
@importing_bp.route('/files/download/<int:id>')
def download_allegato(id):
    """
    Permette di scaricare un file allegato a un documento.
    """
    # Cerca l'allegato nel database o restituisce 404 se non esiste
    allegato = Allegato.query.get_or_404(id)
    
    # Costruisce in modo sicuro il percorso assoluto del file sul server,
    # partendo dalla root del progetto (la cartella sopra 'app').
    project_root = os.path.dirname(current_app.root_path)
    file_path = safe_join(project_root, allegato.path)
    
    # Controlla se il file esiste fisicamente, altrimenti restituisce 404.
    if not os.path.isfile(file_path):
        current_app.logger.error(f"Tentativo di download fallito. File non trovato: {file_path}")
        abort(404)
        
    # Usa send_from_directory per inviare il file in modo sicuro.
    # Richiede la cartella e il nome del file separati.
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    
    return send_from_directory(directory, filename, as_attachment=True)
