"""HireAI — Full Platform with Auth + Role Portals"""
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from config import Config
from extensions import mongo, cache, init_mongo
import os

def create_app(config_class=Config):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.from_object(config_class)
    app.secret_key = app.config.get("SECRET_KEY", "hireai-secret-2024")

    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
    init_mongo(app)
    cache.init_app(app)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs("ml/artifacts", exist_ok=True)

    # Blueprints
    from api.resume     import resume_bp
    from api.jobs       import jobs_bp
    from api.candidates import candidates_bp
    from api.reports    import reports_bp
    from api.screener   import screener_bp
    from api.auth       import auth_bp
    from api.portal     import portal_bp

    app.register_blueprint(resume_bp,     url_prefix="/api/resume")
    app.register_blueprint(jobs_bp,       url_prefix="/api/jobs")
    app.register_blueprint(candidates_bp, url_prefix="/api/candidates")
    app.register_blueprint(reports_bp,    url_prefix="/api/reports")
    app.register_blueprint(screener_bp,   url_prefix="/api/screener")
    app.register_blueprint(auth_bp,       url_prefix="/api/auth")
    app.register_blueprint(portal_bp,     url_prefix="/api/portal")

    @app.route("/health")
    def health():
        try:
            mongo.db.command("ping")
            db_status = "connected"
        except Exception as e:
            db_status = f"error: {str(e)[:60]}"
        return jsonify({"status": "ok", "version": "3.0.0", "database": db_status})

    # ── Page routes ────────────────────────────────────────────────
    @app.route("/")
    def landing(): return app.send_static_file("landing.html")

    @app.route("/login")
    def login_page(): return app.send_static_file("login.html")

    @app.route("/signup")
    def signup_page(): return app.send_static_file("signup.html")

    @app.route("/screener")
    def screener_page(): return app.send_static_file("screener.html")

    @app.route("/recruiter")
    def recruiter_portal(): return app.send_static_file("recruiter.html")

    @app.route("/jobseeker")
    def jobseeker_portal(): return app.send_static_file("jobseeker.html")

    @app.route("/dashboard")
    def dashboard(): return app.send_static_file("index.html")

    @app.errorhandler(404)
    def not_found(e): return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e): return jsonify({"error": "Internal server error"}), 500

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)