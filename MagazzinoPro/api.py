
# api.py - Blueprint API per Magazzino Pro (compat con gemini_workstation)
# Come usare in app.py:
#   from api import api_bp, api_public_bp
#   app.register_blueprint(api_bp)          # /api/*
#   app.register_blueprint(api_public_bp)   # /status e alias /parse-ticket, /parse-materiali
#
# Requisiti: pip install requests pypdf

from __future__ import annotations

import os
import re
import io
import time
import json
import hashlib
from typing import Tuple, Optional, List, Dict

import requests
from flask import Blueprint, request, jsonify, current_app

# --- Blueprints ---
api_bp = Blueprint('api', __name__, url_prefix='/api')
api_public_bp = Blueprint('api_public', __name__)  # senza prefix, per compat frontend esistente


# -----------------------------
# Helpers
# -----------------------------

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = current_app.config.get(name) if current_app else None
    return val if val is not None else os.environ.get(name, default)


def _sha1_bytes(data: bytes) -> str:
    h = hashlib.sha1()
    h.update(data)
    return h.hexdigest()


def _extract_text_with_pypdf(pdf_bytes: bytes) -> Tuple[str, int]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return "", 0
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = len(reader.pages)
    out: List[str] = []
    for i in range(pages):
        try:
            out.append(reader.pages[i].extract_text() or "")
        except Exception:
            out.append("")
    return "\n".join(out), pages


def _norm_num(s: str) -> float:
    s = s.strip()
    s = s.replace('\u00A0', ' ').replace('€', '').replace('EUR', '').strip()
    s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except Exception:
        return 0.0


def _extract_ticket_fields(text: str) -> Dict[str, str]:
    def find_one(patterns, flags=re.IGNORECASE | re.MULTILINE):
        for p in patterns:
            m = re.search(p, text, flags)
            if m:
                return (m.group(1) or "").strip()
        return ""

    cliente = find_one([r"(?:^|\b)Cliente(?:\s*finale)?\s*[:\-]\s*(.+)",
                        r"(?:^|\b)Ragione\s*sociale\s*[:\-]\s*(.+)"])
    condominio = find_one([r"(?:^|\b)Condominio\s*[:\-]\s*(.+)",
                           r"(?:^|\b)Sito\s*[:\-]\s*(.+)",
                           r"(?:^|\b)Cantiere\s*[:\-]\s*(.+)"])
    indirizzo = find_one([r"(?:^|\b)Indirizzo\s*[:\-]\s*([^\n]+)",
                          r"(?:^|\b)Via\s*[:\-]\s*([^\n]+)"])
    data_intervento = find_one([r"(?:^|\b)Data\s*(?:intervento)?\s*[:\-]\s*([0-3]?\d/[01]?\d/\d{4})",
                                r"(?:^|\b)del\s*([0-3]?\d/[01]?\d/\d{4})"])
    tecnico = find_one([r"(?:^|\b)Tecnico\s*[:\-]\s*(.+)",
                        r"(?:^|\b)Operatore\s*[:\-]\s*(.+)"])
    descr = find_one([r"(?:^|\b)(?:Descrizione|Intervento|Note)\s*[:\-]\s*(.+)"])

    return {
        "cliente": cliente,
        "condominio": condominio,
        "indirizzo": indirizzo,
        "data_intervento": data_intervento,
        "tecnico_intervento": tecnico,
        "tecnico_anagrafica": tecnico,
        "intervento_effettuato": descr
    }


def _extract_materials(text: str) -> List[Dict[str, float]]:
    """Heuristica semplice: righe con formato 'Q.tà x Nome ..... Prezzo' o 'Nome .... Q.tà .... Prezzo'"""
    items: List[Dict[str, float]] = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # pattern 1: "2 x Rubinetto da 1/2  12,50"
    p1 = re.compile(r"^(\d+(?:[.,]\d+)?)\s*[x×]\s*(.+?)\s+(?:€|EUR)?\s*([0-9]+(?:[.,][0-9]{2})?)$", re.IGNORECASE)
    # pattern 2: "Rubinetto da 1/2    2    12,50"
    p2 = re.compile(r"^(.+?)\s{2,}(\d+(?:[.,]\d+)?)\s{1,}(?:€|EUR)?\s*([0-9]+(?:[.,][0-9]{2})?)$", re.IGNORECASE)
    # pattern 3: "Cod Desc Qta Prezzo" (tabellare).
    p3 = re.compile(r"^(.+?)\s+(\d+(?:[.,]\d+)?)\s+(?:€|EUR)?\s*([0-9]+(?:[.,][0-9]{2})?)$", re.IGNORECASE)

    for ln in lines:
        for p in (p1, p2, p3):
            m = p.match(ln)
            if m:
                qta = _norm_num(m.group(1 if p is p1 else 2))
                nome = m.group(2 if p is p1 else 1).strip()
                prezzo = _norm_num(m.group(3))
                if nome and qta > 0 and prezzo >= 0:
                    items.append({"nome": nome, "quantita": qta, "prezzoAcquisto": prezzo})
                break
        if len(items) >= 120:
            break
    return items


# -----------------------------
# API endpoints
# -----------------------------

@api_bp.get("/status")
def status():
    return jsonify({
        "ok": True,
        "service": "Magazzino Pro API",
        "time": time.time(),
        "env": {
            "GEMINI_MODEL": _env("GEMINI_MODEL", "gemini-2.0-flash") is not None,
            "GEMINI_API_KEY": bool(_env("GEMINI_API_KEY")),
        }
    })


@api_bp.post("/ai/gemini")
def ai_gemini():
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "Prompt mancante"}), 400

    key = _env("GEMINI_API_KEY")
    if not key:
        return jsonify({"error": "GEMINI_API_KEY non configurato"}), 500

    model = _env("GEMINI_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}

    try:
        r = requests.post(url, json=payload, timeout=45)
        if r.status_code != 200:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            return jsonify({"error": "Chiamata Gemini fallita", "detail": detail}), 502

        j = r.json()
        text = ""
        try:
            cands = j.get("candidates", [])
            for c in cands:
                parts = (((c or {}).get("content") or {}).get("parts") or [])
                for p in parts:
                    t = (p or {}).get("text", "")
                    if t:
                        text += t
            text = text.strip()
        except Exception:
            text = ""
        return jsonify({"text": text})
    except requests.Timeout:
        return jsonify({"error": "Timeout chiamata Gemini"}), 504
    except Exception as e:
        return jsonify({"error": f"Errore generico: {e.__class__.__name__}", "detail": str(e)}), 500


def _do_parse(doc_type: str):
    # accetta campi: 'pdf_file' (frontend), 'file', 'pdf'
    f = request.files.get("pdf_file") or request.files.get("file") or request.files.get("pdf")
    if not f or not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Allega un PDF (campo 'pdf_file', 'file' o 'pdf')."}), 400

    data = f.read()
    size_bytes = len(data)
    sha1 = _sha1_bytes(data)
    text, pages = _extract_text_with_pypdf(data)

    if doc_type == "ticket":
        extracted = _extract_ticket_fields(text) if text else {}
        return jsonify({
            "ok": True,
            "type": "ticket",
            "filename": f.filename,
            "sha1": sha1,
            "size_bytes": size_bytes,
            "pages": pages,
            "data": extracted,
            "notes": ("" if text else "Parsing non disponibile: installa 'pypdf' sul server.")
        })

    if doc_type == "materiali":
        items = _extract_materials(text) if text else []
        return jsonify({
            "ok": True,
            "type": "materiali",
            "filename": f.filename,
            "sha1": sha1,
            "size_bytes": size_bytes,
            "pages": pages,
            "data": items,
            "notes": ("" if text else "Parsing non disponibile: installa 'pypdf' sul server.")
        })

    # fallback "generic"
    preview = (text[:8000] + ("..." if len(text) > 8000 else "")) if text else ""
    return jsonify({
        "ok": True,
        "type": "generic",
        "filename": f.filename,
        "sha1": sha1,
        "size_bytes": size_bytes,
        "pages": pages,
        "text_preview": preview,
        "notes": ("" if text else "Parsing non disponibile: installa 'pypdf' sul server.")
    })


@api_bp.post("/parse-<string:doc_type>")
def parse_pdf(doc_type: str):
    allowed = {"ticket", "materiali", "rti", "rti-df", "mpls", "generic"}
    if doc_type not in allowed:
        doc_type = "generic"
    return _do_parse(doc_type)


# --- Alias pubblici per compat (frontend esistente) ---

@api_public_bp.get("/status")
def status_public():
    return status()


@api_public_bp.post("/parse-ticket")
def parse_ticket_public():
    return _do_parse("ticket")


@api_public_bp.post("/parse-materiali")
def parse_materiali_public():
    return _do_parse("materiali")
