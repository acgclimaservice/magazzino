from flask import Blueprint, request, redirect, url_for

redirects_bp = Blueprint("redirects", __name__)

@redirects_bp.before_app_request
def _redirect_legacy_new_ddt_out():
    """
    Intercetta la rotta legacy /documents/new/DDT_OUT (e varianti) e
    reindirizza alla nuova maschera /ddt-out/new PRIMA del routing.
    """
    p = (request.path or "").lower().rstrip("/")
    if p.startswith("/documents/new/"):
        tail = p.split("/documents/new/", 1)[1]
        # Normalizza possibili varianti
        if tail in ("ddt_out", "ddt-out", "ddtout"):
            return redirect(url_for("importing.ddt_out_new"), code=303)
    # Nessun redirect per altre rotte
    return None
