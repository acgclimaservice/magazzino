
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.services.mastrini import load_mapping_from_dataframe

bp = Blueprint("settings_mastrini", __name__, url_prefix="/settings/mastrini")

@bp.get("/link")
def link_form(): 
    return render_template("settings_mastrini_link.html")

@bp.post("/link")
def link_upload():
    f = request.files.get("file")
    if not f:
        flash("Carica il file Excel con il mapping.", "warning")
        return redirect(url_for("settings_mastrini.link_form"))
    try:
        df = pd.read_excel(f, engine="openpyxl")
    except Exception:
        f.stream.seek(0); df = pd.read_csv(f)
    cnt = load_mapping_from_dataframe(df)
    flash(f"Caricate {cnt} righe di linking mastrini.", "success")
    return redirect(url_for("settings_mastrini.link_form"))
