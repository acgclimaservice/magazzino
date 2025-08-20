from flask import Blueprint, send_from_directory, current_app, abort
from ..models import Allegato
import os

files_bp = Blueprint("files", __name__)

@files_bp.route('/download/<int:allegato_id>')  # ✅ CORRETTO: rimosso /files/
def download_attachment(allegato_id: int):
    allegato = Allegato.query.get_or_404(allegato_id)
    
    # Costruisci il percorso assoluto in modo sicuro
    abs_path = os.path.join(current_app.root_path, allegato.path)
    
    if not os.path.exists(abs_path):
        current_app.logger.error(f"File non trovato: {abs_path}")
        abort(404, description="File non trovato sul server.")
        
    directory = os.path.dirname(abs_path)
    filename = os.path.basename(abs_path)
    
    return send_from_directory(directory, filename, as_attachment=True)

@files_bp.get("/export-document/<int:doc_id>.pdf")  # ✅ CORRETTO: rimosso /files/
def export_document(doc_id: int):
    from ..models import Documento
    from ..services.pdf_export import export_document_pdf
    from flask import make_response
    
    doc = Documento.query.get_or_404(doc_id)
    pdf_bytes = export_document_pdf(doc)
    
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=doc_{doc.id}.pdf'
    return response

# Route aggiuntiva per vedere il PDF nel browser invece di scaricarlo
@files_bp.route('/view/<int:allegato_id>')
def view_attachment(allegato_id: int):
    allegato = Allegato.query.get_or_404(allegato_id)
    
    abs_path = os.path.join(current_app.root_path, allegato.path)
    
    if not os.path.exists(abs_path):
        current_app.logger.error(f"File non trovato: {abs_path}")
        abort(404, description="File non trovato sul server.")
        
    directory = os.path.dirname(abs_path)
    filename = os.path.basename(abs_path)
    
    # Per PDF, mostra nel browser invece di scaricare
    as_attachment = not (allegato.mime and 'pdf' in allegato.mime.lower())
    
    return send_from_directory(directory, filename, as_attachment=as_attachment)
