import os
import shutil
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

def _uploads_root():
    root = current_app.config.get('UPLOAD_FOLDER')
    if not root:
        # Default: project_root/uploads
        project_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
        root = os.path.join(project_root, "uploads")
    os.makedirs(root, exist_ok=True)
    return root

def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def save_upload(file_storage, category="incoming"):
    """Salva un FileStorage in uploads/<category>/<YYYYMM>/filename e restituisce path relativo e assoluto."""
    root = _uploads_root()
    yyyymm = datetime.now().strftime("%Y%m")
    subdir = os.path.join(root, category, yyyymm)
    _ensure_dir(subdir)
    base = secure_filename(file_storage.filename or f"file_{datetime.now().timestamp():.0f}.bin")
    name = base or "file.bin"
    abs_path = os.path.join(subdir, name)

    # evita collisioni
    i = 1
    name_noext, ext = os.path.splitext(name)
    while os.path.exists(abs_path):
        name = f"{name_noext}_{i}{ext}"
        abs_path = os.path.join(subdir, name)
        i += 1

    file_storage.stream.seek(0)
    file_storage.save(abs_path)
    rel_path = os.path.relpath(abs_path, root).replace("\\", "/")
    return rel_path, abs_path

def move_upload_to_document(rel_path, documento_id):
    """Sposta un file da uploads/<...> a uploads/documents/<doc_id>/ e ritorna nuovo rel_path."""
    root = _uploads_root()
    src = os.path.join(root, rel_path)
    if not os.path.exists(src):
        raise FileNotFoundError(f"Sorgente non trovata: {src}")
    dest_dir = os.path.join(root, "documents", str(documento_id))
    _ensure_dir(dest_dir)
    dest = os.path.join(dest_dir, os.path.basename(src))
    # gestisci collisione
    i = 1
    dest_base, dest_ext = os.path.splitext(dest)
    while os.path.exists(dest):
        dest = f"{dest_base}_{i}{dest_ext}"
        i += 1
    shutil.move(src, dest)
    new_rel = os.path.relpath(dest, root).replace("\\", "/")
    return new_rel, dest

def abs_path_from_rel(rel_path):
    root = _uploads_root()
    return os.path.join(root, rel_path)

# --- PDF utilities ---

def generate_document_pdf(doc, out_path):
    """Crea un PDF 'semplice' per il documento (testata + righe)."""
    c = canvas.Canvas(out_path, pagesize=A4)
    width, height = A4
    x_margin = 20 * mm
    y = height - 30 * mm

    c.setFont("Helvetica-Bold", 14)
    c.drawString(x_margin, y, f"{doc.tipo} n. {doc.numero}/{doc.anno}")
    y -= 8 * mm

    c.setFont("Helvetica", 10)
    c.drawString(x_margin, y, f"Data: {doc.data.strftime('%d/%m/%Y')}")
    y -= 6 * mm
    c.drawString(x_margin, y, f"Partner: {doc.partner.nome}")
    y -= 6 * mm
    c.drawString(x_margin, y, f"Magazzino: {doc.magazzino.codice} - {doc.magazzino.nome}")
    y -= 6 * mm
    # Commessa solo per DDT IN
    try:
        if getattr(doc, "tipo", "") == "DDT_IN" and getattr(doc, "commessa", None):
            c.drawString(x_margin, y, f"Commessa: {doc.commessa.nome}")
            y -= 4 * mm
    except Exception:
        pass
    y -= 4 * mm

    # Header righe
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x_margin, y, "Descrizione")
    c.drawRightString(width - x_margin - 70, y, "Q.tà")
    c.drawRightString(width - x_margin - 30, y, "Prezzo")
    y -= 5 * mm
    c.line(x_margin, y, width - x_margin, y)
    y -= 5 * mm
    c.setFont("Helvetica", 9)

    total = 0.0
    for r in doc.righe.order_by().all():
        if y < 30 * mm:
            c.showPage()
            y = height - 30 * mm
        c.drawString(x_margin, y, (r.descrizione or "")[:80])
        c.drawRightString(width - x_margin - 70, y, f"{float(r.quantita):.3f}")
        c.drawRightString(width - x_margin - 30, y, f"{float(r.prezzo):.2f}")
        total += float(r.quantita) * float(r.prezzo)
        y -= 6 * mm

    y -= 6 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - x_margin, y, f"Totale: {total:.2f}")
    c.showPage()
    c.save()
    return out_path

def merge_pdfs(base_pdf_path, attachment_paths, out_path):
    """Unisce base_pdf alle pagine PDF degli allegati. Solo allegati PDF sono incorporati come pagine."""
    writer = PdfWriter()

    def _append_pdf(path):
        try:
            reader = PdfReader(path)
            for p in reader.pages:
                writer.add_page(p)
        except Exception as e:
            # ignora allegati non pdf o corrotti
            pass

    _append_pdf(base_pdf_path)
    for ap in attachment_paths:
        if ap.lower().endswith(".pdf"):
            _append_pdf(ap)

    with open(out_path, "wb") as f:
        writer.write(f)
    return out_path
