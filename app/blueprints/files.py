from flask import Blueprint, send_file, abort, current_app
import os, tempfile
from datetime import datetime
from ..models import Documento, Allegato, RigaDocumento
try:
    # Prefer service helpers if available
    from ..services.file_service import abs_path_from_rel as _abs_path_from_rel
except Exception:
    _abs_path_from_rel = None

files_bp = Blueprint("files", __name__)

# ---------- Helpers ----------

def _uploads_root():
    root = current_app.config.get('UPLOAD_FOLDER')
    if not root:
        project_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
        root = os.path.join(project_root, "uploads")
    os.makedirs(root, exist_ok=True)
    return root

def abs_path_from_rel(rel_path: str) -> str:
    if _abs_path_from_rel:
        try:
            return _abs_path_from_rel(rel_path)
        except Exception:
            pass
    if not rel_path:
        return ""
    root = _uploads_root()
    return os.path.abspath(os.path.join(root, rel_path.strip("/\\")))

def _is_pdf(att: Allegato) -> bool:
    try:
        if att is None: return False
        if att.mime and "pdf" in (att.mime or "").lower(): return True
        p = (att.path or "").lower()
        f = (att.filename or "").lower()
        return p.endswith(".pdf") or f.endswith(".pdf")
    except Exception:
        return False

def _iter_allegati(doc: Documento):
    # Ordina per created_at crescente (il primo è verosimilmente il DDT importato)
    return sorted(list(doc.allegati or []), key=lambda a: a.created_at or datetime.min)

# PDF generation (ReportLab) + merge (pypdf)
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from pypdf import PdfReader, PdfWriter

def generate_document_pdf(doc: Documento, out_path: str):
    c = canvas.Canvas(out_path, pagesize=A4)
    width, height = A4
    x = 15 * mm
    y = height - 20 * mm

    # Header
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y, f"Documento {doc.tipo} n. {doc.numero:04d} / {doc.anno}")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.drawString(x, y, f"Data: {doc.data.strftime('%d/%m/%Y') if doc.data else ''}")
    y -= 6 * mm
    partner = getattr(doc.partner, 'nome', '') or getattr(doc, 'partner_nome', '') or ''
    c.drawString(x, y, f"Controparte: {partner}")
    y -= 6 * mm
    mag = doc.magazzino
    c.drawString(x, y, f"Magazzino: {getattr(mag, 'codice', '')} {getattr(mag, 'nome', '')}")
    y -= 10 * mm

    # Table header
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, "Descrizione")
    c.drawRightString(width - x - 70, y, "Q.tà")
    c.drawRightString(width - x - 30, y, "Prezzo")
    y -= 4 * mm
    c.line(x, y, width - x, y)
    y -= 6 * mm
    c.setFont("Helvetica", 9)

    # Rows
    total = 0.0
    try:
        rows = doc.righe.order_by(RigaDocumento.id).all()
    except Exception:
        rows = list(getattr(doc, "righe", []) or [])
        rows.sort(key=lambda r: getattr(r, "id", 0) or 0)

    for r in rows:
        if y < 30 * mm:
            c.showPage()
            y = height - 30 * mm
        descr = (r.descrizione or "")[:85]
        c.drawString(x, y, descr)
        try:
            q = float(getattr(r, 'quantita', 0) or 0)
        except Exception:
            q = 0.0
        try:
            p = float(getattr(r, 'prezzo', 0) or 0)
        except Exception:
            p = 0.0
        c.drawRightString(width - x - 70, y, f"{q:.3f}")
        c.drawRightString(width - x - 30, y, f"{p:.2f}")
        total += q * p
        y -= 6 * mm

    # Footer
    if y < 40 * mm:
        c.showPage()
        y = height - 30 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - x, y, f"Totale: {total:.2f} €")
    y -= 8 * mm
    c.setFont("Helvetica", 8)
    c.drawString(x, y, f"Stato: {doc.status}")
    c.save()
    return out_path

def merge_pdfs(base_pdf_path: str, attachment_paths: list[str], out_path: str):
    writer = PdfWriter()
    def _append(pdf_path: str):
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                writer.add_page(page)
        except Exception:
            pass

    _append(base_pdf_path)
    for ap in attachment_paths or []:
        if ap and ap.lower().endswith('.pdf') and os.path.exists(ap):
            _append(ap)
    with open(out_path, 'wb') as f:
        writer.write(f)
    return out_path

# ---------- Routes ----------

@files_bp.get("/files/export-document-base/<int:id>.pdf")
def export_document_base(id: int):
    doc = Documento.query.get_or_404(id)
    tmpdir = tempfile.gettempdir()
    base_pdf = os.path.join(tmpdir, f"doc_{doc.id}_base.pdf")
    generate_document_pdf(doc, base_pdf)
    filename = f"{doc.tipo}_{doc.anno}_{doc.numero:04d}_base.pdf"
    return send_file(base_pdf, as_attachment=True, download_name=filename, mimetype="application/pdf")

@files_bp.get("/files/export-document-with-imported/<int:id>.pdf")
def export_document_with_imported(id: int):
    doc = Documento.query.get_or_404(id)
    tmpdir = tempfile.gettempdir()
    base_pdf = os.path.join(tmpdir, f"doc_{doc.id}_base.pdf")
    out_pdf = os.path.join(tmpdir, f"doc_{doc.id}_with_imported.pdf")

    generate_document_pdf(doc, base_pdf)

    # Valido solo per DDT_IN confermato; in altri casi restituisco il base
    if not (doc.tipo == 'DDT_IN' and (doc.status or '').lower() == 'confermato'):
        filename = f"{doc.tipo}_{doc.anno}_{doc.numero:04d}_base.pdf"
        return send_file(base_pdf, as_attachment=True, download_name=filename, mimetype="application/pdf")

    allegati = _iter_allegati(doc)
    imported = next((a for a in allegati if (a.filename or '').upper().startswith('IMPORTATO_') and _is_pdf(a)), None)
    if not imported:
        imported = next((a for a in allegati if _is_pdf(a)), None)

    if imported:
        abs_p = abs_path_from_rel(imported.path)
        if abs_p and os.path.exists(abs_p) and abs_p.lower().endswith('.pdf'):
            merge_pdfs(base_pdf, [abs_p], out_pdf)
            filename = f"{doc.tipo}_{doc.anno}_{doc.numero:04d}_con_importato.pdf"
            return send_file(out_pdf, as_attachment=True, download_name=filename, mimetype="application/pdf")

    # Fallback: solo documento
    filename = f"{doc.tipo}_{doc.anno}_{doc.numero:04d}_base.pdf"
    return send_file(base_pdf, as_attachment=True, download_name=filename, mimetype="application/pdf")
