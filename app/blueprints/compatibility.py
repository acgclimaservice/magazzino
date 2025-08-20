from flask import redirect, url_for, request
# app/blueprints/compatibility.py
"""
Blueprint per gestire redirect di compatibilità durante il refactoring.
Responsabilità singola: mantenere URL legacy funzionanti.
"""
from flask import Blueprint, redirect, url_for, request

compatibility_bp = Blueprint("compatibility", __name__)


# === IMPORT MODULE REDIRECTS ===

@compatibility_bp.route('/import-pdf')
def legacy_import_pdf():
    """Redirect da /import-pdf a /import/ddt"""
    return redirect(url_for('import_web.ddt'), code=301)


@compatibility_bp.route('/workstation')  
def legacy_workstation():
    """Redirect da /workstation a /import/workstation"""
    return redirect(url_for('import_web.workstation'), code=301)


# Legacy API redirects
@compatibility_bp.route("/api/parse-ddt", methods=["GET", "POST"])
def legacy_api_parse_ddt():
    """Redirect da /api/parse-ddt a /api/import/ddt/parse"""
    return redirect(url_for('importing.api_parse_ddt'), code=307)  # 307 mantiene POST


@compatibility_bp.route('/api/import-ddt-preview', methods=['POST'])
def legacy_api_import_preview():
    """Redirect da /api/import-ddt-preview a /api/import/ddt/preview"""
    return redirect(url_for('importing.import_ddt_preview'), code=307)


@compatibility_bp.route('/api/import-ddt-confirm', methods=['POST'])
def legacy_api_import_confirm():
    """Redirect da /api/import-ddt-confirm a /api/import/ddt/confirm"""
    return redirect(url_for('importing.import_ddt_confirm'), code=307)


# === FUTURE MODULE REDIRECTS (preparati per prossimi refactoring) ===

# @compatibility_bp.route('/documents/<int:id>')
# def legacy_document_detail(id):
#     """Redirect futuro per documents"""
#     return redirect(url_for('documents_web.detail', id=id), code=301)


# === HELPER PER LOGGING REDIRECT ===

@compatibility_bp.before_request
def log_legacy_access():
    """Log accessi alle URL legacy per monitoraggio"""
    from flask import current_app
    
    if current_app.config.get('DEBUG'):
        current_app.logger.info(f"🔄 Legacy redirect: {request.method} {request.path}")


# === CONTEXT PROCESSOR ===

@compatibility_bp.context_processor
def inject_migration_status():
    """Inietta info su stato migrazione per template"""
    return {
        'migration_active': True,
        'legacy_mode': False
    }
# Redirect API lookups per compatibilità
@compatibility_bp.route('/api/magazzini')
def api_magazzini_redirect():
    """Redirect /api/magazzini → /lookups/api/magazzini"""
    return redirect(url_for('lookups.api_magazzini'))

@compatibility_bp.route('/api/mastrini')
def api_mastrini_redirect():
    """Redirect /api/mastrini → /lookups/api/mastrini"""
    # Mantieni i query parameters (tipo=RICAVO)
    args = '?' + request.query_string.decode() if request.query_string else ''
    return redirect(url_for('lookups.api_mastrini') + args)

@compatibility_bp.route('/api/clienti')
def api_clienti_redirect():
    return redirect(url_for('lookups.api_clienti'))

@compatibility_bp.route('/api/documents/<int:id>/json')
def api_document_json_redirect(id):
    return redirect(url_for('docops.api_document_json', id=id))

@compatibility_bp.route('/api/documents/<int:id>/delete-draft', methods=['POST'])
def api_delete_draft_redirect(id):
    return redirect(url_for('docops.api_delete_draft', id=id), code=307)

@compatibility_bp.route('/api/documents/<int:id>/confirm', methods=['POST'])
def api_confirm_document_redirect(id):
    return redirect(url_for('docops.api_confirm_document', id=id), code=307)

@compatibility_bp.route('/api/inventory/search')
def api_inventory_search_redirect():
    args = '?' + request.query_string.decode() if request.query_string else ''
    return redirect(url_for('importing.api_inventory_search') + args)

@compatibility_bp.route('/api/documents/<int:id>/add-line', methods=['POST'])
def api_add_line_redirect(id):
    return redirect(url_for('docops.api_add_line', id=id), code=307)
