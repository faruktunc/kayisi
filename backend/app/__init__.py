import os
from pathlib import Path

from flask import Flask, abort, jsonify, send_from_directory
from flask_cors import CORS

from app.container import Container
from app.interfaces.api.routes import BLUEPRINTS

DEFAULT_LITERATURE_PATH = Path(__file__).resolve().parent.parent / "data" / "literature.json"


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.update(LITERATURE_PATH=DEFAULT_LITERATURE_PATH, JSON_AS_ASCII=False,
                      FRONTEND_DIST=os.environ.get("FRONTEND_DIST"))
    if config:
        app.config.update(config)
    app.json.ensure_ascii = False
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.extensions["container"] = Container.build(app.config["LITERATURE_PATH"])
    for bp in BLUEPRINTS:
        app.register_blueprint(bp, url_prefix="/api")

    @app.errorhandler(ValueError)
    def bad_request(err):
        return jsonify({"error": str(err)}), 400

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    _register_frontend(app)
    return app


def _register_frontend(app: Flask) -> None:
    """Derlenmiş React uygulamasını (FRONTEND_DIST) aynı porttan servis eder.
    Geliştirmede ayarlanmaz; arayüzü Vite sunucusu verir."""
    dist = app.config.get("FRONTEND_DIST")
    if not dist or not Path(dist, "index.html").is_file():
        return
    dist = str(Path(dist).resolve())

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def frontend(path):
        if path.startswith("api/"):
            abort(404)
        if path and Path(dist, path).is_file():
            return send_from_directory(dist, path)
        return send_from_directory(dist, "index.html")
