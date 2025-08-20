# app/services/file_service.py
import os
import io
import tempfile
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, List
from werkzeug.utils import secure_filename
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from flask import current_app

def ensure_upload_dir(category: str = "uploads") -> Path:
    """Crea e restituisce la directory di upload"""
    upload_base = Path(current_app.config.get('UPLOAD_FOLDER', 'instance/uploads'))
    upload_dir = upload_base / category / datetime.now().strftime('%Y/%m')
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir

def save_upload(file_storage, category: str = "uploads") -> Tuple[str, str]:
    """
    Salva file uploadato in modo sicuro.
    Returns: (relative_path, absolute_path)
    """
    if not file_storage:
        raise ValueError("Nessun file fornito")
    
    # Genera nome sicuro
    original_name = secure_filename(file_storage.filename or "unnamed")
    name_parts = original_name.rsplit('.', 1)
    base_name = name_parts[0] if name_parts else "file"
    extension = name_parts[1].lower() if len(name_parts) > 1 else "bin"
    
    # Aggiungi timestamp per unicità
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_name = f"{base_name}_{timestamp}.{extension}"
    
    # Salva file
    upload_dir = ensure_upload_dir(category)
    abs_path = upload_dir / unique_name
    file_storage.save(str(abs_path))
    
    # Path relativo dall'instance folder
    rel_path = str(abs_path.relative_to(Path(current_app.config.get('UPLOAD_FOLDER', 'instance/uploads')).parent))
    return rel_path, str(abs_path)

def move_upload_to_document(rel_path: str, doc_id: int) -> Tuple[str, str]:
    """
    Sposta un file uploadato nella cartella del documento.
    Returns: (new_relative_path, new_absolute_path)
    """
    old_abs = abs_path_from_rel(rel_path)
    if not os.path.exists(old_abs):
        raise FileNotFoundError(f"File non trovato: {rel_path}")
    
    # Crea directory documento
    doc_dir = ensure_upload_dir(f"documents/{doc_id}")
    filename = os.path.basename(old_abs)
    new_abs = doc_dir / filename
    
    # Sposta file
    os.rename(old_abs, str(new_abs))
    
    # Nuovo path relativo
    new_rel = str(new_abs.relative_to(Path(current_app.config.get('UPLOAD_FOLDER', 'instance/uploads')).parent))
    return new_rel, str(new_abs)

def abs_path_from_rel(rel_path: str) -> str:
    """Converte path relativo in assoluto"""
    if not rel_path:
        raise ValueError("Path vuoto")
    
    # Rimuovi leading slash se presente
    rel_path = rel_path.lstrip('/')
    
    # Base path dall'instance folder
    base_path = Path(current_app.instance_path)
    abs_path = base_path / rel_path
    
    # Verifica che il path sia dentro l'instance folder (sicurezza)
    try:
        abs_path.resolve().relative_to(base_path.resolve())
    except ValueError:
        raise ValueError(f"Path non sicuro: {rel_path}")
    
    return str(abs_path)

def generate_document_pdf(doc, output_path: str):
    """Genera PDF del documento DDT"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Header
    c.setFont("Helvetica-Bold", 16)
    doc_title = f"Documento {doc.tipo}"
    if doc.numero and doc.anno:
        doc_title += f" n. {doc.numero}/{doc.anno}"
    c.drawString(50, height - 50, doc_title)
    
    # Info documento
    c.setFont("Helvetica", 10)
    y = height - 80
    
    if doc.data:
        c.drawString(50, y, f"Data: {doc.data.strftime('%d/%m/%Y')}")
        y -= 20
    
    if doc.partner:
        partner_text = f"{'Fornitore' if doc.tipo == 'DDT_IN' else 'Cliente'}: {doc.partner.nome}"
        c.drawString(50, y, partner_text)
        y -= 20
    
    if doc.magazzino:
        c.drawString(50, y, f"Magazzino: {doc.magazzino.codice} - {doc.magazzino.nome}")
        y -= 20
    
    # Stato
    c.drawString(50, y, f"Stato: {doc.status}")
    y -= 30
    
    # Tabella righe
    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, y, "Codice")
    c.drawString(150, y, "Descrizione")
    c.drawString(350, y, "Q.tà")
    c.drawString(400, y, "UM")
    c.drawString(450, y, "Prezzo")
    c.drawString(500, y, "Totale")
    
    c.line(50, y - 2, 550, y - 2)
    y -= 15
    
    c.setFont("Helvetica", 9)
    totale_doc = 0
    
    for riga in doc.righe.all():
        if y < 100:  # Nuova pagina se necessario
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 9)
        
        # Codice articolo
        codice = ""
        if riga.articolo:
            codice = riga.articolo.codice_interno or riga.articolo.codice_fornitore or ""
        c.drawString(50, y, codice[:20])
        
        # Descrizione
        desc = (riga.descrizione or "")[:40]
        c.drawString(150, y, desc)
        
        # Quantità
        qty = float(riga.quantita or 0)
        c.drawRightString(380, y, f"{qty:.3f}")
        
        # UM (estrai da descrizione o default)
        um = "PZ"
        if "[" in desc and "]" in desc:
            try:
                um = desc[desc.index("[")+1:desc.index("]")]
            except:
                pass
        c.drawString(400, y, um)
        
        # Prezzo
        prezzo = float(riga.prezzo or 0)
        c.drawRightString(480, y, f"€ {prezzo:.2f}")
        
        # Totale riga
        totale_riga = qty * prezzo
        totale_doc += totale_riga
        c.drawRightString(550, y, f"€ {totale_riga:.2f}")
        
        y -= 15
    
    # Totale documento
    c.line(450, y, 550, y)
    y -= 15
    c.setFont("Helvetica-Bold", 10)
    c.drawString(450, y, "TOTALE:")
    c.drawRightString(550, y, f"€ {totale_doc:.2f}")
    
    # Footer
    c.setFont("Helvetica", 8)
    c.drawString(50, 30, f"Documento generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    c.save()
    
    # Salva su file
    pdf_content = buffer.getvalue()
    with open(output_path, 'wb') as f:
        f.write(pdf_content)
    
    return output_path

def merge_pdfs(base_pdf_path: str, attachment_paths: List[str], output_path: str):
    """Unisce PDF multipli in un unico file"""
    writer = PdfWriter()
    
    # Aggiungi pagine dal PDF base
    if os.path.exists(base_pdf_path):
        with open(base_pdf_path, 'rb') as base_file:
            reader = PdfReader(base_file)
            for page in reader.pages:
                writer.add_page(page)
    
    # Aggiungi pagine dagli allegati
    for att_path in attachment_paths:
        if os.path.exists(att_path) and att_path.lower().endswith('.pdf'):
            try:
                with open(att_path, 'rb') as att_file:
                    reader = PdfReader(att_file)
                    for page in reader.pages:
                        writer.add_page(page)
            except Exception as e:
                current_app.logger.warning(f"Impossibile aggiungere PDF {att_path}: {e}")
                continue
    
    # Scrivi file finale
    with open(output_path, 'wb') as output_file:
        writer.write(output_file)
    
    return output_path

def cleanup_temp_files(*file_paths):
    """Rimuove file temporanei"""
    for path in file_paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            current_app.logger.warning(f"Impossibile rimuovere {path}: {e}")

def get_file_hash(file_path: str) -> str:
    """Calcola hash SHA256 di un file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def validate_pdf(file_path: str) -> bool:
    """Valida che un file sia un PDF valido"""
    try:
        with open(file_path, 'rb') as f:
            PdfReader(f)
        return True
    except Exception:
        return False
