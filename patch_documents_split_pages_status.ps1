# Crea/aggiorna:
# - app/blueprints/documents.py
# - app/templates/documents_in.html
# - app/templates/documents_out.html

$root  = Split-Path -Parent $MyInvocation.MyCommand.Path
$bpDir = Join-Path $root "app\blueprints"
$tplDir= Join-Path $root "app\templates"
New-Item -Force -ItemType Directory $bpDir  | Out-Null
New-Item -Force -ItemType Directory $tplDir | Out-Null

# ---------- app/blueprints/documents.py ----------
$documents_py = @'
from flask import Blueprint, render_template, request, redirect, url_for
from sqlalchemy import desc, or_
from datetime import datetime

from ..extensions import db
from ..models import Documento

documents_bp = Blueprint("documents", __name__)

DOCUMENTS_PER_PAGE = 25

def _parse_date_any(s):
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def _apply_filters(base_query, *, q_text=None, d_from=None, d_to=None, status=None):
    q = base_query
    if q_text:
        like = f"%{q_text.strip()}%"
        conds = []
        if hasattr(Documento, "partner_nome"):
            conds.append(Documento.partner_nome.ilike(like))
        if hasattr(Documento, "note"):
            conds.append(Documento.note.ilike(like))
        if conds:
            q = q.filter(or_(*conds))
    if d_from:
        q = q.filter(Documento.data >= d_from)
    if d_to:
        q = q.filter(Documento.data <= d_to)
    if status and status in ("Bozza","Confermato","Stornato","Annullato"):
        q = q.filter(Documento.status == status)
    return q.order_by(desc(Documento.anno), desc(Documento.numero), desc(Documento.id))

@documents_bp.get("/documents")
def documents_list():
    # Retro-compatibilità: punta a IN
    return redirect(url_for("documents.documents_in"))

@documents_bp.get("/documents/in")
def documents_in():
    q_text = request.args.get("q", type=str)
    d_from = _parse_date_any(request.args.get("from_date"))
    d_to   = _parse_date_any(request.args.get("to_date"))
    status = request.args.get("status", type=str)  # Bozza, Confermato, Stornato, Annullato
    page   = request.args.get("page", 1, type=int)
    per    = request.args.get("per_page", DOCUMENTS_PER_PAGE, type=int)

    q = Documento.query.filter(Documento.tipo == "DDT_IN")
    q = _apply_filters(q, q_text=q_text, d_from=d_from, d_to=d_to, status=status)
    pager = q.paginate(page=page, per_page=per, error_out=False)

    return render_template("documents_in.html", pager=pager, docs=pager.items, status=status)

@documents_bp.get("/documents/out")
def documents_out():
    q_text = request.args.get("q", type=str)
    d_from = _parse_date_any(request.args.get("from_date"))
    d_to   = _parse_date_any(request.args.get("to_date"))
    status = request.args.get("status", type=str)  # Bozza, Confermato, Stornato, Annullato
    page   = request.args.get("page", 1, type=int)
    per    = request.args.get("per_page", DOCUMENTS_PER_PAGE, type=int)

    q = Documento.query.filter(Documento.tipo == "DDT_OUT")
    q = _apply_filters(q, q_text=q_text, d_from=d_from, d_to=d_to, status=status)
    pager = q.paginate(page=page, per_page=per, error_out=False)

    return render_template("documents_out.html", pager=pager, docs=pager.items, status=status)

@documents_bp.get("/documents/<int:id>")
def document_detail(id: int):
    doc = Documento.query.get_or_404(id)
    return render_template("document_detail.html", doc=doc)
'@

# ---------- app/templates/documents_in.html ----------
$documents_in_html = @'
{% extends "_base.html" %}
{% block title %}DDT IN{% endblock %}
{% block content %}
<div class="bg-white p-4 rounded-xl shadow">
  <div class="mb-4 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <a href="{{ url_for('documents.documents_in') }}" class="px-3 py-1 rounded {{ 'bg-indigo-600 text-white' if request.endpoint=='documents.documents_in' else 'bg-gray-200 text-gray-800' }}">DDT IN</a>
      <a href="{{ url_for('documents.documents_out') }}" class="px-3 py-1 rounded bg-gray-200 text-gray-800">DDT OUT</a>
    </div>
    <div class="text-xs text-gray-500">Ordinati per n./anno (Anno ↓, Numero ↓)</div>
  </div>

  <form method="get" class="grid grid-cols-1 md:grid-cols-6 gap-2 mb-3">
    <div class="md:col-span-2">
      <label class="text-xs text-gray-600">Fornitore</label>
      <input type="text" name="q" class="w-full border rounded px-2 py-1" placeholder="cerca fornitore" value="{{ request.args.get('q','') }}">
    </div>
    <div>
      <label class="text-xs text-gray-600">Dal</label>
      <input type="date" name="from_date" class="w-full border rounded px-2 py-1" value="{{ request.args.get('from_date','') }}">
    </div>
    <div>
      <label class="text-xs text-gray-600">Al</label>
      <input type="date" name="to_date" class="w-full border rounded px-2 py-1" value="{{ request.args.get('to_date','') }}">
    </div>
    <div>
      <label class="text-xs text-gray-600">Stato</label>
      <select name="status" class="w-full border rounded px-2 py-1">
        {% set s = request.args.get('status') %}
        <option value="" {% if not s %}selected{% endif %}>Tutti</option>
        <option value="Bozza" {% if s=='Bozza' %}selected{% endif %}>Bozze</option>
        <option value="Confermato" {% if s=='Confermato' %}selected{% endif %}>Confermati</option>
        <option value="Stornato" {% if s=='Stornato' %}selected{% endif %}>Stornati</option>
        <option value="Annullato" {% if s=='Annullato' %}selected{% endif %}>Annullati</option>
      </select>
    </div>
    <div class="flex items-end gap-2">
      <button class="px-3 py-2 rounded bg-indigo-600 text-white text-sm">Filtra</button>
      <a class="px-3 py-2 rounded bg-gray-200 text-gray-800 text-sm" href="{{ url_for('documents.documents_in') }}">Reset</a>
    </div>
  </form>

  {% if docs|length == 0 %}
    <div class="text-sm text-gray-500">Nessun DDT IN trovato.</div>
  {% else %}
    <div class="overflow-x-auto">
      <table class="min-w-full text-sm">
        <thead>
          <tr class="text-left border-b">
            <th class="py-2 pr-2">ID</th>
            <th class="py-2 pr-2">Numero</th>
            <th class="py-2 pr-2">Data</th>
            <th class="py-2 pr-2">Fornitore</th>
            <th class="py-2 pr-2">Stato</th>
            <th class="py-2 pr-2"></th>
          </tr>
        </thead>
        <tbody>
          {% for d in docs %}
          <tr class="border-b hover:bg-gray-50">
            <td class="py-2 pr-2">{{ d.id }}</td>
            <td class="py-2 pr-2">
              {% if d.numero is not none and d.anno is not none %}
                <span class="font-medium">{{ d.numero }}/{{ d.anno }}</span>
              {% elif d.numero is not none %}
                <span class="font-medium">{{ d.numero }}</span>
              {% else %}
                <span class="text-gray-400">—</span>
              {% endif %}
            </td>
            <td class="py-2 pr-2">{% if d.data %}<time datetime="{{ d.data }}">{{ d.data }}</time>{% else %}—{% endif %}</td>
            <td class="py-2 pr-2">
              {% if d.partner %}
                {{ d.partner.nome if d.partner.nome else (d.partner.ragione_sociale if d.partner.ragione_sociale else d.partner)|default('', true) }}
              {% elif d.partner_nome %}
                {{ d.partner_nome }}
              {% else %}
                <span class="text-gray-400">—</span>
              {% endif %}
            </td>
            <td class="py-2 pr-2">{{ d.status }}</td>
            <td class="py-2 pr-2">
              <a class="text-indigo-700 hover:underline" href="{{ url_for('documents.document_detail', id=d.id) }}">Apri</a>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    <div class="mt-3 flex items-center gap-2 text-sm">
      <span>Pagina {{ pager.page }} di {{ pager.pages or 1 }}</span>
      <div class="ml-auto flex gap-2">
        {% if pager.has_prev %}
        <a class="px-3 py-1 rounded border" href="{{ url_for('documents.documents_in', page=pager.prev_num, q=request.args.get('q',''), from_date=request.args.get('from_date',''), to_date=request.args.get('to_date',''), status=request.args.get('status','')) }}">Precedente</a>
        {% else %}
        <span class="px-3 py-1 rounded border text-gray-400">Precedente</span>
        {% endif %}

        {% if pager.has_next %}
        <a class="px-3 py-1 rounded border" href="{{ url_for('documents.documents_in', page=pager.next_num, q=request.args.get('q',''), from_date=request.args.get('from_date',''), to_date=request.args.get('to_date',''), status=request.args.get('status','')) }}">Successiva</a>
        {% else %}
        <span class="px-3 py-1 rounded border text-gray-400">Successiva</span>
        {% endif %}
      </div>
    </div>
  {% endif %}
</div>
{% endblock %}
'@

# ---------- app/templates/documents_out.html ----------
$documents_out_html = @'
{% extends "_base.html" %}
{% block title %}DDT OUT{% endblock %}
{% block content %}
<div class="bg-white p-4 rounded-xl shadow">
  <div class="mb-4 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <a href="{{ url_for('documents.documents_in') }}" class="px-3 py-1 rounded bg-gray-200 text-gray-800">DDT IN</a>
      <a href="{{ url_for('documents.documents_out') }}" class="px-3 py-1 rounded {{ 'bg-indigo-600 text-white' if request.endpoint=='documents.documents_out' else 'bg-gray-200 text-gray-800' }}">DDT OUT</a>
    </div>
    <div class="text-xs text-gray-500">Ordinati per n./anno (Anno ↓, Numero ↓)</div>
  </div>

  <form method="get" class="grid grid-cols-1 md:grid-cols-6 gap-2 mb-3">
    <div class="md:col-span-2">
      <label class="text-xs text-gray-600">Cliente</label>
      <input type="text" name="q" class="w-full border rounded px-2 py-1" placeholder="cerca cliente" value="{{ request.args.get('q','') }}">
    </div>
    <div>
      <label class="text-xs text-gray-600">Dal</label>
      <input type="date" name="from_date" class="w-full border rounded px-2 py-1" value="{{ request.args.get('from_date','') }}">
    </div>
    <div>
      <label class="text-xs text-gray-600">Al</label>
      <input type="date" name="to_date" class="w-full border rounded px-2 py-1" value="{{ request.args.get('to_date','') }}">
    </div>
    <div>
      <label class="text-xs text-gray-600">Stato</label>
      <select name="status" class="w-full border rounded px-2 py-1">
        {% set s = request.args.get('status') %}
        <option value="" {% if not s %}selected{% endif %}>Tutti</option>
        <option value="Bozza" {% if s=='Bozza' %}selected{% endif %}>Bozze</option>
        <option value="Confermato" {% if s=='Confermato' %}selected{% endif %}>Confermati</option>
        <option value="Stornato" {% if s=='Stornato' %}selected{% endif %}>Stornati</option>
        <option value="Annullato" {% if s=='Annullato' %}selected{% endif %}>Annullati</option>
      </select>
    </div>
    <div class="flex items-end gap-2">
      <button class="px-3 py-2 rounded bg-indigo-600 text-white text-sm">Filtra</button>
      <a class="px-3 py-2 rounded bg-gray-200 text-gray-800 text-sm" href="{{ url_for('documents.documents_out') }}">Reset</a>
    </div>
  </form>

  {% if docs|length == 0 %}
    <div class="text-sm text-gray-500">Nessun DDT OUT trovato.</div>
  {% else %}
    <div class="overflow-x-auto">
      <table class="min-w-full text-sm">
        <thead>
          <tr class="text-left border-b">
            <th class="py-2 pr-2">ID</th>
            <th class="py-2 pr-2">Numero</th>
            <th class="py-2 pr-2">Data</th>
            <th class="py-2 pr-2">Cliente</th>
            <th class="py-2 pr-2">Stato</th>
            <th class="py-2 pr-2"></th>
          </tr>
        </thead>
        <tbody>
          {% for d in docs %}
          <tr class="border-b hover:bg-gray-50">
            <td class="py-2 pr-2">{{ d.id }}</td>
            <td class="py-2 pr-2">
              {% if d.numero is not none and d.anno is not none %}
                <span class="font-medium">{{ d.numero }}/{{ d.anno }}</span>
              {% elif d.numero is not none %}
                <span class="font-medium">{{ d.numero }}</span>
              {% else %}
                <span class="text-gray-400">—</span>
              {% endif %}
            </td>
            <td class="py-2 pr-2">{% if d.data %}<time datetime="{{ d.data }}">{{ d.data }}</time>{% else %}—{% endif %}</td>
            <td class="py-2 pr-2">
              {% if d.partner %}
                {{ d.partner.nome if d.partner.nome else (d.partner.ragione_sociale if d.partner.ragione_sociale else d.partner)|default('', true) }}
              {% elif d.partner_nome %}
                {{ d.partner_nome }}
              {% else %}
                <span class="text-gray-400">—</span>
              {% endif %}
            </td>
            <td class="py-2 pr-2">{{ d.status }}</td>
            <td class="py-2 pr-2">
              <a class="text-indigo-700 hover:underline" href="{{ url_for('documents.document_detail', id=d.id) }}">Apri</a>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    <div class="mt-3 flex items-center gap-2 text-sm">
      <span>Pagina {{ pager.page }} di {{ pager.pages or 1 }}</span>
      <div class="ml-auto flex gap-2">
        {% if pager.has_prev %}
        <a class="px-3 py-1 rounded border" href="{{ url_for('documents.documents_out', page=pager.prev_num, q=request.args.get('q',''), from_date=request.args.get('from_date',''), to_date=request.args.get('to_date',''), status=request.args.get('status','')) }}">Precedente</a>
        {% else %}
        <span class="px-3 py-1 rounded border text-gray-400">Precedente</span>
        {% endif %}

        {% if pager.has_next %}
        <a class="px-3 py-1 rounded border" href="{{ url_for('documents.documents_out', page=pager.next_num, q=request.args.get('q',''), from_date=request.args.get('from_date',''), to_date=request.args.get('to_date',''), status=request.args.get('status','')) }}">Successiva</a>
        {% else %}
        <span class="px-3 py-1 rounded border text-gray-400">Successiva</span>
        {% endif %}
      </div>
    </div>
  {% endif %}
</div>
{% endblock %}
'@

# Scrivi i file (UTF8 corretto)
Set-Content -Path (Join-Path $bpDir  "documents.py")       -Value $documents_py       -Encoding UTF8
Set-Content -Path (Join-Path $tplDir "documents_in.html")  -Value $documents_in_html  -Encoding UTF8
Set-Content -Path (Join-Path $tplDir "documents_out.html") -Value $documents_out_html -Encoding UTF8

# Hint su registrazione blueprint
$initPath = Join-Path $root "app\__init__.py"
if (Test-Path $initPath) {
  $initText = Get-Content $initPath -Raw
  if ($initText -notmatch "from \.blueprints\.documents import documents_bp" -or $initText -notmatch "app\.register_blueprint\(documents_bp\)") {
    Write-Host "ATTENZIONE: Verifica in app/__init__.py l'import e la registrazione del blueprint 'documents':" -ForegroundColor Yellow
    Write-Host "  from .blueprints.documents import documents_bp" -ForegroundColor Yellow
    Write-Host "  app.register_blueprint(documents_bp)" -ForegroundColor Yellow
  }
}

Write-Host "Patch applicata. Riavvia l'app e usa /documents/in e /documents/out" -ForegroundColor Green
