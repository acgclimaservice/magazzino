
import io, os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter

def build_document_pdf(document, lines, attachment_path:str|None=None) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, H-40, f"Documento {getattr(document,'type','')} n. {getattr(document,'number','')}")
    c.setFont("Helvetica", 10)
    c.drawString(40, H-60, f"Data: {getattr(document,'date','')}")

    partner = getattr(document, "partner", None)
    wh = getattr(document, "warehouse", None) or getattr(document, "dest_warehouse", None)
    if partner:
        c.drawString(40, H-80, f"Controparte: {getattr(partner,'code','')} - {getattr(partner,'name','')}")
    if wh:
        c.drawString(40, H-95, f"Magazzino: {getattr(wh,'code','')} - {getattr(wh,'name','')}")

    y = H - 120
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, y, "Codice"); c.drawString(130, y, "Descrizione")
    c.drawString(360, y, "Q.tà"); c.drawString(410, y, "Prezzo")
    c.drawString(470, y, "Mastrino"); c.line(40, y-2, 550, y-2); y -= 14
    c.setFont("Helvetica", 9)
    for ln in lines:
        if y < 50: c.showPage(); y = H - 50
        code = getattr(ln, "sku", getattr(ln, "article_code", ""))
        desc = getattr(ln, "description", ""); qty = getattr(ln, "qty", getattr(ln, "quantity", 0))
        price = getattr(ln, "unit_price", getattr(ln, "price", 0))
        mastr = getattr(ln, "mastrino", getattr(ln, "mastrino_code", ""))
        c.drawString(40, y, str(code)); c.drawString(130, y, str(desc)[:35])
        c.drawRightString(400, y, f"{qty}"); c.drawRightString(460, y, f"{price}")
        c.drawString(470, y, str(mastr)); y -= 12
    c.showPage(); c.save()

    base = PdfReader(io.BytesIO(buf.getvalue()))
    writer = PdfWriter()
    for p in base.pages: writer.add_page(p)
    if attachment_path and os.path.exists(attachment_path):
        try:
            att = PdfReader(attachment_path)
            for p in att.pages: writer.add_page(p)
        except Exception: pass
    out = io.BytesIO(); writer.write(out); return out.getvalue()
