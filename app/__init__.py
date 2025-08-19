import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
from dotenv import load_dotenv

# extensions.py deve esporre: db (ed eventualmente migrate)
from .extensions import db

def create_app():
    # Tailwind flag: True=CDN (dev), False=Local CSS (prod)
    use_cdn = os.getenv('TAILWIND_CDN', 'true').lower() in ('1','true','yes','on')

    load_dotenv()

    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="templates",
        static_folder="static",
    )

    # Config di base
    os.makedirs(app.instance_path, exist_ok=True)
    default_db_path = os.path.join(app.instance_path, "magazzino.db")
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", f"sqlite:///{default_db_path}"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=os.path.abspath(os.environ.get("UPLOAD_FOLDER", os.path.join(app.instance_path, "uploads"))),
        MAX_CONTENT_LENGTH=int(os.environ.get("MAX_CONTENT_LENGTH", 32 * 1024 * 1024)),
    )
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Init estensioni
    db.init_app(app)
    try:
        from .extensions import migrate  # opzionale
        migrate.init_app(app, db)
    except Exception:
        pass

    # Blueprints (registriamo tutto ciò che c'è nel progetto)
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

    # Importante: redirects PRIMA, per compat legacy
    app.register_blueprint(redirects_bp)
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

    # Config tailwind
    app.config['TAILWIND_CDN'] = use_cdn

    # Rende disponibile la config in Jinja
    @app.context_processor
    def _inject_config():
        return {'APP_CONFIG': app.config}



    # DEBUG: path del template effettivamente servito
    @app.get("/debug/template-path")
    def _debug_template_path():
        try:
            t = app.jinja_env.get_or_select_template("document_detail.html")
            return {"path": getattr(t, "filename", None), "searchpath": list(getattr(app.jinja_loader, "searchpath", []))}
        except Exception as e:
            try:
                return {"error": str(e)}, 500
            except Exception:
                return "500", 500
    # Helper per template: endpoint_exists/safe_url
    @app.context_processor
    def _ctx_helpers():
        def endpoint_exists(name: str) -> bool:
            try:
                return name in app.view_functions
            except Exception:
                return False
        def safe_url(name: str, fallback: str = "#", **values):
            try:
                if name in app.view_functions:
                    return url_for(name, **values)
            except Exception:
                pass
            return fallback
        return dict(endpoint_exists=endpoint_exists, safe_url=safe_url)

    # Root/fav
    @app.route("/")
    def index():
        return redirect(url_for("core.menu"))
    @app.route("/favicon.ico")
    def favicon():
        return ("", 204)

    # Error handlers → JSON se /api/*
    @app.errorhandler(404)
    def _not_found(e):
        if request.path.startswith("/api/"):
            return jsonify(ok=False, error="Not found", path=request.path), 404
        try:
            return render_template("errors/404.html"), 404
        except Exception:
            return "404 Not Found", 404
    @app.errorhandler(500)
    def _server_error(e):
        if request.path.startswith("/api/"):
            return jsonify(ok=False, error="Internal Server Error"), 500
        try:
            return render_template("errors/500.html"), 500
        except Exception:
            return "500 Internal Server Error", 500

    # Dev convenience: crea tabelle per SQLite se non usi Alembic
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///"):
        with app.app_context():
            try:
                db.create_all()
            except Exception:
                pass

    # CLI opzionale
    try:
        from .cli import register_cli
        register_cli(app)
    except Exception:
        pass

    return app