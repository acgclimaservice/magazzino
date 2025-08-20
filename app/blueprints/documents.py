from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import desc, or_
from datetime import datetime

from ..extensions import db
from ..models import Documento, Partner, Magazzino

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
        # Assumiamo che il modello Documento abbia una relazione 'partner'
        q = q.join(Documento.partner).filter(Partner.nome.ilike(like))

    if d_from:
        q = q.filter(Documento.data >= d_from)
    if d_to:
        q = q.filter(Documento.data <= d_to)
    if status and status in ("Bozza","Confermato","Stornato","Annullato"):
        q = q.filter(Documento.status == status)
    return q.order_by(desc(Documento.anno), desc(Documento.numero), desc(Documento.id))

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

    q = Documento.query.filter(Documento.tipo == "DDT_IN")
    q = _apply_filters(q, q_text=q_text, d_from=d_from, d_to=d_to, status=status)
    pager = q.paginate(page=page, per_page=per, error_out=False)

    return render_template("documents_in.html", pager=pager, docs=pager.items, status=status)

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

@documents_bp.get("/documents/<int:id>")
def document_detail(id: int):
    # Usa il template v2 che contiene la logica JS
    doc = Documento.query.get_or_404(id)
 return render_template("document_detail_v2.html", doc=doc)

# --- Creazione Manuale DDT IN ---
@documents_bp.get("/documents/new-in")
def new_in_form():
    """Mostra il form per creare l'intestazione di un nuovo DDT IN manuale."""
    magazzini = Magazzino.query.order_by(Magazzino.codice).all()
    fornitori = Partner.query.filter_by(tipo='Fornitore').order_by(Partner.nome).all()
    clienti = Partner.query.filter_by(tipo='Cliente').order_by(Partner.nome).all()
    return render_template("document_new_in.html", magazzini=magazzini, fornitori=fornitori, clienti=clienti, today=datetime.today().date())

@documents_bp.post("/documents/new-in")
def new_in_save():
    """Salva l'intestazione di un nuovo DDT IN e reindirizza alla modifica."""
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
        
        flash("Bozza DDT creata. Ora puoi aggiungere le righe.", "success")
        return redirect(url_for('documents.document_detail', id=doc.id))
    except Exception as e:
        db.session.rollback()
        flash(f"Errore creazione bozza: {e}", "error")
        return redirect(url_for('documents.new_in_form'))
