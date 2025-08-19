
from app import db

class StockMove(db.Model):
    __tablename__ = "stock_moves"
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, index=True, nullable=False)
    document_type = db.Column(db.String(10), nullable=False)  # IN/OUT/INT
    date = db.Column(db.Date, nullable=False, index=True)
    sku = db.Column(db.String(120), index=True, nullable=False)
    qty = db.Column(db.Numeric(12,3), nullable=False)
    uom = db.Column(db.String(20), default="pz")
    wh_from = db.Column(db.String(120))
    wh_to = db.Column(db.String(120))
    source_label = db.Column(db.String(120))  # campo “da”
    note = db.Column(db.String(255))

def record_from_ddt_in(document, lines, dest_wh_code:str, supplier_code:str):
    for ln in lines:
        db.session.add(StockMove(
            document_id=document.id, document_type="IN", date=document.date,
            sku=getattr(ln, "sku", getattr(ln, "article_code", "")),
            qty=getattr(ln, "qty", getattr(ln, "quantity", 0)),
            uom=getattr(ln, "uom", "pz"), wh_from=None, wh_to=dest_wh_code,
            source_label=supplier_code or "", note=f"DDT IN {getattr(document,'number','')}"
        ))
    db.session.commit()

def record_from_ddt_out(document, lines, src_wh_code:str):
    for ln in lines:
        db.session.add(StockMove(
            document_id=document.id, document_type="OUT", date=document.date,
            sku=getattr(ln, "sku", getattr(ln, "article_code", "")),
            qty=-abs(getattr(ln, "qty", getattr(ln, "quantity", 0))),
            uom=getattr(ln, "uom", "pz"), wh_from=src_wh_code, wh_to=None,
            source_label=None, note=f"DDT OUT {getattr(document,'number','')}"
        ))
    db.session.commit()
