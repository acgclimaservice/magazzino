from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import asc, or_
from datetime import datetime
from ..extensions import db
from ..models import Documento, Partner, Magazzino

documents_bp = Blueprint("documents", __name__)

DOCUMENTS_PER_PAGE = 25

def _parse_date_any(s):
    if not s: return None
    s = str(s).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try: return datetime.strptime(s, fmt).date()
        except Exception: pass
    return None

def _apply_filters(q, q_text=None, d_from=None, d_to=None, status=None, commessa_id=None):
    if q_text:
        like = f"%{q_text}%"
        conds = []
        if hasattr(Documento, "partner_nome"):
            conds.append(Documento.partner_nome.ilike(like))
        if hasattr(Documento, "note"):
            conds.append(Documento.note.ilike(like))
        if conds:
            q = q.filter(or_(*conds))
    if d_from: q = q.filter(Documento.data >= d_from)
    if d_to:   q = q.filter(Documento.data <= d_to)
    if status and status in ("Bozza","Confermato","Stornato","Annullato"):
        q = q.filter(Documento.status == status)
    if commessa_id:
        q = q.filter(Documento.commessa_id == commessa_id)

    # ORDINAMENTO: Numero crescente (1 in alto). In subordine anno e id.
    return q.order_by(asc(Documento.numero), asc(Documento.anno), asc(Documento.id))

@documents_bp.get("/documents")
def documents_list():
    return redirect(url_for("documents.documents_in"))

@documents_bp.get("/documents/in")
def documents_in():
    q_text = request.args.get("q", type=str)
    d_from = _parse_date_any(request.args.get("from_date"))
    d_to   = _parse_date_any(request.args.get("to_date"))
    status = request.args.get("status", type=str)
    page   = request.args.get("page", 1, type=int)
    per    = request.args.get("per_page", DOCUMENTS_PER_PAGE, type=int)
    commessa_id = request.args.get('commessa_id', type=int)

    q = Documento.query.filter(Documento.tipo == "DDT_IN")
    q = _apply_filters(q, q_text=q_text, d_from=d_from, d_to=d_to, status=status, commessa_id=commessa_id)
    pager = q.paginate(page=page, per_page=per, error_out=False)

    commesse = Partner.query.filter_by(tipo='Cliente').order_by(Partner.nome).all()
    return render_template("documents_in.html",
                           pager=pager,
                           docs=pager.items,
                           status=status,
                           commesse=commesse,
                           show_commessa_filter=True,
                           commessa_id=commessa_id)
@documents_bp.get("/documents/out")
def documents_out():
    q_text = request.args.get("q", type=str)
    d_from = _parse_date_any(request.args.get("from_date"))
    d_to   = _parse_date_any(request.args.get("to_date"))
    status = request.args.get("status", type=str)
    page   = request.args.get("page", 1, type=int)
    per    = request.args.get("per_page", DOCUMENTS_PER_PAGE, type=int)

    q = Documento.query.filter(Documento.tipo == "DDT_OUT")
    q = _apply_filters(q, q_text=q_text, d_from=d_from, d_to=d_to, status=status)
    pager = q.paginate(page=page, per_page=per, error_out=False)
    return render_template("documents_out.html", pager=pager, docs=pager.items, status=status)

# ===== Manuale: Nuovo DDT IN =====
@documents_bp.get("/documents/new-in")
def new_in_form():
    mags = Magazzino.query.order_by(Magazzino.codice).all()
    fornitori = Partner.query.filter_by(tipo='Fornitore').order_by(Partner.nome).all()
    clienti = Partner.query.filter_by(tipo='Cliente').order_by(Partner.nome).all()
    return render_template("document_new_in.html", magazzini=mags, fornitori=fornitori, clienti=clienti, today=datetime.today().date())

@documents_bp.post("/documents/new-in")
def new_in_save():
    try:
        data_str = request.form.get("data")
        numero   = int(request.form.get("numero"))
        fornitore_nome = request.form.get("fornitore")
        mag_id = int(request.form.get("magazzino_id"))
        if not data_str or not numero or not fornitore_nome or not mag_id:
            raise ValueError("Dati insufficienti.")

        d = _parse_date_any(data_str) or datetime.today().date()
        anno = d.year

        # Partner
        partner = Partner.query.filter_by(nome=fornitore_nome).first()
        if partner is None:
            partner = Partner(nome=fornitore_nome, tipo='Fornitore')
            db.session.add(partner); db.session.flush()

        doc = Documento(tipo="DDT_IN", numero=numero, anno=anno, data=d, status="Bozza",
                        partner_id=partner.id, magazzino_id=mag_id,
                        commessa_id=(int(request.form.get("commessa_id")) if request.form.get("commessa_id") else None))
        db.session.add(doc); db.session.commit()
        flash("DDT IN creato (vuoto). Aggiungi righe e conferma dal dettaglio.", "success")
        return redirect(url_for("documents.document_detail", id=doc.id))
    except Exception as e:
        db.session.rollback()
        flash(f"Errore creazione: {e}", "error")
        return redirect(url_for("documents.new_in_form"))

# Reindirizza "Nuovo DDT OUT" alla UI esistente
@documents_bp.get("/documents/new-out")
def new_out_redirect():
    return redirect(url_for("importing.ddt_out_new"))

@documents_bp.get("/documents/<int:id>")
def document_detail(id: int):
    doc = Documento.query.get_or_404(id)
    return render_template("document_detail_v2.html", doc=doc)


@documents_bp.get("/documents/<int:id>/edit")
def document_edit(id: int):
    from flask import url_for, redirect
    return redirect(url_for("documents.document_detail", id=id) + "?edit=1")
