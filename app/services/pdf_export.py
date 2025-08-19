from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from decimal import Decimal

from ..models import Documento, RigaDocumento

def export_document_pdf(doc: Documento) -> bytes:
    buffer = BytesIO()
    doc_template = SimpleDocTemplate(buffer, pagesize=letter)
    
    styles = getSampleStyleSheet()
    story = []

    # Titolo
    title_str = f"Documento {doc.tipo} N. {doc.numero}/{doc.anno}" if doc.numero else f"Documento {doc.tipo} (Bozza)"
    story.append(Paragraph(title_str, styles['h1']))
    story.append(Spacer(1, 0.2*inch))

    # Dettagli intestazione
    partner_type = "Cliente" if doc.tipo == "DDT_OUT" else "Fornitore"
    header_data = [
        ["Data Documento:", doc.data.strftime('%d/%m/%Y') if doc.data else "N/A"],
        [f"{partner_type}:", doc.partner.nome if doc.partner else "N/A"],
        ["Magazzino:", f"{doc.magazzino.codice} - {doc.magazzino.nome}" if doc.magazzino else "N/A"],
    ]
    header_table = Table(header_data, colWidths=[1.5*inch, 4*inch])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.3*inch))

    # Tabella righe
    rows = doc.righe.order_by(RigaDocumento.id).all()
    
    # Intestazioni tabella - Aggiunto Mastrino
    table_data = [
        ["Codice", "Descrizione", "Q.tà", "Prezzo", "Mastrino", "Totale"]
    ]
    
    # Dati righe - Aggiunto Mastrino
    for r in rows:
        # Calcolo sicuro del totale
        quantita = r.quantita or Decimal('0')
        prezzo = r.prezzo or Decimal('0')
        totale_riga = quantita * prezzo
        
        table_data.append([
            r.articolo.codice_interno if r.articolo else '',
            Paragraph(r.descrizione or '', styles['Normal']),
            f"{quantita:.2f}",
            f"{prezzo:.2f}",
            r.mastrino_codice or '',
            f"{totale_riga:.2f}"
        ])

    # Creazione tabella e stile
    col_widths = [0.8*inch, 3*inch, 0.6*inch, 0.7*inch, 1*inch, 0.8*inch]
    righe_table = Table(table_data, colWidths=col_widths)
    righe_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), # FIX: Corretto da whitespoke a whitesmoke
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (2,1), (-1,-1), 'RIGHT'), # Allinea a destra qta, prezzo, totale
        ('ALIGN', (4,1), (4,-1), 'LEFT'), # Allinea a sinistra mastrino
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    story.append(righe_table)

    doc_template.build(story)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
