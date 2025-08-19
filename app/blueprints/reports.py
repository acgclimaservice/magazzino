
from flask import Blueprint, render_template, request
from sqlalchemy import func, case
from app import db
from app.models import Document, DocumentLine

bp = Blueprint("reports", __name__, url_prefix="/reports")

@bp.get("/mastrini")
def report_mastrini():
    dfrom = request.args.get("date_from")
    dto = request.args.get("date_to")
    q = db.session.query(
        DocumentLine.mastrino_code,
        func.sum(case((DocumentLine.doc_type=="IN", DocumentLine.price*DocumentLine.quantity), else_=0)).label("tot_in"),
        func.sum(case((DocumentLine.doc_type=="OUT", DocumentLine.price*DocumentLine.quantity), else_=0)).label("tot_out"),
        func.sum(case((DocumentLine.doc_type=="IN", DocumentLine.quantity), else_=-DocumentLine.quantity)).label("saldo_qty")
    ).group_by(DocumentLine.mastrino_code)
    if dfrom or dto:
        q = q.join(Document, DocumentLine.document_id==Document.id)
        if dfrom: q = q.filter(Document.date >= dfrom)
        if dto: q = q.filter(Document.date <= dto)
    rows = q.all()
    return render_template("reports_mastrini.html", rows=rows, date_from=dfrom, date_to=dto)
