
from datetime import datetime
from app import db
from sqlalchemy import UniqueConstraint

class MastrinoLink(db.Model):
    __tablename__ = "mastrino_links"
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(120))
    purchase_code = db.Column(db.String(120), nullable=False, index=True)
    sale_code = db.Column(db.String(120), nullable=False, index=True)
    __table_args__ = (UniqueConstraint('purchase_code', name='uq_mastrino_links_purchase'),)

class MastrinoOverride(db.Model):
    __tablename__ = "mastrino_overrides"
    id = db.Column(db.Integer, primary_key=True)
    article_code = db.Column(db.String(120), index=True, nullable=False)
    purchase_code = db.Column(db.String(120))
    sale_code = db.Column(db.String(120), nullable=False)
    reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def load_mapping_from_dataframe(df):
    norm = []
    for _, r in df.iterrows():
        m = {str(k).strip().lower(): r[k] for k in df.columns}
        cat = m.get('categoria') or m.get('category')
        purch = (m.get('mastrino_acquisto') or m.get('acquisti') or m.get('mastrino acquisto') or "").strip()
        sale = (m.get('mastrino_vendita') or m.get('vendite') or m.get('mastrino vendita') or "").strip()
        if purch and sale:
            norm.append((cat, purch, sale))
    c = 0
    for cat, purch, sale in norm:
        row = MastrinoLink.query.filter_by(purchase_code=purch).first()
        if row:
            row.sale_code = sale; row.category = cat
        else:
            db.session.add(MastrinoLink(category=cat, purchase_code=purch, sale_code=sale))
        c += 1
    db.session.commit()
    return c

def propose_sale_from_purchase(purchase_code:str):
    row = MastrinoLink.query.filter_by(purchase_code=purchase_code).first()
    return row.sale_code if row else None

def override_article_mapping(article_code:str, new_sale_code:str, new_purchase_code:str|None=None, reason:str|None=None):
    ov = MastrinoOverride(article_code=article_code, purchase_code=new_purchase_code, sale_code=new_sale_code, reason=reason or "manual override")
    db.session.add(ov); db.session.commit()
    return ov
