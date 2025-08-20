// app/static/js/pages/ddt-import.js
/**
 * Modulo per gestione import DDT da PDF
 * Responsabilità singola: logica UI import DDT
 */

class DDTImportManager {
    constructor() {
        this.parsedDDT = null;
        this.previewState = null;
        this.mastriniList = [];
        
        // Usa servizi condivisi
        this.apiClient = window.apiClient || new APIClient();
        this.errorHandler = window.errorHandler || new ErrorHandler();
        this.loadingOverlay = window.loadingOverlay || new LoadingOverlay();
        
        this.initializeElements();
        this.attachEventListeners();
        this.loadInitialData();
    }
    
    initializeElements() {
        // Form elements
        this.uploadForm = document.getElementById('form-ddt');
        this.confirmBtn = document.getElementById('btn-ddt-confirm');
        this.fornitoreField = document.getElementById('fld-fornitore');
        this.magazzinoSelect = document.getElementById('sel-magazzino');
        this.commessaSelect = document.getElementById('sel-commessa');
        
        // Container elements
        this.metaBox = document.getElementById('meta-box');
        this.rowsBox = document.getElementById('rows-box');
        this.noteBox = document.getElementById('ddt-note');
        this.noteText = document.getElementById('note-text');
        this.rowsTable = document.getElementById('rows-table');
        this.rowsBody = document.getElementById('rows-body');
        this.rowsCount = document.getElementById('rows-count');
        this.rowsTotal = document.getElementById('rows-total');
        
        // Dev buttons (if present)
        this.devButtons = {
            clearIn: document.getElementById('btn-clear-in'),
            clearOut: document.getElementById('btn-clear-out'),
            clearArt: document.getElementById('btn-clear-art')
        };
    }
    
    attachEventListeners() {
        // Upload form
        if (this.uploadForm) {
            this.uploadForm.addEventListener('submit', (e) => this.handleUpload(e));
        }
        
        // Confirm button
        if (this.confirmBtn) {
            this.confirmBtn.addEventListener('click', () => this.handleConfirm());
        }
        
        // Dev buttons
        Object.entries(this.devButtons).forEach(([key, btn]) => {
            if (btn) {
                btn.addEventListener('click', () => this.handleDevAction(key));
            }
        });
        
        // Listen per aggiornamenti righe
        if (this.rowsBody) {
            this.rowsBody.addEventListener('input', () => this.updateRowsSummary());
        }
    }
    
    async loadInitialData() {
        try {
            this.loadingOverlay.show('Caricamento dati iniziali…');
            
            await Promise.all([
                this.loadMagazzini(),
                this.loadClienti(), 
                this.loadMastrini()
            ]);
            
            this.errorHandler.showSuccess('Dati caricati correttamente');
            
        } catch (error) {
            this.errorHandler.handleAPIError(error, 'Caricamento dati iniziali');
        } finally {
            this.loadingOverlay.hide();
        }
    }
    
    async loadMagazzini() {
        const response = await this.apiClient.get('/api/magazzini');
        const magazzini = response.data || response;
        
        this.populateSelect(this.magazzinoSelect, magazzini, {
            valueField: 'id',
            textFormatter: (m) => `${m.codice} — ${m.nome}`
        });
    }
    
    async loadClienti() {
        const response = await this.apiClient.get('/api/clienti');
        const clienti = response.data || response;
        
        this.populateSelect(this.commessaSelect, clienti, {
            valueField: 'id',
            textFormatter: (c) => c.nome,
            includeEmpty: true,
            emptyText: '— Nessuna —'
        });
    }
    
    async loadMastrini() {
        const response = await this.apiClient.get('/api/mastrini?tipo=ACQUISTO');
        this.mastriniList = response.data || response;
    }
    
    populateSelect(selectElement, items, options = {}) {
        if (!selectElement) return;
        
        selectElement.innerHTML = '';
        
        if (options.includeEmpty) {
            const emptyOpt = document.createElement('option');
            emptyOpt.value = '';
            emptyOpt.textContent = options.emptyText || '— Seleziona —';
            selectElement.appendChild(emptyOpt);
        }
        
        items.forEach(item => {
            const opt = document.createElement('option');
            opt.value = item[options.valueField || 'id'];
            opt.textContent = options.textFormatter ? 
                options.textFormatter(item) : 
                item.nome || item.descrizione || item.codice;
            selectElement.appendChild(opt);
        });
    }
    
    async handleUpload(event) {
        event.preventDefault();
        
        try {
            const formData = new FormData(event.target);
            
            // Validazione client-side
            const file = formData.get('pdf_file');
            if (!file || file.size === 0) {
                throw new Error('Seleziona un file PDF');
            }
            
            if (file.size > 32 * 1024 * 1024) { // 32MB
                throw new Error('File troppo grande (max 32MB)');
            }
            
            this.loadingOverlay.show('Estrazione dati dal PDF in corso…');
            
            // Step 1: Parse PDF (nuovo endpoint)
            this.parsedDDT = await this.apiClient.postForm('/api/import/ddt/parse', formData);
            
            // Show parsing method note
            this.showParsingNote(this.parsedDDT);
            
            // Step 2: Create preview (nuovo endpoint)
            this.previewState = await this.apiClient.post('/api/import/ddt/preview', {
                data: this.parsedDDT.data,
                uploaded_file: this.parsedDDT.uploaded_file
            });
            
            // Update UI
            this.populateMetaFields(this.previewState.preview);
            this.renderRows(this.previewState.preview.righe || []);
            this.showEditableFields();
            
            this.errorHandler.showSuccess('Dati estratti con successo dal PDF');
            
        } catch (error) {
            this.errorHandler.handleAPIError(error, 'Parsing DDT');
        } finally {
            this.loadingOverlay.hide();
        }
    }
    
    showParsingNote(parsedData) {
        if (!this.noteBox || !this.noteText || !parsedData.method) return;
        
        let noteText = `Metodo parsing: ${parsedData.method}`;
        if (parsedData.note) {
            noteText += ` — ${parsedData.note}`;
        }
        
        this.noteText.textContent = noteText;
        this.noteBox.classList.remove('hidden');
    }
    
    populateMetaFields(preview) {
        if (this.fornitoreField) {
            this.fornitoreField.value = preview.fornitore || '';
        }
    }
    
    renderRows(righe) {
        if (!this.rowsBody) return;
        
        this.rowsBody.innerHTML = '';
        
        const defaultMastrino = this.mastriniList.length > 0 ? this.mastriniList[0].codice : '';
        
        righe.forEach((riga, index) => {
            const tr = this.createRowElement(riga, defaultMastrino);
            this.rowsBody.appendChild(tr);
        });
        
        this.updateRowsSummary();
    }
    
    createRowElement(riga, defaultMastrino) {
        const tr = document.createElement('tr');
        tr.className = 'border-t hover:bg-gray-50';
        
        const mastrinoOptions = this.mastriniList.map(m => 
            `<option value="${m.codice}" ${m.codice === (riga.mastrino_codice || defaultMastrino) ? 'selected' : ''}>
                ${m.codice} — ${m.descrizione}
            </option>`
        ).join('');
        
        tr.innerHTML = `
            <td class="p-3">
                <input class="w-full border border-gray-300 rounded p-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent" 
                       value="${this.escapeHtml(riga.codice || '')}"
                       data-field="codice"
                       placeholder="Codice fornitore">
            </td>
            <td class="p-3">
                <input class="w-full border border-gray-300 rounded p-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent" 
                       value="${this.escapeHtml(riga.descrizione || '')}"
                       data-field="descrizione"
                       placeholder="Descrizione articolo">
            </td>
            <td class="p-3 text-right">
                <input type="number" step="0.001" min="0"
                       class="w-24 border border-gray-300 rounded p-2 text-sm text-right focus:ring-2 focus:ring-blue-500 focus:border-transparent" 
                       value="${Number(riga.quantità || riga.quantita || riga.qty || 1)}"
                       data-field="quantita"
                       placeholder="Q.tà">
            </td>
            <td class="p-3">
                <input class="w-16 border border-gray-300 rounded p-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent" 
                       value="${this.escapeHtml(riga.um || 'PZ')}"
                       data-field="um"
                       placeholder="UM">
            </td>
            <td class="p-3 text-right">
                <input type="number" step="0.01" min="0"
                       class="w-24 border border-gray-300 rounded p-2 text-sm text-right focus:ring-2 focus:ring-blue-500 focus:border-transparent" 
                       value="${Number(riga.prezzo_unitario || riga.prezzo || 0)}"
                       data-field="prezzo"
                       placeholder="Prezzo">
            </td>
            <td class="p-3">
                <select class="border border-gray-300 rounded p-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent" data-field="mastrino">
                    ${mastrinoOptions}
                </select>
            </td>
        `;
        
        return tr;
    }
    
    showEditableFields() {
        if (this.metaBox) this.metaBox.classList.remove('hidden');
        if (this.rowsBox) this.rowsBox.classList.remove('hidden');
        if (this.confirmBtn) this.confirmBtn.disabled = false;
    }
    
    updateRowsSummary() {
        if (!this.rowsBody || !this.rowsCount || !this.rowsTotal) return;
        
        const rows = this.rowsBody.querySelectorAll('tr');
        let totalAmount = 0;
        
        rows.forEach(tr => {
            const qtyInput = tr.querySelector('[data-field="quantita"]');
            const priceInput = tr.querySelector('[data-field="prezzo"]');
            
            if (qtyInput && priceInput) {
                const qty = parseFloat(qtyInput.value) || 0;
                const price = parseFloat(priceInput.value) || 0;
                totalAmount += qty * price;
            }
        });
        
        this.rowsCount.textContent = `${rows.length} righe`;
        this.rowsTotal.textContent = `Totale: € ${totalAmount.toFixed(2)}`;
    }
    
    readRowsFromDOM() {
        if (!this.rowsBody) return [];
        
        const rows = [];
        this.rowsBody.querySelectorAll('tr').forEach(tr => {
            const row = {};
            tr.querySelectorAll('[data-field]').forEach(input => {
                const field = input.dataset.field;
                let value = input.value.trim();
                
                // Type conversion
                if (field === 'quantita' || field === 'prezzo') {
                    value = parseFloat(value.replace(',', '.')) || 0;
                }
                
                // Field mapping
                switch (field) {
                    case 'quantita':
                        row.quantità = value;
                        break;
                    case 'prezzo':
                        row.prezzo_unitario = value;
                        break;
                    case 'mastrino':
                        row.mastrino_codice = value;
                        break;
                    default:
                        row[field] = value;
                }
            });
            
            // Validazione riga
            if (row.descrizione && row.quantità > 0) {
                rows.push(row);
            }
        });
        
        return rows;
    }
    
    async handleConfirm() {
        if (!this.previewState) {
            this.errorHandler.show('Prima estrai i dati dal PDF');
            return;
        }
        
        try {
            // Validazione
            const rows = this.readRowsFromDOM();
            if (rows.length === 0) {
                throw new Error('Aggiungi almeno una riga valida');
            }
            
            const fornitore = this.fornitoreField?.value?.trim();
            if (!fornitore) {
                throw new Error('Inserisci il nome del fornitore');
            }
            
            this.loadingOverlay.show('Creazione documento in corso…');
            
            const payload = {
                fornitore: fornitore,
                righe: rows,
                uploaded_file: this.previewState.preview.uploaded_file,
                magazzino_id: this.magazzinoSelect?.value || null,
                commessa_id: this.commessaSelect?.value || null
            };
            
            // Nuovo endpoint
            const result = await this.apiClient.post('/api/import/ddt/confirm', payload);
            
            this.errorHandler.showSuccess('Documento DDT creato con successo');
            
            // Redirect to document
            if (result.redirect_url) {
                window.location.href = result.redirect_url;
            } else if (result.document_id) {
                window.location.href = `/documents/${result.document_id}`;
            } else {
                this.errorHandler.show('Documento creato ma senza URL di redirect');
            }
            
        } catch (error) {
            this.errorHandler.handleAPIError(error, 'Creazione documento');
        } finally {
            this.loadingOverlay.hide();
        }
    }
    
    async handleDevAction(action) {
        const endpoints = {
            clearIn: '/test/clear-ddt-in',
            clearOut: '/test/clear-ddt-out', 
            clearArt: '/test/clear-articles'
        };
        
        const endpoint = endpoints[action];
        if (!endpoint) return;
        
        if (!confirm(`Sei sicuro di voler eliminare tutti i dati di test (${action})?`)) {
            return;
        }
        
        try {
            this.loadingOverlay.show('Pulizia dati di test…');
            const result = await this.apiClient.post(endpoint);
            this.errorHandler.showSuccess(result.msg || 'Operazione completata');
        } catch (error) {
            this.errorHandler.handleAPIError(error, 'Pulizia dati');
        } finally {
            this.loadingOverlay.hide();
        }
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if we're on the DDT import page
    const importModule = document.querySelector('[data-module="ddt-import"]');
    if (importModule) {
        new DDTImportManager();
        console.log('✅ DDT Import Manager initialized');
    }
});

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DDTImportManager;
}