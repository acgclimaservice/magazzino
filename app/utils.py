import re
from datetime import datetime, date, time
from decimal import Decimal, InvalidOperation
from sqlalchemy import func, and_
from .extensions import db
from .models import Articolo, Giacenza, Magazzino, Documento

# --- Validazioni / parsing formali ---

def parse_it_date(s: str) -> date:
    s = (s or '').strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError("Formato data non valido. Usa YYYY-MM-DD o gg/mm/aaaa.")

def q_dec(value: str, scale='0.001', allow_zero=False, field="Quantità") -> Decimal:
    s = (str(value) if value is not None else '').strip().replace(',', '.')
    try:
        q = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"{field} non valida.")
    if (not allow_zero and q <= 0) or (allow_zero and q < 0):
        raise ValueError(f"{field} deve essere {'> 0' if not allow_zero else '>= 0'}.")
    return q.quantize(Decimal(scale))

def money_dec(value: str) -> Decimal:
    s = (str(value) if value is not None else '').strip().replace(',', '.')
    if not s:
        return Decimal('0.00')
    try:
        return Decimal(s).quantize(Decimal('0.01'))
    except InvalidOperation:
        raise ValueError("Importo non valido.")

def required(s: str, name: str) -> str:
    if not s or not str(s).strip():
        raise ValueError(f"{name} è obbligatorio.")
    return str(s).strip()

# --- Giacenze / numerazioni ---

def get_giacenza(articolo_id, magazzino_id, session=None) -> Decimal:
    db_session = session or db.session
    g = db_session.query(Giacenza).filter_by(articolo_id=articolo_id, magazzino_id=magazzino_id).first()
    return g.quantita if g else Decimal('0.000')

def update_giacenza(articolo_id, magazzino_id, qty, session=None):
    db_session = session or db.session
    qty = qty if isinstance(qty, Decimal) else Decimal(str(qty))
    qty = qty.quantize(Decimal('0.001'))
    g = db_session.query(Giacenza).filter_by(articolo_id=articolo_id, magazzino_id=magazzino_id).first()
    if g:
        g.quantita = (g.quantita + qty).quantize(Decimal('0.001'))
        if g.quantita < 0:
            raise ValueError("Operazione non valida: giacenza negativa.")
    else:
        if qty < 0:
            raise ValueError("Impossibile creare giacenza negativa.")
        g = Giacenza(articolo_id=articolo_id, magazzino_id=magazzino_id, quantita=qty)
        db_session.add(g)
    return g

def next_doc_number(doc_type, year=None) -> int:
    year = year or date.today().year
    last = (Documento.query
            .filter(Documento.tipo == doc_type, Documento.anno == year, Documento.numero != None)
            .order_by(Documento.numero.desc())
            .first())
    return (last.numero + 1) if last and last.numero is not None else 1

# --- Normalizzazione UM ---

UM_MAP = {
    "PZ": "PZ", "PCS": "PZ", "PEZZO": "PZ", "PEZZI": "PZ", "NR": "PZ", "N": "PZ",
    "M": "M", "MT": "M", "METRO": "M", "METRI": "M",
    "KG": "KG", "KGS": "KG", "KILOGRAMMI": "KG",
    "G": "G", "GR": "G", "GRAMMI": "G",
    "L": "L", "LT": "L", "LITRI": "L",
    "ML": "ML"
}
def unify_um(um: str) -> str:
    if not um:
        return "PZ"
    key = re.sub(r'[^A-Z]', '', um.upper())
    return UM_MAP.get(key, key[:5] or "PZ")

# --- Generazione codici interni ---

def _clean_token(s: str) -> str:
    return re.sub(r'[^A-Z0-9]', '', (s or '').upper())

def supplier_prefix(fornitore: str) -> str:
    """Restituisce un prefisso 'parlante' per il codice interno, in base al fornitore."""
    f = _clean_token(fornitore or '')
    # mapping più comuni
    if 'CAMBIELLI' in f:
        return 'CAM'
    if 'SAB' in f and 'SAB' == f[:3]:
        return 'SAB'
    if 'WURTH' in f or 'WÜRTH' in f:
        return 'WUR'
    if 'FERRAMENTA' in f:
        return 'FER'
    # fallback: prime 3 lettere utili
    base = (f[:3] or 'INT')
    return base

def gen_internal_code(prefix: str, supplier_code: str | None = None) -> str:
    """
    Genera un codice interno univoco:
    - se supplier_code è valorizzato e non crea collisioni: PREFIX + <supplier_code_clean>
    - altrimenti genera sequenza PREFIX + 6 cifre (progressivo)
    """
    pre = _clean_token(prefix)[:6] or 'INT'
    if supplier_code:
        suff = _clean_token(supplier_code)[:20]
        cand = f"{pre}{suff}"[:30]
        if not Articolo.query.filter_by(codice_interno=cand).first():
            return cand

    # progressivo a 6 cifre
    import re as _re
    pattern = f"^{pre}(\\d+)$"
    max_n = 0
    for a in Articolo.query.filter(Articolo.codice_interno.like(f"{pre}%")).all():
        m = _re.match(pattern, a.codice_interno or '')
        if m:
            try:
                n = int(m.group(1))
                if n > max_n: max_n = n
            except:
                pass
    return f"{pre}{max_n + 1:06d}"

def gen_code_from_descr(descr: str) -> str:
    base = re.sub(r'[^A-Z0-9]', '', (descr or 'AUTO')[:12].upper())
    if not base:
        base = "AUTO"
    code = base
    i = 1
    while Articolo.query.filter_by(codice_interno=code).first():
        i += 1
        code = f"{base[:10]}{i:02d}"
    return code
