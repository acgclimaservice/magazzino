from flask import Blueprint, request, redirect, url_for

redirects_bp = Blueprint("redirects", __name__)

@redirects_bp.before_app_request
def _redirect_legacy_new_ddt_out():
    p = (request.path or "").lower().rstrip("/")
    if p.startswith("/documents/new/"):
        tail = p.split("/documents/new/", 1)[1]
        if tail in ("ddt_out", "ddt-out", "ddtout"):
            return redirect(url_for("documents.new_out_form"), code=303)
    elif p == "/ddt-out/new":
        return redirect(url_for("documents.new_out_form"), code=303)
    return None
