from flask import Blueprint, send_from_directory, current_app, abort
from ..models import Allegato
import os

files_bp = Blueprint("files", __name__)

@files_bp.route('/files/download/<int:allegato_id>')
def download_attachment(allegato_id: int):
    allegato = Allegato.query.get_or_404(allegato_id)
    
    # Costruisci il percorso assoluto in modo sicuro
    abs_path = os.path.join(current_app.root_path, allegato.path)
    
    if not os.path.exists(abs_path):
        abort(404, description="File non trovato sul server.")

    directory = os.path.dirname(abs_path)
    filename = os.path.basename(abs_path)
    
    return send_from_directory(directory, filename, as_attachment=True)

@files_bp.get("/files/export-document/<int:doc_id>.pdf")
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
