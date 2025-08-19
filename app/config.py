# app/config.py
import os
import secrets
from datetime import timedelta
from pathlib import Path

basedir = Path(__file__).parent.parent.absolute()

class Config:
    """Configurazione base"""
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    
    # Session
    SESSION_COOKIE_SECURE = os.environ.get('ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # Database
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = os.environ.get('ENV') == 'development'
    
    # Upload
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH_MB', '32')) * 1024 * 1024
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', str(basedir / 'instance' / 'uploads'))
    ALLOWED_EXTENSIONS = {'pdf', 'csv', 'xlsx', 'xls', 'txt', 'png', 'jpg', 'jpeg'}
    
    # API Keys
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    
    # LLM Settings
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')
    LLM_TIMEOUT_SECONDS = int(os.environ.get('LLM_TIMEOUT_SECONDS', '60'))
    LLM_MAX_RETRIES = int(os.environ.get('LLM_MAX_RETRIES', '3'))
    LLM_MIN_INTERVAL_SECONDS = float(os.environ.get('LLM_MIN_INTERVAL_SECONDS', '1.2'))
    
    # App Settings
    TEMPLATES_AUTO_RELOAD = True
    JSON_AS_ASCII = False
    JSON_SORT_KEYS = False
    
    @staticmethod
    def init_app(app):
        """Inizializzazioni custom per l'app"""
        # Crea directory necessarie
        Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
        
        # Logging
        if not app.debug:
            import logging
            from logging.handlers import RotatingFileHandler
            
            log_dir = basedir / 'logs'
            log_dir.mkdir(exist_ok=True)
            
            file_handler = RotatingFileHandler(
                log_dir / 'magazzino.log',
                maxBytes=10485760,  # 10MB
                backupCount=10
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
            app.logger.setLevel(logging.INFO)
            app.logger.info('Magazzino Pro startup')

class DevelopmentConfig(Config):
    """Configurazione sviluppo"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f"sqlite:///{basedir / 'instance' / 'magazzino_dev.db'}"
    SQLALCHEMY_ECHO = False  # True per debug query SQL

class TestingConfig(Config):
    """Configurazione test"""
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

class ProductionConfig(Config):
    """Configurazione produzione"""
    DEBUG = False
    
    # Database (preferire PostgreSQL in produzione)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        # Fix per SQLAlchemy che richiede postgresql://
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    
    # Security headers
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1 anno per static files
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Email errors to admins
        import logging
        from logging.handlers import SMTPHandler
        
        mail_handler = SMTPHandler(
            mailhost=os.environ.get('MAIL_SERVER', 'localhost'),
            fromaddr=os.environ.get('MAIL_FROM', 'error@magazzino.local'),
            toaddrs=[os.environ.get('ADMIN_EMAIL', 'admin@magazzino.local')],
            subject='Magazzino Pro - Errore Applicazione'
        )
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
