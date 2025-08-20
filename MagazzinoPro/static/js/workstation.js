document.addEventListener('DOMContentLoaded', () => {
        const app = {
            state: {
                ticket: {},
                mpls: {
                    ore_manodopera: 0.0,
                    sovrapprezzo: 0.00,
                },
                materiali: [],
                isGuazzotti: false,
                risultatiCalcolo: {},
                rtiCounter: 1,
                currentYear: new Date().getFullYear(),
                attachments: [], 
                costoTotaleRtidf: 0.00,
                archivio: [],
                iva_percentuale: 22 // Default IVA
            },
            
            companyInfo: {
                name: "ACG CLIMA SERVICE S.R.L.",
                legalAddress: "Via Duccio Galimberti 47 – 15121 – Alessandria (AL)",
                operativeAddress: "Via Zanardi Bonfiglio 68 – 27058 – Voghera (PV)",
                vatNumber: "02735970069",
                sdiCode: "SUBM70N",
                rea: "AL – 311785",
                phone: "0383/640606",
                email: "info@acgclimaservice.com",
                pec: "posta@pec.acgclimaservice.it"
            },

            technicians: ["Albanesi Gianluca", "Tosca Federico", "Troise Antonio", "Piparo Marco", "Dellafiore Lorenzo", "Dellafiore Victor", "Aime David"],
            
            elements: {
                // Main UI
                menuItems: document.querySelectorAll('.menu-item'),
                sections: document.querySelectorAll('.section-content'),
                statusLabel: document.getElementById('status-label'),
                
                // Anagrafica
                pdfTicketInput: document.getElementById('pdf-ticket-input'),
                ticketDropzone: document.getElementById('ticket-dropzone'),
                ticketDropzoneLabel: document.getElementById('ticket-dropzone-label'),
                clearTicketBtn: document.getElementById('clear-ticket-btn'),
                notes: document.getElementById('note'),
                diagnoseBtn: document.getElementById('diagnose-btn'),

                // Intervention
                generateRtiBtn: document.getElementById('generate-rti-btn'),
                numeroRti: document.getElementById('numero_rti'),
                dataIntervento: document.getElementById('data_intervento'),
                tecnicoAnagraficaSelect: document.getElementById('tecnico_anagrafica'),
                tecnicoInterventoSelect: document.getElementById('tecnico_intervento'),
                costoTotaleRtidf: document.getElementById('costo_totale_rtidf'),
                interventoEffettuato: document.getElementById('intervento_effettuato'),
                generateDescBtn: document.getElementById('generate-desc-btn'),
                
                // MPLS
                isGuazzottiCheckbox: document.getElementById('is-guazzotti'),
                recalculateBtn: document.getElementById('recalculate-btn'),
                addMaterialBtn: document.getElementById('add-material-btn'),
                materialiTableBody: document.querySelector('#materiali-table tbody'),
                pdfMaterialInput: document.getElementById('pdf-material-input'),
                materialDropzone: document.getElementById('material-dropzone'),
                materialDropzoneLabel: document.getElementById('material-dropzone-label'),
                numeroMpls: document.getElementById('numero_mpls'),
                mplsDataIntervento: document.getElementById('mpls_data_intervento'),
                oreManodopera: document.getElementById('ore_manodopera'),
                sovrapprezzo: document.getElementById('sovrapprezzo'),
                ivaSelect: document.getElementById('iva-select'),
                summaryIvaLabel: document.getElementById('summary-iva_percentuale_label'),

                // Finalize
                generatePdfBtns: document.querySelectorAll('.generate-pdf-btn'),
                generateHtmlBtns: document.querySelectorAll('.generate-html-btn'),
                emailTicketBtn: document.getElementById('email-ticket-btn'), 
                attachmentInput: document.getElementById('attachment-input'),
                attachmentDropzone: document.getElementById('attachment-dropzone'),
                clearAttachmentsBtn: document.getElementById('clear-attachments-btn'),
                attachmentsList: document.getElementById('attachments-list'),
                includeAttachments: document.getElementById('include-attachments'),
                includeSignature: document.getElementById('include-signature'),
                exportProjectBtn: document.getElementById('export-project-btn'),
                importProjectInput: document.getElementById('import-project-input'),
                pdfTemplateSelect: document.getElementById('pdf-template-select'),
                costoTotaleRtidfFinalize: document.getElementById('costo_totale_rtidf_finalize'),

                // Archivio
                archivioSearch: document.getElementById('archivio-search'),
                clearArchiveBtn: document.getElementById('clear-archive-btn'),
                archivioList: document.getElementById('archivio-list'),
                archivioFilterType: document.getElementById('archivio-filter-type'),

                // Modals & Loaders
                modalContainer: document.getElementById('modal-container'),
                modal: document.getElementById('modal'),
                modalTitle: document.getElementById('modal-title'),
                modalMessage: document.getElementById('modal-message'),
                modalClose: document.getElementById('modal-close'),
                modalActionBtn: document.getElementById('modal-action-btn'), 
                loaderContainer: document.getElementById('loader-container'),

                // Status Overlay
                statusOverlay: document.getElementById('status-overlay'),
                statusText: document.getElementById('status-text')
            },

            init() {
                this.checkBackendStatus();
                this.populateTechniciansDropdown();
                this.bindEvents();
                this.generateNextRTI();
                this.loadArchivio();
                this.updateUI();
                this.setCurrentDate(); 
                this.setupDropzones();
            },
            
            setupDropzones() {
                const setup = (dropzone, input) => {
                    dropzone.addEventListener('click', (e) => {
                        if (e.target.tagName.toLowerCase() !== 'label' && e.target.parentElement.tagName.toLowerCase() !== 'label') {
                            input.click();
                        }
                    });
                    
                    dropzone.addEventListener('dragenter', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
                    dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
                    dropzone.addEventListener('dragleave', e => { e.preventDefault(); dropzone.classList.remove('dragover'); });
                    dropzone.addEventListener('drop', e => {
                        e.preventDefault();
                        dropzone.classList.remove('dragover');
                        const files = e.dataTransfer.files;
                        if(files.length > 0) {
                            input.files = files;
                            input.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    });
                };
                
                setup(this.elements.ticketDropzone, this.elements.pdfTicketInput);
                setup(this.elements.materialDropzone, this.elements.pdfMaterialInput);
                setup(this.elements.attachmentDropzone, this.elements.attachmentInput);
            },

            checkBackendStatus() {
                const maxWaitTime = 180000;
                const checkInterval = 2000;
                let intervalId;

                const timeoutId = setTimeout(() => {
                    clearInterval(intervalId);
                    this.elements.statusText.textContent = 'Errore: Backend non raggiungibile.';
                    this.elements.statusOverlay.querySelector('.loader').style.display = 'none';
                    this.elements.statusOverlay.classList.add('hidden');
                }, maxWaitTime);

                intervalId = setInterval(async () => {
                    try {
                        const response = await fetch('/api/status');
                        if (response.ok) {
                            clearInterval(intervalId);
                            clearTimeout(timeoutId);
                            this.elements.statusOverlay.style.opacity = '0';
                            setTimeout(() => this.elements.statusOverlay.classList.add('hidden'), 500);
                            this.elements.pdfTicketInput.disabled = false;
                            this.elements.pdfMaterialInput.disabled = false;
                            this.elements.ticketDropzoneLabel.innerHTML = 'Caricamento abilitato. <br>Trascina qui il file PDF del ticket o fai clic per selezionarlo.';
                            this.elements.ticketDropzoneLabel.classList.replace('text-red-500', 'text-green-500');
                            this.elements.materialDropzoneLabel.innerHTML = 'Caricamento abilitato. <br>Trascina qui il PDF dei materiali o fai clic per selezionarlo.';
                            this.elements.materialDropzoneLabel.classList.replace('text-red-500', 'text-green-500');
                        }
                    } catch (error) {
                        console.log("Backend non ancora pronto, nuovo tentativo tra 2s...");
                    }
                }, checkInterval);
            },
            
            populateTechniciansDropdown() {
                this.technicians.forEach(tech => {
                    this.elements.tecnicoAnagraficaSelect.add(new Option(tech, tech));
                    this.elements.tecnicoInterventoSelect.add(new Option(tech, tech));
                });
            },

            setCurrentDate() {
                const today = new Date().toISOString().split('T')[0];
                if (!this.elements.dataIntervento.value) {
                    this.elements.dataIntervento.value = today;
                    this.syncMplsData();
                }
            },

            bindEvents() {
                this.elements.menuItems.forEach(item => item.addEventListener('click', () => this.showSection(item.dataset.section)));
                this.elements.pdfTicketInput.addEventListener('change', e => this.handlePdfUpload(e, 'ticket'));
                this.elements.pdfMaterialInput.addEventListener('change', e => this.handlePdfUpload(e, 'materiali'));
                this.elements.attachmentInput.addEventListener('change', e => this.handleAttachmentUpload(e));
                
                this.elements.clearTicketBtn.addEventListener('click', () => this.clearTicket());
                this.elements.clearAttachmentsBtn.addEventListener('click', () => this.clearAttachments());

                this.elements.isGuazzottiCheckbox.addEventListener('change', () => {
                    this.state.isGuazzotti = this.elements.isGuazzottiCheckbox.checked;
                    this.aggiornaCalcoli();
                });

                document.querySelectorAll('[data-sync]').forEach(el => el.addEventListener('input', () => this.syncMplsData()));

                this.elements.recalculateBtn.addEventListener('click', () => this.aggiornaCalcoli());
                this.elements.addMaterialBtn.addEventListener('click', () => this.addMaterial());
                
                this.elements.generatePdfBtns.forEach(btn => btn.addEventListener('click', () => this.generaPdf(btn.dataset.pdfType)));
                this.elements.generateHtmlBtns.forEach(btn => btn.addEventListener('click', () => this.generaHtml(btn.dataset.htmlType)));
                this.elements.emailTicketBtn.addEventListener('click', () => this.inviaChiusuraTicket()); 
                this.elements.exportProjectBtn.addEventListener('click', () => this.exportProjectJson());
                this.elements.importProjectInput.addEventListener('change', e => this.handleJsonUpload(e));
                
                this.elements.modalClose.addEventListener('click', () => this.hideModal());
                this.elements.modalActionBtn.addEventListener('click', () => { if (this.elements.modalActionBtn.onclick) this.elements.modalActionBtn.onclick(); });

                this.elements.generateRtiBtn.addEventListener('click', () => this.generateNextRTI());
                
                [this.elements.oreManodopera, this.elements.sovrapprezzo, this.elements.ivaSelect].forEach(el => {
                    el.addEventListener('input', () => this.aggiornaCalcoli());
                });
                
                this.elements.diagnoseBtn.addEventListener('click', () => this.handleDiagnose());
                this.elements.generateDescBtn.addEventListener('click', () => this.handleGenerateDescription());
                
                this.elements.archivioSearch.addEventListener('input', () => this.renderArchivio());
                this.elements.archivioFilterType.addEventListener('change', () => this.renderArchivio());
                this.elements.clearArchiveBtn.addEventListener('click', () => this.clearArchivio());
            },

            
async callGeminiApi(prompt) {
                this.showLoader();
                try {
                    const res = await fetch('/api/ai/gemini', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ prompt })
                    });
                    if (!res.ok) {
                        let err = '';
                        try { err = (await res.json()).error || ''; } catch {}
                        throw new Error(err || 'Errore sconosciuto');
                    }
                    const { text } = await res.json();
                    return text;
                } catch (error) {
                    console.error("Dettagli errore chiamata AI:", error);
                    this.showModal("Errore Chiamata AI", `Impossibile completare la richiesta: ${error.message}`);
                    return null;
                } finally {
                    this.hideLoader();
                }
            }
,
            
            async handleDiagnose() {
                const faultDescription = this.elements.notes.value.trim();
                if (!faultDescription) {
                    this.showModal("Input Mancante", "Per favore, inserisci una descrizione del guasto nel campo 'Note'.");
                    return;
                }
                const prompt = `Sei un tecnico di climatizzazione esperto. Un cliente ha segnalato: "${faultDescription}". Fornisci un'analisi tecnica in Markdown con possibili cause e primi passi diagnostici.`;
                const aiResponse = await this.callGeminiApi(prompt);
                if (aiResponse) {
                    const formattedHtml = aiResponse
                        .replace(/### (.*)/g, '<h3 class="text-lg font-bold mt-4 mb-2">$1</h3>')
                        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
                        .replace(/^- (.*)/gm, '<li class="ml-5 list-disc">$1</li>')
                        .replace(/^(\d+)\. (.*)/gm, '<li class="ml-5 list-decimal">$1. $2</li>')
                        .replace(/\n/g, '<br>');
                    this.showModal("✨ Suggerimento Diagnosi AI", formattedHtml);
                }
            },

            async handleGenerateDescription() {
                const keywords = this.elements.interventoEffettuato.value.trim();
                if (!keywords) {
                    this.showModal("Input Mancante", "Per favore, inserisci alcune parole chiave sull'intervento effettuato.");
                    return;
                }
                const prompt = `Sei un assistente per la compilazione di rapporti tecnici. Espandi le seguenti note: "${keywords}" in una descrizione formale e completa per un "Rapporto Tecnico di Intervento" ufficiale.`;
                const aiResponse = await this.callGeminiApi(prompt);
                if (aiResponse) {
                    this.elements.interventoEffettuato.value = aiResponse;
                    this.showModal("Descrizione Generata", "La descrizione dell'intervento è stata compilata con successo dall'AI.");
                }
            },

            collectAllProjectData() {
                document.querySelectorAll('[data-sync]').forEach(el => this.state.ticket[el.dataset.sync] = el.value);
                this.state.mpls.ore_manodopera = parseFloat(this.elements.oreManodopera.value) || 0;
                this.state.mpls.sovrapprezzo = parseFloat(this.elements.sovrapprezzo.value) || 0;
                this.state.isGuazzotti = this.elements.isGuazzottiCheckbox.checked;
                this.state.iva_percentuale = parseInt(this.elements.ivaSelect.value, 10);
            },

            exportProjectJson() {
                this.collectAllProjectData();
                const clientName = (this.state.ticket.cliente || 'Progetto').replace(/[^a-zA-Z0-9\s]/g, '').trim().replace(/\s+/g, '_');
                const rtiNumber = (this.state.ticket.numero_rti || 'SenzaNumero').replace(/[^a-zA-Z0-9]/g, '');
                const filename = `ACG_Progetto_${clientName}_${rtiNumber}_${new Date().toISOString().split('T')[0]}.json`;
                try {
                    download(JSON.stringify(this.state, null, 2), filename, "application/json");
                    this.showModal("Esportazione Completata", `Progetto salvato come "${filename}".`);
                } catch (error) {
                    this.showModal("Errore Esportazione", "Impossibile salvare il progetto.");
                }
            },

            handleJsonUpload(event) {
                const file = event.target.files[0];
                if (!file) return;
                this.showLoader();
                const reader = new FileReader();
                reader.onload = e => {
                    try {
                        const importedState = JSON.parse(e.target.result);
                        Object.assign(this.state, {
                            ticket: {},
                            mpls: { ore_manodopera: 0, sovrapprezzo: 0 },
                            materiali: [],
                            attachments: [],
                            risultatiCalcolo: {},
                            ...importedState,
                            archivio: this.state.archivio // Preserve existing archive
                        });
                        this.updateUI();
                        this.showModal("Importazione Completata", "Progetto caricato.");
                    } catch (error) {
                        this.showModal("Errore Importazione", `File JSON non valido o corrotto. ${error.message}`);
                    } finally {
                        this.hideLoader();
                        event.target.value = '';
                    }
                };
                reader.readAsText(file);
            },
            
            handleAttachmentUpload(event) {
                Array.from(event.target.files).forEach(file => {
                    if (file.size > 10 * 1024 * 1024) {
                        this.showModal("File Troppo Grande", `Il file ${file.name} supera i 10MB.`);
                        return;
                    }
                    if (!file.type.startsWith('image/')) {
                        this.showModal("File non supportato", `Il file ${file.name} non è un'immagine. Sono ammessi solo file JPG e PNG.`);
                        return;
                    }
                    const reader = new FileReader();
                    reader.onload = e => {
                        this.state.attachments.push({ id: Date.now() + Math.random(), name: file.name, type: file.type, size: file.size, data: e.target.result, isImage: true });
                        this.updateAttachmentsList();
                    };
                    reader.readAsDataURL(file);
                });
                event.target.value = '';
            },

            updateAttachmentsList() {
                this.elements.attachmentsList.innerHTML = '';
                this.state.attachments.forEach(att => {
                    const div = document.createElement('div');
                    div.className = 'attachment-item';
                    div.innerHTML = `
                        <div class="flex items-center space-x-3 flex-1 overflow-hidden">
                            ${att.isImage ? `<img src="${att.data}" alt="${att.name}" class="attachment-preview shrink-0">` : `<span class="text-2xl shrink-0">📄</span>`}
                            <div class="truncate"><p class="font-medium text-sm truncate">${att.name}</p><p class="text-xs text-gray-500">${this.formatFileSize(att.size)}</p></div>
                        </div>
                        <button onclick="app.removeAttachment(${att.id})" class="text-red-500 hover:text-red-700 p-2 shrink-0">🗑️</button>`;
                    this.elements.attachmentsList.appendChild(div);
                });
            },

            removeAttachment(id) {
                this.state.attachments = this.state.attachments.filter(att => att.id !== id);
                this.updateAttachmentsList();
            },

            clearAttachments() {
                 this.showModal("Conferma Rimozione", "Sei sicuro di voler rimuovere tutti gli allegati?", "Rimuovi Tutti", () => {
                    this.state.attachments = [];
                    this.updateAttachmentsList();
                    this.hideModal();
                });
            },

            formatFileSize: bytes => (bytes === 0 ? '0 Bytes' : `${parseFloat((bytes / Math.pow(1024, Math.floor(Math.log(bytes) / Math.log(1024)))).toFixed(2))} ${['Bytes', 'KB', 'MB', 'GB'][Math.floor(Math.log(bytes) / Math.log(1024))]}`),
            formatDateItalian: dateString => dateString ? new Date(dateString).toLocaleDateString('it-IT') : '',
            parseDateItalian(dateString) {
                if (!dateString || /^\d{4}-\d{2}-\d{2}$/.test(dateString)) return dateString;
                const parts = dateString.split('/');
                return parts.length === 3 ? `${parts[2]}-${parts[1].padStart(2, '0')}-${parts[0].padStart(2, '0')}` : dateString;
            },

            
generateNextRTI() {
                const year = new Date().getFullYear();
                this.state.currentYear = year;
                const key = `acgRtiCounter_${year}`;
                try {
                    this.state.rtiCounter = parseInt(localStorage.getItem(key) || '1', 10);
                } catch(e) { this.state.rtiCounter = 1; }
                this.elements.numeroRti.value = `RTI-${year}-${String(this.state.rtiCounter).padStart(3, '0')}`;
                this.state.rtiCounter++;
                try { localStorage.setItem(key, String(this.state.rtiCounter)); } catch(e) {}
                this.syncMplsData();
            }
,
            
            
syncMplsData() {
                document.querySelectorAll('[data-sync]').forEach(el => this.state.ticket[el.dataset.sync] = el.value);
                document.getElementById('mpls_cliente').value = this.state.ticket.cliente || '';
                document.getElementById('mpls_condominio').value = this.state.ticket.condominio || '';
                document.getElementById('mpls_indirizzo').value = this.state.ticket.indirizzo || '';
                document.getElementById('mpls_data_intervento').value = this.state.ticket.data_intervento || this.state.ticket.data_intervento_programmato || '';
                document.getElementById('mpls_tecnico').value = this.state.ticket.tecnico_intervento || '';
                this.elements.numeroMpls.value = (this.elements.numeroRti.value || '').replace('RTI-', 'MPLS-');
            }
,
            
            showSection(sectionId) {
                this.elements.sections.forEach(s => s.classList.add('hidden'));
                document.getElementById(sectionId).classList.remove('hidden');
                this.elements.menuItems.forEach(item => {
                    const isSelected = item.dataset.section === sectionId;
                    item.classList.toggle('bg-[#007AFF]', isSelected);
                    item.classList.toggle('text-white', isSelected);
                    if(isSelected) this.elements.statusLabel.textContent = `📍 ${item.querySelector('span:last-child').textContent}`;
                });
                if (sectionId === 'archivio') this.renderArchivio();
            },
            
            updateUI() {
                document.querySelectorAll('[data-sync]').forEach(el => el.value = this.state.ticket[el.dataset.sync] || '');
                this.elements.oreManodopera.value = this.state.mpls.ore_manodopera || 0;
                this.elements.sovrapprezzo.value = this.state.mpls.sovrapprezzo || 0;
                this.elements.isGuazzottiCheckbox.checked = this.state.isGuazzotti;
                this.elements.ivaSelect.value = this.state.iva_percentuale || 22;
                this.updateAttachmentsList();
                this.renderArchivio();
                this.syncMplsData();
                this.aggiornaCalcoli();
            },
            
            clearTicket() {
                this.showModal("Conferma Cancellazione", "Sei sicuro di voler cancellare tutti i dati del progetto?", "Cancella Tutto", () => {
                    this.state = {
                        ...this.state, // Preserve archive and counter
                        ticket: {}, mpls: { ore_manodopera: 0, sovrapprezzo: 0 }, materiali: [], isGuazzotti: false,
                        risultatiCalcolo: {}, attachments: [], costoTotaleRtidf: 0, iva_percentuale: 22
                    };
                    document.querySelectorAll('input:not([type=button]), textarea, select').forEach(el => {
                        if (el.type === 'checkbox') el.checked = false;
                        else if(el.id !== 'numero_rti') el.value = '';
                    });
                    this.generateNextRTI(); 
                    this.updateUI();
                    this.hideModal();
                    this.showModal("Dati Cancellati", "Tutti i campi sono stati puliti.");
                });
            },
            
            async handlePdfUpload(event, type) {
                const file = event.target.files[0];
                if (!file) return;
                this.showLoader();
                try {
                    const formData = new FormData();
                    formData.append('pdf_file', file);
                    const response = await fetch(`/api/parse-${type}`, { method: 'POST', body: formData });
                    if (!response.ok) throw new Error((await response.json()).error || 'Errore di parsing.');
                    const parsedData = await response.json();
                    if (type === 'ticket') {
                        this.popolaDatiTicket(parsedData.data);
                        this.showModal("Successo", "Dati del ticket importati.");
                    } else {
                        this.state.materiali.push(...parsedData.data);
                        this.aggiornaCalcoli();
                        this.showModal("Successo", `${parsedData.data.length} materiali importati.`);
                    }
                } catch (error) {
                    this.showModal("Errore di Parsing", error.message);
                } finally {
                    this.hideLoader();
                    event.target.value = '';
                }
            },
            
            popolaDatiTicket(data) {
                Object.entries(data).forEach(([key, value]) => {
                    const el = document.getElementById(key);
                    if (el) {
                        el.value = (el.type === 'date') ? this.parseDateItalian(value) : value;
                        this.state.ticket[key] = el.value;
                    }
                });
                this.syncMplsData();
            },
            
            addMaterial() {
                const nome = document.getElementById('nome_materiale_entry').value.trim();
                const qta = parseFloat(document.getElementById('qta_materiale_entry').value);
                const prezzo = parseFloat(document.getElementById('prezzo_materiale_entry').value);
                if (!nome || isNaN(qta) || isNaN(prezzo) || qta <= 0 || prezzo < 0) {
                    this.showModal("Input non valido", "Inserisci nome, quantità e prezzo validi.");
                    return;
                }
                this.state.materiali.push({ nome, quantita: qta, prezzoAcquisto: prezzo });
                this.aggiornaCalcoli();
                ['nome_materiale_entry', 'qta_materiale_entry', 'prezzo_materiale_entry'].forEach(id => document.getElementById(id).value = '');
                document.getElementById('nome_materiale_entry').focus();
            },

            removeMaterial(index) {
                this.state.materiali.splice(index, 1);
                this.aggiornaCalcoli();
            },

            aggiornaCalcoli() {
                this.collectAllProjectData();
                this.state.risultatiCalcolo = this.calcolaTotali();
                this.elements.materialiTableBody.innerHTML = this.state.materiali.map((mat, index) => `
                    <tr class="border-b border-[#F2F2F7]">
                        <td class="p-3">${mat.nome}</td>
                        <td class="p-3 text-center">${mat.quantita.toFixed(2)}</td>
                        <td class="p-3 text-right">${this.formattaEuro(mat.prezzoAcquisto)}</td>
                        <td class="p-3 text-right">${this.formattaEuro(mat.prezzoAcquisto * mat.quantita)}</td>
                        <td class="p-3 text-center"><button onclick="app.removeMaterial(${index})" class="text-red-500 hover:text-red-700">🗑️</button></td>
                    </tr>`).join('');
                
                Object.entries(this.state.risultatiCalcolo).forEach(([key, value]) => {
                    const el = document.getElementById(`summary-${key.replace(/([A-Z])/g, "_$1").toLowerCase()}`);
                     if (el) {
                        if (key.includes('Percentuale')) el.textContent = `${(value || 0).toFixed(2).replace('.', ',')}%`;
                        else el.textContent = this.formattaEuro(value);
                    }
                });
                this.elements.summaryIvaLabel.textContent = this.state.iva_percentuale;
                const totaleIvato = this.state.risultatiCalcolo.totaleIvato || 0;
                this.elements.costoTotaleRtidf.value = totaleIvato.toFixed(2);
                this.elements.costoTotaleRtidfFinalize.value = totaleIvato.toFixed(2);
                this.state.costoTotaleRtidf = totaleIvato;
            },
            
            calcolaTotali() {
                const { ore_manodopera, sovrapprezzo } = this.state.mpls;
                const { isGuazzotti, iva_percentuale } = this.state;
                const { subtotaleMaterialiVendita } = this.state.materiali.reduce((acc, mat) => {
                    const costoAcquisto = mat.quantita * mat.prezzoAcquisto;
                    const ricarico = isGuazzotti ? 0.20 : (costoAcquisto < 100 ? 0.40 : (costoAcquisto <= 200 ? 0.35 : 0.30));
                    acc.subtotaleMaterialiVendita += costoAcquisto * (1 + ricarico);
                    return acc;
                }, { subtotaleMaterialiVendita: 0 });

                const costoOrarioVendita = isGuazzotti ? 25.0 : 40.0;
                const subtotaleManodoperaVendita = ore_manodopera * costoOrarioVendita;
                
                const costoMaterialiAcquisto = this.state.materiali.reduce((sum, mat) => sum + (mat.quantita * mat.prezzoAcquisto), 0);
                const costoGestione = isGuazzotti ? 0 : 30.0;
                const speseBrevi = (!isGuazzotti && ore_manodopera > 0 && ore_manodopera < 3) ? 30.0 : 0;
                const materialeConsumo = (!isGuazzotti && costoMaterialiAcquisto > 0) ? Math.max(10.0, costoMaterialiAcquisto * 0.03) : 0;
                const totaleCostiAccessori = costoGestione + speseBrevi + materialeConsumo + sovrapprezzo;

                const totaleGeneraleVendita = subtotaleMaterialiVendita + subtotaleManodoperaVendita + totaleCostiAccessori;
                const importoIva = totaleGeneraleVendita * (iva_percentuale / 100);
                const totaleIvato = totaleGeneraleVendita + importoIva;
                
                const costoOrarioAcquisto = 22.0;
                const costoTotaleAcquisto = costoMaterialiAcquisto + (ore_manodopera * costoOrarioAcquisto);
                
                const margineInEuro = totaleGeneraleVendita - costoTotaleAcquisto;
                const marginePercentuale = totaleGeneraleVendita > 0 ? (margineInEuro / totaleGeneraleVendita) * 100 : 0;

                return { subtotaleMaterialiVendita: this.round2(subtotaleMaterialiVendita), subtotaleManodoperaVendita: this.round2(subtotaleManodoperaVendita), costoGestione: this.round2(costoGestione), speseBrevi: this.round2(speseBrevi), materialeConsumo: this.round2(materialeConsumo), sovrapprezzo: this.round2(sovrapprezzo), totaleGeneraleVendita: this.round2(totaleGeneraleVendita), margineInEuro: this.round2(margineInEuro), marginePercentuale, importoIva: this.round2(importoIva), totaleIvato: this.round2(totaleIvato) };
            },
            
            generaPdf(pdfType) {
                this.collectAllProjectData();
                this.aggiornaCalcoli(); 
                this.showLoader();
                try {
                    const finalHtml = this.buildHtmlForPdf(pdfType);
                    if (!finalHtml) throw new Error("Generazione HTML fallita.");
                    this.addToArchivio(pdfType, finalHtml);
                    const printWindow = window.open('', '_blank');
                    printWindow.document.open();
                    printWindow.document.write(finalHtml);
                    printWindow.document.close();
                    setTimeout(() => {
                        printWindow.print();
                        this.hideLoader();
                        setTimeout(() => printWindow.close(), 1000);
                    }, 500);
                } catch (error) {
                    this.showModal("Errore Generazione PDF", `Si è verificato un errore: ${error.message}`);
                    this.hideLoader();
                }
            },
            
            generaHtml(htmlType) {
                this.collectAllProjectData();
                this.aggiornaCalcoli(); 
                this.showLoader();
                try {
                    const finalHtml = this.buildHtmlForPdf(htmlType);
                    if (!finalHtml) throw new Error("Generazione HTML fallita.");
                    this.addToArchivio(htmlType, finalHtml);
                    const clientName = (this.state.ticket.cliente || 'Cliente').replace(/[^a-zA-Z0-9]/g, '');
                    const docNumber = (this.state.ticket.numero_rti || '000').replace(/[^a-zA-Z0-9]/g, '');
                    const downloadFileName = `${htmlType}_${clientName}_${docNumber}_DEBUG.html`;
                    download(finalHtml, downloadFileName, "text/html");
                    this.showModal("Successo", `File di debug "${downloadFileName}" generato e documento archiviato.`);
                } catch (error) {
                    this.showModal("Errore Generazione HTML", error.message);
                } finally {
                    this.hideLoader();
                }
            },
            
            buildHtmlForPdf(pdfType) {
                const htmlTemplate = `
                    <!DOCTYPE html><html lang="it"><head><meta charset="UTF-8"><title>Report</title><style>
                    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');
                    body{font-family:'Roboto',sans-serif;font-size:9.5pt;color:#333;margin:0}
                    .page{padding:20px;page-break-after:always}.page:last-child{page-break-after:auto}
                    h1,h2,h3{font-weight:700;color:#2E8B57}
                    table{width:100%;border-collapse:collapse;margin-top:15px;font-size:9pt}
                    th,td{border:1px solid #ddd;padding:8px;text-align:left}
                    thead th{background-color:#2E8B57!important;color:#fff!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
                    tbody tr:nth-child(even){background-color:#f9f9f9!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
                    .section{margin-bottom:20px;page-break-inside:avoid}
                    .section-title{font-size:15pt;margin-bottom:10px;border-bottom:1px solid #2E8B57;padding-bottom:4px}
                    .total-box{background-color:#E6F5ED!important;border:1px solid #5BC87F;padding:15px;margin:20px 0;text-align:center;font-size:13pt;font-weight:700;color:#1D6B40;-webkit-print-color-adjust:exact;print-color-adjust:exact}
                    .signature-section{margin-top:50px;text-align:right;page-break-inside:avoid}
                    .signature-line{width:250px;border-top:1px solid #333;margin:0 0 5px auto}
                    figure.attachment{page-break-inside:avoid;text-align:center;margin:20px 0}
                    figure.attachment img{max-width:100%;max-height:500px;border:1px solid #ccc}
                    figure.attachment figcaption{font-size:9pt;color:#777;margin-top:5px}
                    .company-header{background-color:#2E8B57!important;padding:15px 20px;color:#fff;text-align:center;-webkit-print-color-adjust:exact;print-color-adjust:exact}
                    .company-header h1{font-size:20pt;color:#fff;margin:0}
                    .company-header p{font-size:8pt;margin:4px 0 0}
                    @media print{html,body{width:210mm;height:297mm;font-size:9pt}.page{margin:0;padding:10mm 15mm}}
                    </style></head><body><div class="page"><div class="content">{{REPORT_CONTENT}}</div></div></body></html>`;
                
                try {
                    const data = { ...this.state.ticket, ...this.state.risultatiCalcolo, ...this.state.mpls, iva_percentuale: this.state.iva_percentuale };
                    let docNumber = data.numero_rti || '';
                    let docTitle = "Report Generico";

                    switch(pdfType) {
                        case 'RTI': docTitle = "Rapporto Tecnico di Intervento (RTI)"; break;
                        case 'RTIDF': docTitle = "Report Tecnico Intervento con Corrispettivo (RTIDF)"; break;
                        case 'PREVENTIVO': docTitle = "Preventivo Lavori"; docNumber = docNumber.replace('RTI-', 'PL-'); break;
                        case 'MPLS': docTitle = "Preventivo Materiali e Lavori (MPLS)"; docNumber = docNumber.replace('RTI-', 'MPLS-'); break;
                        case 'COMPLETO': docTitle = "Report Completo (RTIDF + MPLS)"; break;
                    }

                    let reportContent = `
                        <div class="company-header"><h1>${this.companyInfo.name}</h1><p>${this.companyInfo.operativeAddress} | Tel: ${this.companyInfo.phone} | Email: ${this.companyInfo.email}</p><p>P.IVA/C.F.: ${this.companyInfo.vatNumber} | SDI: ${this.companyInfo.sdiCode}</p></div>
                        <div style="padding:10px 0;"><p style="text-align:right;font-size:9pt;color:#777">Data di compilazione: ${new Date().toLocaleDateString('it-IT')}</p>
                        <h2 style="font-size:18pt;text-align:center;margin-top:5px;margin-bottom:15px;color:#333">${docTitle}</h2>
                        <h3 style="font-size:13pt;text-align:center;margin-bottom:20px;color:#333;font-weight:700">Numero: ${docNumber}</h3>
                        <div class="section"><h2 class="section-title">Dettagli Cliente</h2><p><strong>Cliente:</strong> ${data.cliente||''}</p><p><strong>Condominio:</strong> ${data.condominio||''}</p><p><strong>Indirizzo:</strong> ${data.indirizzo||''}</p></div>`;

                    if (pdfType === 'RTI' || pdfType === 'RTIDF' || pdfType === 'COMPLETO' || pdfType === 'PREVENTIVO') {
                        reportContent += `<div class="section"><h2 class="section-title">Dettagli Intervento</h2><table><tbody>
                            <tr><td><strong>Data Intervento Previsto:</strong></td><td>${this.formatDateItalian(data.data_intervento)||''}</td></tr>
                            <tr><td><strong>Tecnico Esecutore:</strong></td><td>${data.tecnico_intervento||''}</td></tr>
                            <tr><td style="vertical-align:top"><strong>Descrizione Lavori da Eseguire:</strong></td><td>${(data.note||'').replace(/\n/g,'<br>')}</td></tr>
                        </tbody></table></div>`;
                        if ((data.intervento_effettuato||'').trim() && pdfType !== 'PREVENTIVO') {
                            reportContent += `<div class="section"><h2 class="section-title">Descrizione Intervento Effettuato</h2><p style="line-height:1.6">${(data.intervento_effettuato).replace(/\n/g,'<br>')}</p></div>`;
                        }
                    }

                    if (pdfType === 'RTIDF' || pdfType === 'COMPLETO') {
                         reportContent += `<div class="total-box">Costo Totale Intervento (IVA Inclusa): ${this.formattaEuro(data.totaleIvato)}</div>`;
                    }

                    if (pdfType === 'MPLS' || pdfType === 'COMPLETO' || pdfType === 'PREVENTIVO') {
                        const ricaricoFn = costo => this.state.isGuazzotti ? 0.20 : (costo < 100 ? 0.40 : (costo <= 200 ? 0.35 : 0.30));
                        const materialiRows = this.state.materiali.map(mat => {
                            const costoTotAcquisto = mat.prezzoAcquisto * mat.quantita;
                            const prezzoVendita = mat.prezzoAcquisto * (1 + ricaricoFn(costoTotAcquisto));
                            return `<tr><td>${mat.nome}</td><td style="text-align:center">${mat.quantita.toFixed(2)}</td><td style="text-align:right">${this.formattaEuro(prezzoVendita)}</td><td style="text-align:right">${this.formattaEuro(prezzoVendita * mat.quantita)}</td></tr>`;
                        }).join('');

                        let summaryTable;
                        let { subtotaleMaterialiVendita, subtotaleManodoperaVendita, costoGestione, speseBrevi, materialeConsumo, sovrapprezzo, totaleGeneraleVendita, importoIva, totaleIvato, margineInEuro, marginePercentuale } = data;
                        
                        if (pdfType === 'PREVENTIVO') {
                            const totaleCostiAccessori = costoGestione + speseBrevi + materialeConsumo + sovrapprezzo;
                            let manodoperaConRipartizione = subtotaleManodoperaVendita;
                            let materialiConRipartizione = subtotaleMaterialiVendita;

                            if (subtotaleManodoperaVendita > 0 && subtotaleMaterialiVendita > 0) {
                                manodoperaConRipartizione += totaleCostiAccessori / 2;
                                materialiConRipartizione += totaleCostiAccessori / 2;
                            } else if (subtotaleManodoperaVendita > 0) {
                                manodoperaConRipartizione += totaleCostiAccessori;
                            } else {
                                materialiConRipartizione += totaleCostiAccessori;
                            }

                            summaryTable = `
                                <tr><td>Subtotale Materiali:</td><td style="text-align:right;font-weight:700">${this.formattaEuro(materialiConRipartizione)}</td></tr>
                                <tr><td>Subtotale Manodopera:</td><td style="text-align:right;font-weight:700">${this.formattaEuro(manodoperaConRipartizione)}</td></tr>
                                <tr style="border-top:1.5px dashed #555"><td>Imponibile:</td><td style="text-align:right;font-weight:700">${this.formattaEuro(totaleGeneraleVendita)}</td></tr>
                                <tr><td>IVA (${data.iva_percentuale}%):</td><td style="text-align:right;font-weight:700">${this.formattaEuro(importoIva)}</td></tr>
                                <tr style="font-size:14pt;font-weight:700;color:#2E8B57;border-top:2px solid #333"><td style="padding-top:10px">TOTALE PREVENTIVO:</td><td style="text-align:right;padding-top:10px">${this.formattaEuro(totaleIvato)}</td></tr>`;
                        } else { // MPLS and COMPLETO
                            summaryTable = `
                                <tr><td>Subtotale Materiali:</td><td style="text-align:right;font-weight:700">${this.formattaEuro(subtotaleMaterialiVendita)}</td></tr>
                                <tr><td>Subtotale Manodopera:</td><td style="text-align:right;font-weight:700">${this.formattaEuro(subtotaleManodoperaVendita)}</td></tr>
                                <tr style="border-top:1px dashed #D1D1D1"><td>Costo Gestione Pratica:</td><td style="text-align:right;font-weight:700;border-top:1px dashed #D1D1D1">${this.formattaEuro(costoGestione)}</td></tr>
                                <tr><td>Spese Interventi Brevi:</td><td style="text-align:right;font-weight:700">${this.formattaEuro(speseBrevi)}</td></tr>
                                <tr><td>Materiale di Consumo:</td><td style="text-align:right;font-weight:700">${this.formattaEuro(materialeConsumo)}</td></tr>
                                <tr><td>Sovrapprezzo Generico:</td><td style="text-align:right;font-weight:700">${this.formattaEuro(sovrapprezzo)}</td></tr>
                                <tr style="border-top:1.5px dashed #555"><td>Imponibile:</td><td style="text-align:right;font-weight:700">${this.formattaEuro(totaleGeneraleVendita)}</td></tr>
                                <tr><td>IVA (${data.iva_percentuale}%):</td><td style="text-align:right;font-weight:700">${this.formattaEuro(importoIva)}</td></tr>
                                <tr style="font-size:14pt;font-weight:700;color:#2E8B57;border-top:2px solid #333"><td style="padding-top:10px">TOTALE FATTURA:</td><td style="text-align:right;padding-top:10px">${this.formattaEuro(totaleIvato)}</td></tr>
                                <tr style="border-top:1.5px dashed #555"><td style="font-weight:700;color:#1E8449">Margine Totale (€):</td><td style="text-align:right;font-weight:700;color:#1E8449">${this.formattaEuro(margineInEuro)}</td></tr>
                                <tr style="font-weight:700;color:#1E8449"><td>Margine Totale (%):</td><td style="text-align:right">${(marginePercentuale||0).toFixed(2).replace('.',',')}%</td></tr>`;
                        }
                        
                        reportContent += `<div class="section"><h2 class="section-title">Dettaglio Economico</h2><h3>Materiali e Servizi:</h3>
                            <table><thead><tr><th>Descrizione</th><th>Qtà</th><th style="text-align:right">Prezzo Unitario</th><th style="text-align:right">Totale</th></tr></thead><tbody>${materialiRows}</tbody></table>
                            <h3 style="margin-top:20px">Riepilogo</h3><table style="width:50%;margin-left:auto"><tbody>${summaryTable}</tbody></table></div>`;
                    }
                    
                    if (this.elements.includeSignature.checked) {
                        reportContent += `<div class="signature-section"><div class="signature-line"></div><p style="font-size:10pt;color:#666;margin:0">Firma Cliente</p></div>`;
                    }
                    
                    if (this.elements.includeAttachments.checked && this.state.attachments.length > 0) {
                        const attachmentsContent = this.state.attachments.map(att => `<figure class="attachment"><img src="${att.data}" alt="${att.name}"><figcaption>${att.name}</figcaption></figure>`).join('');
                        reportContent += `<div class="section" style="page-break-before:always;"><h2 class="section-title">Allegati</h2>${attachmentsContent}</div>`;
                    }

                    reportContent += `</div>`;
                    return htmlTemplate.replace('{{REPORT_CONTENT}}', reportContent);
                } catch (error) {
                    console.error("Errore durante la costruzione dell'HTML: ", error);
                    this.showModal("Errore Template", `Impossibile costruire il documento: ${error.message}`);
                    return null;
                }
            },
            
            async inviaChiusuraTicket() {
                this.showLoader();
                this.collectAllProjectData();
                const numeroTicket = this.state.ticket.numero_ticket || '[NUMERO MANCANTE]';
                try {
                    const finalHtml = await this.buildHtmlForPdf('RTI');
                    if (!finalHtml) throw new Error("Impossibile generare il contenuto del report.");
                    const clientName = (this.state.ticket.cliente || 'Cliente').replace(/[^a-zA-Z0-9]/g, '');
                    const docNumber = (this.state.ticket.numero_rti || '000').replace(/[^a-zA-Z0-9]/g, '');
                    const downloadFileName = `RTI_${clientName}_${docNumber}.html`;
                    download(finalHtml, downloadFileName, "text/html");
                    const recipient = 'assistenza.tecnica@guazzottienergia.com';
                    const cc_recipient = 'ticketarchivio@inboxAC2.sendboard.com';
                    const subject = `Chiusura ticket n. ${numeroTicket}`;
                    const body = `Si invia in allegato la chiusura del ticket in oggetto.\n\nCordiali saluti`;
                    const mailtoLink = `mailto:${recipient}?cc=${cc_recipient}&subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
                    this.hideLoader();
                    this.showModal("Email Pronta", `Il file "${downloadFileName}" è stato scaricato.\nClicca 'Apri Email' per aprire il tuo programma di posta. Ricordati di allegare manualmente il file prima di inviare.`, "Apri Email", () => {
                        window.location.href = mailtoLink;
                        this.hideModal();
                    });
                } catch (error) {
                    this.hideLoader();
                    this.showModal("Errore", `Si è verificato un errore: ${error.message}`);
                }
            },
            
            saveArchivio() {
                try {
                    localStorage.setItem('acgArchivioDocumenti', JSON.stringify(this.state.archivio));
                } catch (e) {
                    this.showModal("Errore di Salvataggio", "Impossibile salvare l'archivio. Potrebbe essere pieno.");
                }
            },

            loadArchivio() {
                try {
                    const archivioSalvato = localStorage.getItem('acgArchivioDocumenti');
                    if (archivioSalvato) this.state.archivio = JSON.parse(archivioSalvato);
                } catch (e) { this.state.archivio = []; }
                this.renderArchivio();
            },

            // MODIFIED: Added 'condominioName' to the archived entry
            addToArchivio(docType, htmlContent) {
                const entry = {
                    id: Date.now(),
                    type: docType,
                    clientName: this.state.ticket.cliente || 'N/D',
                    condominioName: this.state.ticket.condominio || 'N/D',
                    rtiNumber: this.state.ticket.numero_rti || 'N/D',
                    date: new Date().toISOString(),
                    htmlContent: htmlContent
                };
                this.state.archivio.unshift(entry);
                this.saveArchivio();
            },

            // MODIFIED: Updated search logic and display format
            renderArchivio() {
                const searchTerm = this.elements.archivioSearch.value.toLowerCase();
                const typeFilter = this.elements.archivioFilterType.value;

                const filteredArchivio = this.state.archivio.filter(item => {
                    const searchTermMatch = item.clientName.toLowerCase().includes(searchTerm) || 
                                            item.rtiNumber.toLowerCase().includes(searchTerm) ||
                                            (item.condominioName && item.condominioName.toLowerCase().includes(searchTerm));
                    const typeMatch = (typeFilter === 'all') || (item.type === typeFilter);
                    return searchTermMatch && typeMatch;
                });

                if (filteredArchivio.length === 0) {
                    this.elements.archivioList.innerHTML = `<p class="text-center text-gray-500 py-8">${this.state.archivio.length > 0 ? 'Nessun documento trovato per la ricerca.' : "L'archivio è vuoto."}</p>`;
                    return;
                }

                this.elements.archivioList.innerHTML = filteredArchivio.map(item => `
                    <div class="bg-gray-50 p-4 rounded-lg border border-gray-200 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                        <div class="flex-grow">
                            <p class="font-semibold text-gray-800">
                                <span class="font-bold bg-blue-100 text-blue-800 px-2 py-1 rounded-full">${item.type}</span>
                                <span class="text-gray-500 mx-1">|</span>
                                <span>${item.rtiNumber}</span>
                                <span class="text-gray-500 mx-1">|</span>
                                <span>${new Date(item.date).toLocaleDateString('it-IT')}</span>
                            </p>
                            <p class="text-lg text-gray-900 mt-2 font-medium">${item.condominioName || 'Nessun condominio'}</p>
                            <p class="text-md text-gray-700">${item.clientName}</p>
                        </div>
                        <div class="flex space-x-2 shrink-0 w-full md:w-auto">
                            <button onclick="app.viewArchivedDocument(${item.id})" class="flex-1 md:flex-initial bg-green-500 text-white font-semibold py-2 px-4 rounded-lg hover:bg-green-600">Visualizza</button>
                            <button onclick="app.deleteArchivedDocument(${item.id})" class="flex-1 md:flex-initial bg-red-500 text-white font-semibold py-2 px-4 rounded-lg hover:bg-red-600">Elimina</button>
                        </div>
                    </div>`).join('');
            },
            
            viewArchivedDocument(id) {
                const item = this.state.archivio.find(doc => doc.id === id);
                if (item) {
                    const printWindow = window.open('', '_blank');
                    printWindow.document.write(item.htmlContent);
                    printWindow.document.close();
                } else { this.showModal("Errore", "Documento non trovato."); }
            },

            deleteArchivedDocument(id) {
                this.showModal("Conferma Eliminazione", "Sei sicuro di voler eliminare questo documento dall'archivio?", "Elimina", () => {
                    this.state.archivio = this.state.archivio.filter(item => item.id !== id);
                    this.saveArchivio();
                    this.renderArchivio();
                    this.hideModal();
                });
            },

            clearArchivio() {
                this.showModal("Conferma Svuota Archivio", "Sei sicuro di voler eliminare TUTTI i documenti dall'archivio?", "Svuota Tutto", () => {
                    this.state.archivio = [];
                    this.saveArchivio();
                    this.renderArchivio();
                    this.hideModal();
                });
            },

            round2: x => Math.round((Number(x) + Number.EPSILON) * 100) / 100,
            formattaEuro: v => new Intl.NumberFormat('it-IT', { style:'currency', currency:'EUR' }).format(Number(v || 0)),
            showModal(title, message, actionText = null, actionCallback = null) {
                this.elements.modalTitle.textContent = title;
                this.elements.modalMessage.innerHTML = message.replace(/\n/g, '<br>'); 
                if (actionText && actionCallback) {
                    this.elements.modalActionBtn.textContent = actionText;
                    this.elements.modalActionBtn.onclick = actionCallback;
                    this.elements.modalActionBtn.classList.remove('hidden');
                    this.elements.modalClose.textContent = "Annulla";
                } else {
                    this.elements.modalActionBtn.classList.add('hidden');
                    this.elements.modalActionBtn.onclick = null;
                    this.elements.modalClose.textContent = "OK";
                }
                this.elements.modalContainer.classList.remove('hidden');
            },
            hideModal() {
                this.elements.modalContainer.classList.add('hidden');
            },
            showLoader() { this.elements.loaderContainer.classList.remove('hidden'); },
            hideLoader() { this.elements.loaderContainer.classList.add('hidden'); }
        };

        window.app = app;
        app.init();
    });