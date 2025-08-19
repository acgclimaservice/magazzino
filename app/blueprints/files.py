from flask import Blueprint, send_file, abort
import os, tempfile
from ..models import Documento, Allegato
from ..services.file_service import generate_document_pdf, merge_pdfs, abs_path_from_rel

files_bp = Blueprint("files", __name__)

@files_bp.route("/files/export-document/<int:id>.pdf")
def export_document_pdf(id):
    """
    Genera un PDF del documento e lo unisce con eventuali allegati PDF.
    Questa funzione ora gestisce l'esportazione completa.
    """
    doc = Documento.query.get_or_404(id)
    tmpdir = tempfile.gettempdir()
    base_pdf = os.path.join(tmpdir, f"doc_{doc.id}_base.pdf")
    out_pdf = os.path.join(tmpdir, f"doc_{doc.id}_export.pdf")
    generate_document_pdf(doc, base_pdf)

    # Raccoglie gli allegati in formato PDF
    att_paths = []
    for a in (doc.allegati or []):
        abs_p = abs_path_from_rel(a.path)
        if os.path.exists(abs_p) and abs_p.lower().endswith(".pdf"):
            att_paths.append(abs_p)

    merge_pdfs(base_pdf, att_paths, out_pdf)
    filename = f"{doc.tipo}_{doc.anno}_{doc.numero:04d}.pdf"
    return send_file(out_pdf, as_attachment=True, download_name=filename, mimetype="application/pdf")

@files_bp.route("/files/export-document-base/<int:id>.pdf")
def export_document_base_pdf(id):
    """
    NUOVA FUNZIONE: Esporta solo il PDF base del documento, senza unire gli allegati.
    """
    doc = Documento.query.get_or_404(id)
    tmpdir = tempfile.gettempdir()
    base_pdf = os.path.join(tmpdir, f"doc_{doc.id}_base_only.pdf")
    generate_document_pdf(doc, base_pdf)
    filename = f"{doc.tipo}_{doc.anno}_{doc.numero:04d}_base.pdf"
    return send_file(base_pdf, as_attachment=True, download_name=filename, mimetype="application/pdf")


@files_bp.route("/files/attachment/<int:allegato_id>/download")
def download_attachment(allegato_id):
    att = Allegato.query.get_or_404(allegato_id)
    abs_p = abs_path_from_rel(att.path)
    if not os.path.exists(abs_p):
        abort(404)
    return send_file(abs_p, as_attachment=True, download_name=att.filename, mimetype=att.mime or "application/octet-stream")
