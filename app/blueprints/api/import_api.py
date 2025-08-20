# app/blueprints/api/import_api.py
"""
API Blueprint dedicato esclusivamente alle operazioni di import.
Responsabilità singola: endpoint API per import DDT.
"""
from flask import Blueprint, request, jsonify, current_app
from ...services.import_service import ImportService
from ...extensions import db

import_api_bp = Blueprint("import_api", __name__, url_prefix="/api/import")

# Inizializza servizio
import_service = ImportService()


@import_api_bp.route("/ddt/parse", methods=["POST"])
def parse_ddt():
    """
    Parsing DDT da PDF caricato.
    Returns: {"ok": bool, "data": dict, "method": str, "note": str, "uploaded_file": str}
    """
    try:
        file = request.files.get("pdf_file")
        if not file:
            return jsonify({"ok": False, "error": "Nessun file ricevuto"}), 400
        
        result = import_service.parse_ddt_from_upload(file)
        
        if result["ok"]:
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        current_app.logger.exception("Errore in parse_ddt")
        return jsonify({"ok": False, "error": str(e)}), 500


@import_api_bp.route("/ddt/preview", methods=["POST"])
def ddt_preview():
    """
    Crea preview per DDT da importare.
    Body: {"data": dict, "uploaded_file": str}
    Returns: {"ok": bool, "preview": dict}
    """
    try:
        payload = request.get_json()
        if not payload or not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "Nessun dato ricevuto"}), 400
        
        result = import_service.create_preview(
            parsed_data=payload,
            uploaded_file=payload.get("uploaded_file")
        )
        
        if result["ok"]:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        current_app.logger.exception("Errore in ddt_preview")
        return jsonify({"ok": False, "error": str(e)}), 500


@import_api_bp.route("/ddt/confirm", methods=["POST"])
def ddt_confirm():
    """
    Conferma import DDT IN.
    Body: {"fornitore": str, "righe": list, "uploaded_file": str, "magazzino_id": int, "commessa_id": int}
    Returns: {"ok": bool, "document_id": int, "redirect_url": str}
    """
    try:
        payload = request.get_json(force=True)
        
        # Validazione input
        fornitore_nome = payload.get("fornitore")
        righe = payload.get("righe") or []
        
        if not fornitore_nome or not righe:
            return jsonify({
                "ok": False, 
                "error": "Dati insufficienti (fornitore, righe)"
            }), 400
        
        # Import
        result = import_service.import_ddt_in(
            fornitore_nome=fornitore_nome,
            righe=righe,
            uploaded_file=payload.get("uploaded_file"),
            magazzino_id=payload.get("magazzino_id"),
            commessa_id=payload.get("commessa_id")
        )
        
        if result["ok"]:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        current_app.logger.exception("Errore in ddt_confirm")
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500


# Error handlers specifici per questo blueprint
@import_api_bp.errorhandler(413)
def file_too_large(error):
    return jsonify({
        "ok": False,
        "error": "File troppo grande. Massimo 32MB."
    }), 413


@import_api_bp.errorhandler(415)
def unsupported_media_type(error):
    return jsonify({
        "ok": False,
        "error": "Tipo file non supportato. Solo PDF."
    }), 415


# Health check per questo modulo
@import_api_bp.route("/health", methods=["GET"])
def health():
    """Health check del modulo import"""
    try:
        # Test connessione DB
        from ...models import Mastrino
        count = Mastrino.query.count()
        
        return jsonify({
            "ok": True,
            "module": "import_api",
            "status": "healthy",
            "mastrini_count": count
        })
        
    except Exception as e:
        return jsonify({
            "ok": False,
            "module": "import_api", 
            "status": "unhealthy",
            "error": str(e)
        }), 500