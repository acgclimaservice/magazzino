# app/__init__.py
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Carica variabili ambiente
load_dotenv()

# Import extensions
from .extensions import db
from .config import config

def create_app(config_name=None):
    """Application factory pattern"""
    
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
    
    # Registra blueprints
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
    
    return app

def init_extensions(app):
    """Inizializza estensioni Flask"""
    db.init_app(app)
    
    # Migrate (opzionale)
    try:
        from flask_migrate import Migrate
        migrate = Migrate()
        migrate.init_app(app, db)
    except ImportError:
        pass
    
    # CSRF Protection
    try:
        from flask_wtf.csrf import CSRFProtect
        csrf = CSRFProtect()
        csrf.init_app(app)
    except ImportError:
        pass

def register_blueprints(app):
    """Registra tutti i blueprints"""
    from .blueprints.core import core_bp
    from .blueprints.articles import articles_bp
    from .blueprints.movements import movements_bp
    from .blueprints.documents import documents_bp
    from .blueprints.inventory import inventory_bp
    from .blueprints.settings import settings_bp
    from .blueprints.importing import importing_bp
    from .blueprints.files import files_bp
    from .blueprints.lookups import lookups_bp
    from .blueprints.docops import docops_bp
    from .blueprints.redirects import redirects_bp
    
    # Redirects deve essere registrato PRIMA per compatibilità
    app.register_blueprint(redirects_bp)
    
    # Core blueprints
    app.register_blueprint(core_bp)
    app.register_blueprint(articles_bp)
    app.register_blueprint(movements_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(importing_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(lookups_bp)
    app.register_blueprint(docops_bp)
    
    # Reports (se disponibile)
    try:
        from .blueprints.reports import reports_bp
        app.register_blueprint(reports_bp)
    except ImportError:
        app.logger.info("Reports blueprint not found, skipping")

def register_error_handlers(app):
    """Registra gestori errori personalizzati"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith('/api/'):
            return jsonify(ok=False, error='Not found', path=request.path), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f'Internal error: {error}')
        if request.path.startswith('/api/'):
            return jsonify(ok=False, error='Internal server error'), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        if request.path.startswith('/api/'):
            return jsonify(ok=False, error='Forbidden'), 403
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.error(f'Unhandled exception: {error}', exc_info=True)
        db.session.rollback()
        if app.debug:
            raise error
        if request.path.startswith('/api/'):
            return jsonify(ok=False, error='An unexpected error occurred'), 500
        return render_template('errors/500.html'), 500

def register_context_processors(app):
    """Registra context processors per i template"""
    
    @app.context_processor
    def inject_config():
        """Inietta configurazione nei template"""
        return {
            'APP_CONFIG': app.config,
            'APP_VERSION': '1.3.1',  # Incrementato per le migliorie
            'APP_NAME': 'Magazzino Pro'
        }
    
    @app.context_processor
    def utility_processor():
        """Funzioni utility per i template"""
        from .utils import unify_um
        
        def endpoint_exists(name: str) -> bool:
            try:
                return name in app.view_functions
            except Exception:
                return False
        
        def safe_url(name: str, fallback: str = "#", **values):
            from flask import url_for
            try:
                if name in app.view_functions:
                    return url_for(name, **values)
            except Exception:
                pass
            return fallback
        
        def format_currency(value):
            """Formatta valori monetari"""
            try:
                return f"€ {float(value or 0):.2f}"
            except:
                return "€ 0.00"
        
        def format_quantity(value):
            """Formatta quantità"""
            try:
                val = float(value or 0)
                if val == int(val):
                    return str(int(val))
                return f"{val:.3f}".rstrip('0').rstrip('.')
            except:
                return "0"
        
        return dict(
            endpoint_exists=endpoint_exists,
            safe_url=safe_url,
            format_currency=format_currency,
            format_quantity=format_quantity,
            unify_um=unify_um
        )

def register_cli_commands(app):
    """Registra comandi CLI personalizzati"""
    try:
        from .cli import register_cli
        register_cli(app)
    except ImportError:
        pass
    
    @app.cli.command()
    def init_db():
        """Inizializza il database"""
        db.create_all()
        print("Database inizializzato!")
    
    @app.cli.command()
    def seed_db():
        """Popola il database con dati di esempio"""
        from .models import Magazzino, Mastrino, Partner
        
        # Magazzini default
        if not Magazzino.query.first():
            magazzini = [
                Magazzino(codice='MAG1', nome='Magazzino Principale'),
                Magazzino(codice='FUR1', nome='Furgone 1'),
                Magazzino(codice='DEP1', nome='Deposito Esterno')
            ]
            db.session.add_all(magazzini)
        
        # Mastrini default
        if not Mastrino.query.first():
            mastrini = [
                Mastrino(codice='0590001003', descrizione='ACQUISTO MATERIALE DI CONSUMO', tipo='ACQUISTO'),
                Mastrino(codice='0490001003', descrizione='RICAVI PER VENDITA MATERIALE', tipo='RICAVO'),
                Mastrino(codice='0475002000', descrizione='RICAVI MANUTENZIONE ORDINARIA', tipo='RICAVO')
            ]
            db.session.add_all(mastrini)
        
        # Partner esempio
        if not Partner.query.first():
            partners = [
                Partner(nome='Fornitore Test Srl', tipo='Fornitore'),
                Partner(nome='Cliente Esempio Spa', tipo='Cliente')
            ]
            db.session.add_all(partners)
        
        db.session.commit()
        print("Database popolato con dati di esempio!")

def setup_logging(app):
    """Configura il sistema di logging"""
    if not app.debug and not app.testing:
        # File logging
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler(
            'logs/magazzino.log',
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Magazzino Pro startup')

def setup_security_headers(app):
    """Aggiunge security headers alle risposte"""
    
    @app.after_request
    def set_security_headers(response):
        # Solo per risposte HTML
        if response.content_type and 'text/html' in response.content_type:
            # Content Security Policy base
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self';"
            )
            
            # Altri security headers
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response
