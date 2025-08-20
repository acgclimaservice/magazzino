# app/__init__.py - SEZIONE BLUEPRINT AGGIORNATA

def register_blueprints(app):
    """Registra tutti i blueprints con struttura modulare"""
    
    # === CORE BLUEPRINTS ===
    from .blueprints.core import core_bp
    from .blueprints.redirects import redirects_bp
    
    # Redirects deve essere registrato PRIMA per compatibilità
    app.register_blueprint(redirects_bp)
    app.register_blueprint(core_bp)
    
    # === NUOVI BLUEPRINT MODULARI ===
    
    # API Blueprints (nuovi)
    try:
        from .blueprints.api.import_api import import_api_bp
        app.register_blueprint(import_api_bp)
        app.logger.info("✅ Import API blueprint registrato")
    except ImportError as e:
        app.logger.warning(f"❌ Import API blueprint non trovato: {e}")
    
    # Web Blueprints (nuovi)  
    try:
        from .blueprints.web.import_web import import_web_bp
        app.register_blueprint(import_web_bp)
        app.logger.info("✅ Import Web blueprint registrato")
    except ImportError as e:
        app.logger.warning(f"❌ Import Web blueprint non trovato: {e}")
    
    # === LEGACY BLUEPRINTS (mantenuti per compatibilità) ===
    
    # NOTA: importing.py DISABILITATO durante migrazione
    # from .blueprints.importing import importing_bp
    # app.register_blueprint(importing_bp)
    
    from .blueprints.articles import articles_bp
    from .blueprints.movements import movements_bp
    from .blueprints.documents import documents_bp
    from .blueprints.inventory import inventory_bp
    from .blueprints.settings import settings_bp
    from .blueprints.files import files_bp
    from .blueprints.lookups import lookups_bp
    from .blueprints.docops import docops_bp
    
    app.register_blueprint(articles_bp)
    app.register_blueprint(movements_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(lookups_bp)
    app.register_blueprint(docops_bp)
    
    # === OPTIONAL BLUEPRINTS ===
    try:
        from .blueprints.reports import reports_bp
        app.register_blueprint(reports_bp)
        app.logger.info("✅ Reports blueprint registrato")
    except ImportError:
        app.logger.info("Reports blueprint non trovato, saltato")


def register_services(app):
    """Registra servizi come singleton nell'app context"""
    
    # Inizializza extension dict se non esiste
    if not hasattr(app, 'extensions'):
        app.extensions = {}
    
    try:
        # Import services
        from .services.pdf_service import PDFService
        from .services.parsing_service import ParsingService  
        from .services.file_service import FileService
        from .services.import_service import ImportService
        
        # Registra come singleton
        app.extensions['pdf_service'] = PDFService()
        app.extensions['parsing_service'] = ParsingService()
        app.extensions['file_service'] = FileService()
        app.extensions['import_service'] = ImportService()
        
        app.logger.info("✅ Servizi modulari registrati con successo")
        
    except ImportError as e:
        app.logger.error(f"❌ Errore registrazione servizi: {e}")
        # Non bloccare l'avvio se mancano servizi
        pass


# AGGIORNAMENTO della funzione create_app esistente

def create_app(config_name=None):
    """Application factory pattern AGGIORNATO per supporto modulare"""
    
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="templates",
        static_folder="static",
    )
    
    # Configurazione
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # Assicura che instance folder esista
    os.makedirs(app.instance_path, exist_ok=True)
    
    # Inizializza estensioni  
    init_extensions(app)
    
    # NUOVO: Registra servizi modulari
    register_services(app)
    
    # Registra blueprints (AGGIORNATO per modularità)
    register_blueprints(app)
    
    # Registra error handlers
    register_error_handlers(app)
    
    # Registra context processors
    register_context_processors(app)
    
    # Registra CLI commands
    register_cli_commands(app)
    
    # Setup logging
    setup_logging(app)
    
    # Security headers
    setup_security_headers(app)
    
    app.logger.info(f"🚀 App creata in modalità {config_name}")
    return app


# NUOVO: Helper per accesso servizi

def get_service(service_name: str):
    """
    Helper per accesso ai servizi registrati.
    
    Usage:
        from app import get_service
        import_service = get_service('import_service')
    """
    from flask import current_app
    
    if not hasattr(current_app, 'extensions'):
        raise RuntimeError("Servizi non inizializzati")
    
    service = current_app.extensions.get(service_name)
    if not service:
        raise RuntimeError(f"Servizio '{service_name}' non trovato")
    
    return service