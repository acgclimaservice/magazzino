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
@compatibility_bp.route('/api/parse-ddt', methods=['POST'])
def legacy_api_parse_ddt():
    """Redirect da /api/parse-ddt a /api/import/ddt/parse"""
    return redirect(url_for('import_api.parse_ddt'), code=307)  # 307 mantiene POST


@compatibility_bp.route('/api/import-ddt-preview', methods=['POST'])
def legacy_api_import_preview():
    """Redirect da /api/import-ddt-preview a /api/import/ddt/preview"""
    return redirect(url_for('import_api.ddt_preview'), code=307)


@compatibility_bp.route('/api/import-ddt-confirm', methods=['POST'])
def legacy_api_import_confirm():
    """Redirect da /api/import-ddt-confirm a /api/import/ddt/confirm"""
    return redirect(url_for('import_api.ddt_confirm'), code=307)


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