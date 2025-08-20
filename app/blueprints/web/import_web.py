# app/blueprints/web/import_web.py
"""
Web Blueprint dedicato alle pagine di import.
Responsabilità singola: rendering pagine web per import.
"""
from flask import Blueprint, render_template, redirect, url_for

import_web_bp = Blueprint("import_web", __name__, url_prefix="/import")


@import_web_bp.route("/")
def index():
    """Pagina principale import - redirect a DDT"""
    return redirect(url_for('import_web.ddt'))


@import_web_bp.route("/ddt")
def ddt():
    """Pagina import DDT da PDF"""
    return render_template('import/ddt.html', 
                         page_title="Importa DDT Fornitore")


@import_web_bp.route("/workstation")
def workstation():
    """Workstation - pagina moduli operativi"""
    return render_template('import/workstation.html',
                         page_title="Workstation")


# ===== ROUTES LEGACY (per compatibilità) =====

@import_web_bp.route("/pdf")  # era /import-pdf
def import_pdf():
    """Redirect compatibilità"""
    return redirect(url_for('import_web.ddt'))


# ===== CONTEXT PROCESSORS =====

@import_web_bp.context_processor
def inject_import_context():
    """Variabili comuni per template import"""
    return {
        'import_max_file_size': '32MB',
        'supported_formats': ['PDF'],
        'default_timeout': 60
    }


# ===== ERROR HANDLERS =====

@import_web_bp.errorhandler(404)
def import_not_found(error):
    """404 specifico per sezione import"""
    return render_template('import/404.html', 
                         section="Import"), 404


@import_web_bp.errorhandler(500)
def import_server_error(error):
    """500 specifico per sezione import"""
    return render_template('import/500.html',
                         section="Import"), 500