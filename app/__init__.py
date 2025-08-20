import os
from flask import Flask
#from flask_migrate import Migrate
from .extensions import db
from .models import *


def create_app():
    """Factory pattern per creare l'app Flask"""
    
    # Configurazione
    config_name = os.environ.get('FLASK_ENV', 'development')
    
    # Creazione app
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static'
    )
    
    # Configurazione database
    if config_name == 'production':
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///magazzino.db'
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///magazzino.db'
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
    app.config['UPLOAD_FOLDER'] = 'app/uploads'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    
    # Inizializza estensioni
    db.init_app(app)
    #migrate = Migrate(app, db)
    
    # Registra blueprint
    register_blueprints(app)
    
    # Crea tabelle se non esistono
    with app.app_context():
        db.create_all()
    
    return app


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
        app.register_blueprint(import_api_bp, url_prefix='/api')
        print("✅ Registrato import_api_bp")
    except ImportError as e:
        print(f"⚠️ Errore import import_api_bp: {e}")
    
    # Web Blueprints (nuovi)
    try:
        from .blueprints.web.import_web import import_web_bp
        app.register_blueprint(import_web_bp, url_prefix='/import')
        print("✅ Registrato import_web_bp")
    except ImportError as e:
        print(f"⚠️ Errore import import_web_bp: {e}")
    
    # Compatibility Redirects
    try:
        from .blueprints.compatibility import compatibility_bp
        app.register_blueprint(compatibility_bp)
        print("✅ Registrato compatibility_bp")
    except ImportError as e:
        print(f"⚠️ Errore import compatibility_bp: {e}")
    
    # === BLUEPRINT ESISTENTI ===
    try:
        from .blueprints.documents import documents_bp
        app.register_blueprint(documents_bp, url_prefix='/documents')
    except ImportError as e:
        print(f"⚠️ Errore import documents_bp: {e}")
    
    try:
        from .blueprints.inventory import inventory_bp
        app.register_blueprint(inventory_bp, url_prefix='/inventory')
    except ImportError as e:
        print(f"⚠️ Errore import inventory_bp: {e}")
    
    try:
        from .blueprints.articles import articles_bp
        app.register_blueprint(articles_bp, url_prefix='/articles')
    except ImportError as e:
        print(f"⚠️ Errore import articles_bp: {e}")
    
    try:
        from .blueprints.movements import movements_bp
        app.register_blueprint(movements_bp, url_prefix='/movements')
    except ImportError as e:
        print(f"⚠️ Errore import movements_bp: {e}")
    
    try:
        from .blueprints.settings import settings_bp
        app.register_blueprint(settings_bp, url_prefix='/settings')
    except ImportError as e:
        print(f"⚠️ Errore import settings_bp: {e}")
    
    try:
        from .blueprints.files import files_bp
        app.register_blueprint(files_bp, url_prefix='/files')
    except ImportError as e:
        print(f"⚠️ Errore import files_bp: {e}")
    
    try:
        from .blueprints.lookups import lookups_bp
        app.register_blueprint(lookups_bp, url_prefix='/lookups')
    except ImportError as e:
        print(f"⚠️ Errore import lookups_bp: {e}")
    
    try:
        from .blueprints.docops import docops_bp
        app.register_blueprint(docops_bp, url_prefix='/docops')
    except ImportError as e:
        print(f"⚠️ Errore import docops_bp: {e}")
    
    # IMPORTING - Blueprint originale (mantenuto per ora)
    try:
        from .blueprints.importing import importing_bp
        app.register_blueprint(importing_bp, url_prefix='/importing')
        print("✅ Registrato importing_bp (legacy)")
    except ImportError as e:
        print(f"⚠️ Errore import importing_bp: {e}")


# Per compatibilità con script esterni
def create_app_for_cli():
    """Crea app per CLI commands"""
    return create_app()
