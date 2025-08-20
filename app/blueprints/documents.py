from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import desc, or_
from datetime import datetime

from ..extensions import db
from ..models import Documento, Magazzino, Partner, RigaDocumento

documents_bp = Blueprint("documents", __name__)

DOCUMENTS_PER_PAGE = 25

def _parse_date_any(s):
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def _apply_filters(base_query, *, q_text=None, d_from=None, d_to=None, status=None):
    q = base_query
    if q_text:
        like = f"%{q_text.strip()}%"
        conds = []
        if hasattr(Documento, "partner_nome"):
            conds.append(Documento.partner_nome.ilike(like))
        if hasattr(Documento, "note"):
            conds.append(Documento.note.ilike(like))
        if conds:
            q = q.filter(or_(*conds))
    if d_from:
        q = q.filter(Documento.data >= d_from)
    if d_to:
        q = q.filter(Documento.data <= d_to)
    if status and status in ("Bozza","Confermato","Stornato","Annullato"):
        q = q.filter(Documento.status == status)
    return q.order_by(desc(Documento.anno), desc(Documento.numero), desc(Documento.id))

@documents_bp.get("/")
@documents_bp.get("")
def documents_list():
    return redirect(url_for("documents.documents_in"))

@documents_bp.get("/in")
def documents_in():
    q_text = request.args.get("q", type=str)
    d_from = _parse_date_any(request.args.get("from_date"))
    d_to   = _parse_date_any(request.args.get("to_date"))
    status = request.args.get("status", type=str)
    page   = request.args.get("page", 1, type=int)
    per    = request.args.get("per_page", DOCUMENTS_PER_PAGE, type=int)

    q = Documento.query.filter(Documento.tipo == "DDT_IN")
    q = _apply_filters(q, q_text=q_text, d_from=d_from, d_to=d_to, status=status)
    pager = q.paginate(page=page, per_page=per, error_out=False)

    return render_template("documents_in.html", pager=pager, docs=pager.items, status=status)

@documents_bp.get("/out")
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

@documents_bp.get("/<int:id>")
def document_detail(id: int):
    doc = Documento.query.get_or_404(id)
    return render_template("document_detail_v2.html", doc=doc)

# --- Creazione Manuale DDT IN ---
@documents_bp.get("/new-in")
def new_in_form():
    magazzini = Magazzino.query.order_by(Magazzino.codice).all()
    fornitori = Partner.query.filter_by(tipo='Fornitore').order_by(Partner.nome).all()
    clienti = Partner.query.filter_by(tipo='Cliente').order_by(Partner.nome).all()
    return render_template("document_new_in.html", magazzini=magazzini, fornitori=fornitori, clienti=clienti, today=datetime.today().date())

@documents_bp.post("/new-in")
def new_in_save():
    try:
        fornitore_nome = request.form.get("fornitore")
        mag_id = int(request.form.get("magazzino_id"))
        commessa_id = request.form.get("commessa_id")

        if not fornitore_nome or not mag_id:
            raise ValueError("Fornitore e magazzino sono obbligatori.")

        partner = Partner.query.filter_by(nome=fornitore_nome).first()
        if not partner:
            partner = Partner(nome=fornitore_nome, tipo='Fornitore')
            db.session.add(partner)
            db.session.flush()

        doc = Documento(
            tipo='DDT_IN',
            status='Bozza',
            partner_id=partner.id,
            magazzino_id=mag_id,
            commessa_id=(int(commessa_id) if commessa_id else None)
        )
        db.session.add(doc)
        db.session.commit()
        
        flash("Bozza DDT IN creata. Ora puoi aggiungere le righe.", "success")
        return redirect(url_for('documents.document_detail', id=doc.id))
    except Exception as e:
        db.session.rollback()
        flash(f"Errore creazione bozza: {e}", "error")
        return redirect(url_for('documents.new_in_form'))

# --- Creazione Manuale DDT OUT ---
@documents_bp.get("/new-out")
def new_out_form():
    magazzini = Magazzino.query.order_by(Magazzino.codice).all()
    clienti = Partner.query.filter_by(tipo='Cliente').order_by(Partner.nome).all()
    return render_template("document_new_out.html", 
                         magazzini=magazzini, 
                         clienti=clienti, 
                         today=datetime.today().date())

@documents_bp.post("/new-out")
def new_out_save():
    try:
        cliente_nome = request.form.get("cliente")
        mag_id = int(request.form.get("magazzino_id"))
        commessa_id = request.form.get("commessa_id")

        if not cliente_nome or not mag_id:
            raise ValueError("Cliente e magazzino sono obbligatori.")

        partner = Partner.query.filter_by(nome=cliente_nome).first()
        if not partner:
            partner = Partner(nome=cliente_nome, tipo='Cliente')
            db.session.add(partner)
            db.session.flush()

        doc = Documento(
            tipo='DDT_OUT',
            status='Bozza',
            partner_id=partner.id,
            magazzino_id=mag_id,
            commessa_id=(int(commessa_id) if commessa_id else None)
        )
        db.session.add(doc)
        db.session.commit()
        
        flash("Bozza DDT OUT creata. Ora puoi aggiungere le righe.", "success")
        return redirect(url_for('documents.document_detail', id=doc.id))
    except Exception as e:
        db.session.rollback()
        flash(f"Errore creazione bozza: {e}", "error")
        return redirect(url_for('documents.new_out_form'))

# --- Duplicazione DDT IN → DDT OUT ---
@documents_bp.get("/<int:id>/duplicate-to-out")
def duplicate_to_out_form(id: int):
    """Form per duplicare DDT IN come DDT OUT."""
    doc = Documento.query.get_or_404(id)
    if doc.tipo != 'DDT_IN':
        flash("Solo i DDT IN possono essere duplicati come DDT OUT.", "error")
        return redirect(url_for('documents.document_detail', id=id))
    
    magazzini = Magazzino.query.order_by(Magazzino.codice).all()
    clienti = Partner.query.filter_by(tipo='Cliente').order_by(Partner.nome).all()
    return render_template("document_duplicate_to_out.html", 
                         doc=doc, magazzini=magazzini, clienti=clienti)

@documents_bp.post("/<int:id>/duplicate-to-out")
def duplicate_to_out_save(id: int):
    """Salva duplicazione DDT IN → DDT OUT."""
    try:
        doc_in = Documento.query.get_or_404(id)
        if doc_in.tipo != 'DDT_IN':
            raise ValueError("Solo i DDT IN possono essere duplicati.")
        
        cliente_nome = request.form.get("cliente")
        mag_id = int(request.form.get("magazzino_id"))
        
        if not cliente_nome or not mag_id:
            raise ValueError("Cliente e magazzino sono obbligatori.")

        # Trova/crea cliente
        partner = Partner.query.filter_by(nome=cliente_nome).first()
        if not partner:
            partner = Partner(nome=cliente_nome, tipo='Cliente')
            db.session.add(partner)
            db.session.flush()

        # Crea nuovo DDT OUT
        doc_out = Documento(
            tipo='DDT_OUT',
            status='Bozza',
            partner_id=partner.id,
            magazzino_id=mag_id
        )
        db.session.add(doc_out)
        db.session.flush()

        # Duplica righe
        from ..models import RigaDocumento
        for riga_in in doc_in.righe:
            riga_out = RigaDocumento(
                documento_id=doc_out.id,
                articolo_id=riga_in.articolo_id,
                descrizione=riga_in.descrizione,
                quantita=riga_in.quantita,
                prezzo=riga_in.prezzo,
                mastrino_codice=riga_in.mastrino_codice
            )
            db.session.add(riga_out)

        db.session.commit()
        flash(f"DDT OUT creato dalla duplicazione del DDT IN #{doc_in.numero or doc_in.id}.", "success")
        return redirect(url_for('documents.document_detail', id=doc_out.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Errore duplicazione: {e}", "error")
        return redirect(url_for('documents.document_detail', id=id))
