from flask import Blueprint, render_template, request, jsonify, url_for, current_app
from sqlalchemy.exc import IntegrityError
from decimal import Decimal, InvalidOperation
from ..extensions import db
from ..models import Articolo, Magazzino, Partner, Documento, RigaDocumento, Movimento, Mastrino, Allegato
from ..utils import parse_it_date, q_dec, money_dec, next_doc_number, unify_um, supplier_prefix, gen_internal_code
from ..services.parsing_service import extract_text_from_pdf, build_prompt, call_gemini, parse_ddt_with_fallback, parse_ddt_duotermica
from ..services.file_service import save_upload, move_upload_to_document
import os, re

importing_bp = Blueprint("importing", __name__)

# ===== UI =====
@importing_bp.route('/workstation')
def workstation():
    return render_template('workstation.html')

@importing_bp.route('/import-pdf')
def import_pdf():
    return render_template('import_pdf.html')

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
    s = str(x).strip().replace('€','').replace('\\xa0','').replace(' ', '').replace(',', '.')
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
    db.session.add(m); db.session.flush()
    return m.codice

def _default_ricavo_mastrino():
    m = Mastrino.query.filter_by(tipo='RICAVO').order_by(Mastrino.codice).first()
    if m:
        return m.codice
    m = Mastrino(codice='0700001000', descrizione='RICAVI MERCI', tipo='RICAVO')
    db.session.add(m); db.session.flush()
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

        data, method, note = parse_ddt_with_fallback(raw_text)

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
        # DUOTERMICA: forza mappatura QUANT./NETTO CAD. usando il PDF caricato
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
            "data": d.get("data"),
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
        data_str = payload.get("data")
        fornitore_nome = payload.get("fornitore")
        righe = payload.get("righe") or []
        rel_upload = payload.get("uploaded_file")
        # DUOTERMICA: ricalcolo righe dal PDF per mappare QUANT./NETTO CAD.
        if (fornitore_nome or "").upper().find("DUOTERMICA") >= 0 and rel_upload:
            try:
                import os
                abs_path = os.path.join(current_app.root_path, rel_upload.lstrip("/\\"))
                raw = extract_text_from_pdf(abs_path)
                vparsed = parse_ddt_duotermica(raw) or {}
                vrows = vparsed.get("righe") or []
                if vrows:
                    righe = vrows
            except Exception as e:
                current_app.logger.warning(f"DUOTERMICA confirm override fallito: {e}")
        
        mag_id = payload.get("magazzino_id")
        mastrino_default = (payload.get("mastrino_codice") or "").strip()  # opzionale, usato come fallback
        if not data_str or not fornitore_nome or not righe:
            return jsonify({"ok": False, "error": "Dati insufficienti (data, fornitore, righe)"}), 400

        from decimal import Decimal as D
        doc_date = parse_it_date(data_str)
        anno = doc_date.year

        # Partner
        partner = Partner.query.filter_by(nome=fornitore_nome).first()
        if partner is None:
            partner = Partner(nome=fornitore_nome, tipo='Fornitore')
            db.session.add(partner)
            db.session.flush()
        elif partner.tipo != 'Fornitore':
            partner.tipo = 'Fornitore'

        # Magazzino
        mag = Magazzino.query.get(int(mag_id)) if mag_id else Magazzino.query.order_by(Magazzino.id).first()
        if not mag:
            return jsonify({"ok": False, "error": "Nessun magazzino configurato"}), 400

        # Default mastrino
        if mastrino_default:
            m = Mastrino.query.filter_by(codice=mastrino_default).first()
            if not m:
                mastrino_default = _default_acquisto_mastrino()
        else:
            mastrino_default = _default_acquisto_mastrino()

        # Documento
        commessa_id = payload.get('commessa_id')
        try:
            commessa_id = int(commessa_id) if commessa_id not in (None, '', 'null') else None
        except Exception:
            commessa_id = None
        doc = Documento(tipo='DDT_IN', anno=anno, data=doc_date, partner_id=partner.id, magazzino_id=mag.id, commessa_id=commessa_id, status='Bozza')
        for _ in range(3):
            doc.numero = next_doc_number('DDT_IN', anno)
            try:
                db.session.add(doc)
                db.session.flush()
                break
            except IntegrityError:
                db.session.rollback()
        else:
            return jsonify({"ok": False, "error": "Assegnazione numero documento fallita"}), 500

        # Righe
        pref = supplier_prefix(fornitore_nome)
        for r in righe:
            sup_code = (r.get('codice') or '').strip()
            descr = (r.get('descrizione') or '').strip() or sup_code or "Articolo"
            qty_raw = r.get('quantità') if 'quantità' in r else r.get('quantita') if 'quantita' in r else r.get('qty')
            um = unify_um(r.get('um'))
            qty_dec = _to_decimal(qty_raw) or D('0')
            unit_price = _extract_unit_price(r, qty_dec)
            if qty_raw in (None, ''):
                raise ValueError(f"Quantità mancante per riga con codice fornitore '{sup_code or 'N/A'}'")

            # mastrino per riga
            mastrino_row = (r.get('mastrino_codice') or '').strip()
            if mastrino_row:
                m = Mastrino.query.filter_by(codice=mastrino_row).first()
                if not m:
                    mastrino_row = mastrino_default
            else:
                mastrino_row = mastrino_default

            art = None
            if sup_code:
                art = Articolo.query.filter_by(codice_fornitore=sup_code, fornitore=fornitore_nome).first()
                if not art:
                    art = Articolo.query.filter_by(codice_interno=sup_code).first()  # legacy

            if art is None:
                internal = gen_internal_code(pref, supplier_code=sup_code or None)
                art = Articolo(
                    codice_interno=internal,
                    codice_fornitore=sup_code or None,
                    descrizione=descr,
                    fornitore=fornitore_nome,
                    last_cost=(unit_price.quantize(D('0.01')) if unit_price is not None else D('0.00'))
                )
                db.session.add(art)
                db.session.flush()
            else:
                if sup_code and not art.codice_fornitore:
                    art.codice_fornitore = sup_code
                if not art.fornitore:
                    art.fornitore = fornitore_nome
                art.last_cost = (unit_price.quantize(D('0.01')) if unit_price is not None else D('0.00'))

            riga = RigaDocumento(
                documento_id=doc.id,
                articolo_id=art.id,
                descrizione=f"{descr} [{um}]",
                quantita=q_dec(qty_raw),
                prezzo=unit_price.quantize(D('0.01')) if unit_price is not None else D('0.00'),
                mastrino_codice=mastrino_row
            )
            db.session.add(riga)

        # Allegato PDF originale (se disponibile)
        if rel_upload:
            try:
                new_rel, new_abs = move_upload_to_document(rel_upload, doc.id)
                # Rinomina con prefisso IMPORTATO_ per tracciamento univoco (best effort)
                try:
                    import os
                    dir_abs = os.path.dirname(new_abs)
                    base = os.path.basename(new_abs)
                    if not base.upper().startswith("IMPORTATO_"):
                        new_base = f"IMPORTATO_{base}"
                        pref_abs = os.path.join(dir_abs, new_base)
                        os.rename(new_abs, pref_abs)
                        new_abs = pref_abs
                        rel_dir = os.path.dirname(new_rel).replace('\\', '/')
                        new_rel = f"{rel_dir}/{new_base}".lstrip('/')
                except Exception:
                    pass
                size = os.path.getsize(new_abs) if os.path.exists(new_abs) else 0
                allegato = Allegato(
                    documento_id=doc.id,
                    filename=os.path.basename(new_abs),
                    mime='application/pdf',
                    path=new_rel,
                    size=size
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
        data_str = payload.get("data")
        cliente_nome = payload.get("cliente")
        mag_id = payload.get("magazzino_id")
        righe = payload.get("righe") or []
        if not data_str or not cliente_nome or not mag_id or not righe:
            return jsonify({"ok": False, "error": "Dati insufficienti (data, cliente, magazzino, righe)"}), 400

        from decimal import Decimal as D
        doc_date = parse_it_date(data_str)
        anno = doc_date.year

        # Partner (Cliente)
        partner = Partner.query.filter_by(nome=cliente_nome).first()
        if partner is None:
            partner = Partner(nome=cliente_nome, tipo='Cliente')
            db.session.add(partner)
            db.session.flush()
        elif partner.tipo != 'Cliente':
            partner.tipo = 'Cliente'

        # Magazzino
        mag = Magazzino.query.get(int(mag_id))
        if not mag:
            return jsonify({"ok": False, "error": "Magazzino non trovato"}), 400

        # Documento DDT_OUT
        doc = Documento(tipo='DDT_OUT', anno=anno, data=doc_date, partner_id=partner.id, magazzino_id=mag.id, status='Bozza')
        for _ in range(3):
            doc.numero = next_doc_number('DDT_OUT', anno)
            try:
                db.session.add(doc)
                db.session.flush()
                break
            except IntegrityError:
                db.session.rollback()
        else:
            return jsonify({"ok": False, "error": "Assegnazione numero documento fallita"}), 500

        
        # Righe con mastrino per riga (RICAVO) — robusto e tollerante
        default_m = _default_ricavo_mastrino()
        errors = []
        for idx, r in enumerate(righe, start=1):
            try:
                codice = (r.get('codice') or '').strip()
                descr = (r.get('descrizione') or '').strip() or codice or 'Articolo'
                qty_raw = r.get('quantità') if 'quantità' in r else r.get('quantita') if 'quantita' in r else r.get('qty')
                if qty_raw in (None, ''):
                    raise ValueError("Quantità mancante")

                um = unify_um(r.get('um'))
                qty_dec = q_dec(qty_raw, field="Quantità")
                price = _extract_unit_price(r, qty_dec)  # prezzo di vendita

                mastrino_row = (r.get('mastrino_codice') or '').strip() or default_m
                m = Mastrino.query.filter_by(codice=mastrino_row).first()
                if not m:
                    mastrino_row = default_m

                # Articolo: cerca per codice interno, poi fornitore; fallback crea nuovo
                art = None
                if codice:
                    art = Articolo.query.filter_by(codice_interno=codice).first()
                    if not art:
                        art = Articolo.query.filter_by(codice_fornitore=codice).first()
                if art is None:
                    internal = gen_internal_code('OUT', supplier_code=codice or None)
                    art = Articolo(codice_interno=internal, codice_fornitore=None, descrizione=descr)
                    db.session.add(art); db.session.flush()

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

# ===== Endpoints supporto (combo) =====
@importing_bp.route("/api/magazzini")
def api_magazzini():
    rows = Magazzino.query.order_by(Magazzino.codice).all()
    return jsonify([{"id": m.id, "codice": m.codice, "nome": m.nome} for m in rows])


@importing_bp.route("/api/clienti")
def api_clienti():
    rows = Partner.query.filter_by(tipo='Cliente').order_by(Partner.nome).all()
    return jsonify([{"id": c.id, "nome": c.nome} for c in rows])

@importing_bp.route("/api/mastrini")
def api_mastrini():
    tipo = (request.args.get("tipo") or "").upper()
    q = Mastrino.query
    if tipo in ("ACQUISTO", "RICAVO"):
        q = q.filter_by(tipo=tipo)
    rows = q.order_by(Mastrino.codice).all()
    return jsonify([{"codice": m.codice, "descrizione": m.descrizione, "tipo": m.tipo} for m in rows])

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


@importing_bp.route("/api/inventory/search", methods=["GET"])
def api_inventory_search():
    # import locali per evitare NameError anche con import globali non aggiornati
    try:
        from ..models import Giacenza, Articolo
        from sqlalchemy import or_
    except Exception as e:
        current_app.logger.exception("Import error in api_inventory_search")
        return jsonify({"ok": False, "error": f"import error: {e}"}), 500

    try:
        mag_id = request.args.get("magazzino_id", type=int)
        q = (request.args.get("q") or "").strip()
        limit = min(max(request.args.get("limit", default=25, type=int), 1), 100)
        if not mag_id:
            return jsonify({"ok": False, "error": "magazzino_id mancante"}), 400

        qry = db.session.query(Giacenza, Articolo)\
            .join(Articolo, Articolo.id == Giacenza.articolo_id)\
            .filter(Giacenza.magazzino_id == mag_id, Giacenza.quantita > 0)

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
        for g,a in rows:
            try:
                qty = float(g.quantita)
            except Exception:
                qty = None
            out.append({
                "articolo_id": a.id,
                "codice_interno": a.codice_interno,
                "codice_fornitore": a.codice_fornitore,
                "descrizione": a.descrizione,
                "giacenza": qty
            })
        return jsonify(out)
    except Exception as e:
        current_app.logger.exception("Errore in api_inventory_search")
        return jsonify({"ok": False, "error": str(e)}), 500
