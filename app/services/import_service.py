# app/services/import_service.py
"""
Servizio dedicato all'import di documenti DDT da PDF.
Responsabilità singola: gestire il flusso di import.
"""
from typing import Dict, Any, Tuple, Optional, List
from decimal import Decimal
from flask import current_app
from ..extensions import db
from ..models import Articolo, Magazzino, Partner, Documento, RigaDocumento, Allegato, Mastrino
from ..utils import q_dec, money_dec, supplier_prefix, gen_internal_code, unify_um
from .pdf_service import PDFService
from .parsing_service import ParsingService  
from .file_service import FileService


class ImportService:
    """Servizio per import DDT da PDF"""
    
    def __init__(self):
        self.pdf_service = PDFService()
        self.parsing_service = ParsingService()
        self.file_service = FileService()
    
    def parse_ddt_from_upload(self, file_storage) -> Dict[str, Any]:
        """
        Estrae dati da PDF caricato.
        Returns: {"ok": bool, "data": dict, "method": str, "note": str, "uploaded_file": str}
        """
        try:
            # Estrai testo PDF
            raw_text = self.pdf_service.extract_text(file_storage)
            
            # Salva file per allegarlo successivamente
            file_storage.stream.seek(0)
            rel_path, abs_path = self.file_service.save_upload(file_storage, category="incoming_ddt")
            
            # Parsing con fallback
            
            return {
                "ok": True,
                "data": data,
                "method": method,
                "note": note or "",
                "uploaded_file": rel_path
            }
            
        except Exception as e:
            current_app.logger.exception("Errore in parse_ddt_from_upload")
            return {
                "ok": False,
                "error": str(e)
            }
    
    def create_preview(self, parsed_data: Dict, uploaded_file: str) -> Dict[str, Any]:
        """
        Crea preview normalizzata per l'UI.
        """
        try:
            d = parsed_data.get("data", {})
            righe = d.get("righe", []) or d.get("articoli", [])
            
            # Normalizza UM
            for r in righe:
                r["um"] = unify_um(r.get("um"))
            
            # Gestione speciale DUOTERMICA
            vendor = (d.get("fornitore", "") or "").upper()
            if "DUOTERMICA" in vendor and uploaded_file:
                try:
                    righe = self._apply_duotermica_override(uploaded_file, righe)
                except Exception as e:
                    current_app.logger.warning(f"DUOTERMICA override fallito: {e}")
            
            preview = {
                "fornitore": d.get("fornitore"),
                "righe": righe,
                "uploaded_file": uploaded_file
            }
            
            if not preview["righe"]:
                return {"ok": False, "error": "Nessuna riga trovata"}
                
            return {"ok": True, "preview": preview}
            
        except Exception as e:
            current_app.logger.exception("Errore in create_preview")
            return {"ok": False, "error": str(e)}
    
    def import_ddt_in(self, 
                     fornitore_nome: str, 
                     righe: List[Dict], 
                     uploaded_file: str = None,
                     magazzino_id: int = None,
                     commessa_id: int = None) -> Dict[str, Any]:
        """
        Crea documento DDT IN da dati importati.
        """
        try:
            if not fornitore_nome or not righe:
                return {"ok": False, "error": "Dati insufficienti (fornitore, righe)"}
            
            # Partner
            partner = self._get_or_create_partner(fornitore_nome, 'Fornitore')
            
            # Magazzino
            magazzino = self._get_magazzino(magazzino_id)
            if not magazzino:
                return {"ok": False, "error": "Nessun magazzino configurato"}
            
            # Documento
            doc = Documento(
                tipo='DDT_IN',
                partner_id=partner.id,
                magazzino_id=magazzino.id,
                commessa_id=commessa_id,
                status='Bozza'
            )
            db.session.add(doc)
            db.session.flush()
            
            # Righe
            mastrino_default = self._get_default_acquisto_mastrino()
            pref = supplier_prefix(fornitore_nome)
            
            for r in righe:
                riga_doc = self._create_riga_from_import(doc.id, r, fornitore_nome, pref, mastrino_default)
                db.session.add(riga_doc)
            
            # Allegato
            if uploaded_file:
                self._attach_uploaded_file(doc.id, uploaded_file)
            
            db.session.commit()
            
            return {
                "ok": True,
                "document_id": doc.id,
                "redirect_url": f"/documents/{doc.id}"
            }
            
        except Exception as e:
            current_app.logger.exception("Errore in import_ddt_in")
            db.session.rollback()
            return {"ok": False, "error": str(e)}
    
    # ===== METODI PRIVATI =====
    
    def _apply_duotermica_override(self, uploaded_file: str, default_righe: List) -> List:
        """Applica parsing specifico DUOTERMICA"""
        rel = uploaded_file.lstrip("/\\")
        if not rel:
            return default_righe
            
        abs_path = self.file_service.get_absolute_path(rel)
        raw = self.pdf_service.extract_text_from_file(abs_path)
        parsed = self.parsing_service.parse_ddt_duotermica(raw) or {}
        return parsed.get("righe", []) or default_righe
    
    def _get_or_create_partner(self, nome: str, tipo: str) -> Partner:
        """Ottieni o crea partner"""
        partner = Partner.query.filter_by(nome=nome).first()
        if partner is None:
            partner = Partner(nome=nome, tipo=tipo)
            db.session.add(partner)
            db.session.flush()
        elif partner.tipo != tipo:
            partner.tipo = tipo
        return partner
    
    def _get_magazzino(self, magazzino_id: int = None) -> Optional[Magazzino]:
        """Ottieni magazzino"""
        if magazzino_id:
            return Magazzino.query.get(magazzino_id)
        return Magazzino.query.order_by(Magazzino.id).first()
    
    def _get_default_acquisto_mastrino(self) -> str:
        """Ottieni mastrino acquisto di default"""
        m = Mastrino.query.filter_by(tipo='ACQUISTO').order_by(Mastrino.codice).first()
        if m:
            return m.codice
        # Crea mastrino di default se non esiste
        m = Mastrino(codice='0590001003', descrizione='ACQUISTO MATERIALE DI CONSUMO', tipo='ACQUISTO')
        db.session.add(m)
        db.session.flush()
        return m.codice
    
    def _create_riga_from_import(self, documento_id: int, riga_data: Dict, 
                               fornitore_nome: str, prefix: str, mastrino_default: str) -> RigaDocumento:
        """Crea riga documento da dati import"""
        sup_code = (riga_data.get('codice') or '').strip()
        descr = (riga_data.get('descrizione') or '').strip() or sup_code or "Articolo"
        
        # Quantità
        qty_raw = (riga_data.get('quantità') or 
                  riga_data.get('quantitÃ ') or 
                  riga_data.get('quantita') or 
                  riga_data.get('qty'))
        
        if qty_raw in (None, ''):
            raise ValueError(f"Quantità mancante per riga con codice fornitore '{sup_code or 'N/A'}'")
        
        um = unify_um(riga_data.get('um'))
        qty_dec = self._to_decimal(qty_raw)
        unit_price = self._extract_unit_price(riga_data, qty_dec)
        mastrino_row = (riga_data.get('mastrino_codice') or '').strip() or mastrino_default
        
        # Articolo
        art = self._get_or_create_articolo(sup_code, descr, fornitore_nome, prefix, unit_price)
        
        return RigaDocumento(
            documento_id=documento_id,
            articolo_id=art.id,
            descrizione=f"{descr} [{um}]",
            quantita=q_dec(str(qty_raw)),
            prezzo=unit_price.quantize(Decimal('0.01')) if unit_price is not None else Decimal('0.00'),
            mastrino_codice=mastrino_row
        )
    
    def _get_or_create_articolo(self, sup_code: str, descr: str, 
                              fornitore_nome: str, prefix: str, unit_price: Decimal) -> Articolo:
        """Ottieni o crea articolo"""
        art = None
        if sup_code:
            art = Articolo.query.filter_by(codice_fornitore=sup_code, fornitore=fornitore_nome).first()
        if not art:
            art = Articolo.query.filter_by(codice_interno=sup_code).first()
        
        if art is None:
            internal = gen_internal_code(prefix, supplier_code=sup_code or None)
            art = Articolo(
                codice_interno=internal,
                codice_fornitore=sup_code or None,
                descrizione=descr,
                fornitore=fornitore_nome,
                last_cost=(unit_price.quantize(Decimal('0.01')) if unit_price is not None else Decimal('0.00'))
            )
            db.session.add(art)
            db.session.flush()
        else:
            # Aggiorna articolo esistente
            if sup_code and not art.codice_fornitore:
                art.codice_fornitore = sup_code
            if not art.fornitore:
                art.fornitore = fornitore_nome
            art.last_cost = (unit_price.quantize(Decimal('0.01')) if unit_price is not None else Decimal('0.00'))
        
        return art
    
    def _to_decimal(self, x) -> Optional[Decimal]:
        """Converte valore in Decimal"""
        if x is None:
            return None
        if isinstance(x, (int, float, Decimal)):
            try:
                return Decimal(str(x))
            except Exception:
                return None
        s = str(x).strip().replace('€','').replace('\\xa0','').replace(' ', '').replace(',', '.')
        import re
        m = re.search(r'[-+]?\\d+(?:\\.\\d+)?', s)
        if not m:
            return None
        try:
            return Decimal(m.group(0))
        except:
            return None
    
    def _extract_unit_price(self, row: Dict, qty_dec: Optional[Decimal]) -> Decimal:
        """Estrae prezzo unitario da riga"""
        for k in ['prezzo_unitario', 'prezzo', 'unit_price', 'importo_unitario']:
            v = row.get(k)
            val = self._to_decimal(v)
            if val is not None:
                return val
        
        for k in ['totale_riga', 'totale', 'importo', 'importo_riga']:
            v = row.get(k)
            tot = self._to_decimal(v)
            if tot is not None and qty_dec and qty_dec != 0:
                try:
                    return (tot / qty_dec).quantize(Decimal('0.01'))
                except Exception:
                    pass
        
        return Decimal('0.00')
    
    def _attach_uploaded_file(self, doc_id: int, uploaded_file: str):
        """Allega file caricato al documento"""
        try:
            new_rel, new_abs = self.file_service.move_upload_to_document(uploaded_file, doc_id)
            import os
            allegato = Allegato(
                documento_id=doc_id,
                filename=os.path.basename(new_abs),
                mime='application/pdf',
                path=new_rel,
                size=os.path.getsize(new_abs) if os.path.exists(new_abs) else 0
            )
            db.session.add(allegato)
        except Exception as e:
            current_app.logger.warning(f"Impossibile allegare file: {e}")