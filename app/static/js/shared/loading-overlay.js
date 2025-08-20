// app/static/js/shared/loading-overlay.js
/**
 * Gestore overlay di caricamento condiviso.
 * Responsabilità singola: gestione stati di loading.
 */

class LoadingOverlay {
    constructor(options = {}) {
        this.options = {
            overlayId: 'loading-overlay',
            messageSelector: '.msg',
            autoDisableElements: true,
            zIndex: 9999,
            ...options
        };
        
        this.isVisible = false;
        this.disabledElements = new Set();
        
        this.initializeOverlay();
    }
    
    /**
     * Mostra overlay di caricamento
     */
    show(message = 'Elaborazione in corso…') {
        if (this.isVisible) {
            this.updateMessage(message);
            return;
        }
        
        const overlay = this.getOverlay();
        if (!overlay) {
            console.warn('Loading overlay non trovato');
            return;
        }
        
        this.updateMessage(message);
        overlay.classList.remove('hidden');
        
        if (this.options.autoDisableElements) {
            this.disableInteractiveElements();
        }
        
        this.isVisible = true;
        
        // Evento personalizzato
        window.dispatchEvent(new CustomEvent('loadingshow', { detail: { message } }));
    }
    
    /**
     * Nascondi overlay di caricamento
     */
    hide() {
        if (!this.isVisible) return;
        
        const overlay = this.getOverlay();
        if (overlay) {
            overlay.classList.add('hidden');
        }
        
        if (this.options.autoDisableElements) {
            this.enableInteractiveElements();
        }
        
        this.isVisible = false;
        
        // Evento personalizzato
        window.dispatchEvent(new CustomEvent('loadinghide'));
    }
    
    /**
     * Aggiorna messaggio di caricamento
     */
    updateMessage(message) {
        const overlay = this.getOverlay();
        if (!overlay) return;
        
        const messageElement = overlay.querySelector(this.options.messageSelector);
        if (messageElement) {
            messageElement.textContent = message;
        }
    }
    
    /**
     * Mostra loading con timeout automatico
     */
    showWithTimeout(message, timeoutMs = 30000) {
        this.show(message);
        
        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
        }
        
        this.timeoutId = setTimeout(() => {
            this.hide();
            window.errorHandler?.showWarning('Operazione interrotta per timeout');
        }, timeoutMs);
        
        return {
            cancel: () => {
                if (this.timeoutId) {
                    clearTimeout(this.timeoutId);
                    this.timeoutId = null;
                }
                this.hide();
            }
        };
    }
    
    /**
     * Wrapper per operazioni async
     */
    async wrap(asyncOperation, message = 'Elaborazione…') {
        try {
            this.show(message);
            const result = await asyncOperation();
            return result;
        } finally {
            this.hide();
        }
    }
    
    /**
     * Controlla se il loading è attivo
     */
    get visible() {
        return this.isVisible;
    }
    
    // ===== METODI PRIVATI =====
    
    initializeOverlay() {
        // Controlla se esiste già un overlay
        let overlay = document.getElementById(this.options.overlayId);
        
        if (!overlay) {
            overlay = this.createOverlay();
            document.body.appendChild(overlay);
        }
    }
    
    createOverlay() {
        const overlay = document.createElement('div');
        overlay.id = this.options.overlayId;
        overlay.className = 'hidden fixed inset-0 flex items-center justify-center bg-black/40 backdrop-blur-sm';
        overlay.style.zIndex = this.options.zIndex;
        
        overlay.innerHTML = `
            <div class="bg-white rounded-xl shadow-lg p-6 flex items-center gap-4 max-w-md">
                <div class="flex-shrink-0">
                    <div class="animate-spin rounded-full h-8 w-8 border-2 border-gray-300 border-t-indigo-600"></div>
                </div>
                <div>
                    <div class="font-semibold text-gray-800">Operazione in corso…</div>
                    <div class="msg text-sm text-gray-600">Elaborazione…</div>
                </div>
            </div>
        `;
        
        // Previeni click sulla sottostante pagina
        overlay.addEventListener('click', (e) => {
            e.stopPropagation();
        });
        
        return overlay;
    }
    
    getOverlay() {
        return document.getElementById(this.options.overlayId);
    }
    
    disableInteractiveElements() {
        this.disabledElements.clear();
        
        const elements = document.querySelectorAll('button, input, select, textarea, a[href]');
        elements.forEach(element => {
            if (!element.disabled && !element.hasAttribute('data-loading-ignore')) {
                element.disabled = true;
                this.disabledElements.add(element);
            }
        });
    }
    
    enableInteractiveElements() {
        this.disabledElements.forEach(element => {
            element.disabled = false;
        });
        this.disabledElements.clear();
    }
}

/**
 * Progress bar helper per operazioni lunghe
 */
class ProgressBar {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            showPercentage: true,
            showMessage: true,
            animated: true,
            ...options
        };
        
        this.currentValue = 0;
        this.maxValue = 100;
        
        this.initializeProgressBar();
    }
    
    show() {
        if (this.container) {
            this.container.classList.remove('hidden');
        }
    }
    
    hide() {
        if (this.container) {
            this.container.classList.add('hidden');
        }
    }
    
    update(value, message = '') {
        this.currentValue = Math.min(Math.max(value, 0), this.maxValue);
        const percentage = (this.currentValue / this.maxValue) * 100;
        
        if (this.progressBar) {
            this.progressBar.style.width = `${percentage}%`;
        }
        
        if (this.options.showPercentage && this.percentageElement) {
            this.percentageElement.textContent = `${Math.round(percentage)}%`;
        }
        
        if (this.options.showMessage && this.messageElement && message) {
            this.messageElement.textContent = message;
        }
    }
    
    reset() {
        this.update(0, '');
    }
    
    complete(message = 'Completato') {
        this.update(this.maxValue, message);
        setTimeout(() => this.hide(), 1000);
    }
    
    initializeProgressBar() {
        if (!this.container) return;
        
        this.container.innerHTML = `
            <div class="bg-gray-200 rounded-full h-4 overflow-hidden">
                <div class="progress-bar bg-indigo-600 h-full transition-all duration-300 ease-out" style="width: 0%"></div>
            </div>
            ${this.options.showPercentage ? '<div class="percentage text-sm text-gray-600 mt-1">0%</div>' : ''}
            ${this.options.showMessage ? '<div class="message text-sm text-gray-700 mt-1"></div>' : ''}
        `;
        
        this.progressBar = this.container.querySelector('.progress-bar');
        this.percentageElement = this.container.querySelector('.percentage');
        this.messageElement = this.container.querySelector('.message');
    }
}

// Esporta per uso globale
window.LoadingOverlay = LoadingOverlay;
window.ProgressBar = ProgressBar;

// Crea istanza globale di default
window.loadingOverlay = new LoadingOverlay();

// Alias per compatibilità
window.showLoading = (message) => window.loadingOverlay.show(message);
window.hideLoading = () => window.loadingOverlay.hide();

// Export per moduli ES6 se supportati
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { LoadingOverlay, ProgressBar };
}