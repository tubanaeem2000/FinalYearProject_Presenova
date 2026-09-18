"""
Main Flask Application Hub
Role: Initialize Flask app, configure database and authentication, register blueprints, and expose health-check endpoint.

Key Features:
- SQLAlchemy ORM for database management
- JWT-Extended for secure token-based authentication
- CORS enabled for frontend integration
- Blueprint-based modular architecture
- Comprehensive error handling
"""

import sys

# Force stdout/stderr to use UTF-8 encoding to prevent UnicodeEncodeError on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from datetime import timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Global SocketIO instance
# FIX: explicit async_mode='eventlet' instead of relying on auto-detection.
# eventlet is installed (requirements.txt), so Flask-SocketIO was already
# auto-selecting it — but the gunicorn Start Command used the plain
# gthread worker class, which never calls eventlet.monkey_patch(). That
# mismatch (SocketIO internals assuming an eventlet-patched environment
# while gunicorn actually ran plain OS threads) broke WebSocket upgrades
# entirely and made emit() calls from inside event handlers unreliable in
# production, while working fine locally where `python main.py` uses
# socketio.run() (which serves via eventlet directly, no gunicorn
# involved). The gunicorn worker class must be `eventlet` in production
# (see Procfile / render.yaml) for this to actually match at runtime.
socketio = SocketIO(async_mode='eventlet')

# Import blueprints
from auth import auth_bp, register_jwt_error_handlers, signup, login, firebase_login, get_current_user, refresh
from phase_two import phase_two_bp
from phase_four import phase_four_bp
from phase_five import phase_five_bp
from phase_live import phase_live_bp, init_socketio_events
from routes.presentation_rewriter import presentation_rewriter_bp
from routes.question_generator import question_generator_bp
from routes.presentation_generator import presentation_generator_bp
from services.download_service import MAX_UPLOAD_BYTES
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def _start_pptx_purge_worker(max_age_hours: int = 24, interval_seconds: int = 3600):
    """Background daemon thread to purge generated presentations and uploads older than max_age_hours."""
    import threading
    import time
    import glob

    # Protected extensions that must NEVER be deleted by purge worker
    PROTECTED_EXTENSIONS = {'.task', '.xml', '.onnx', '.model', '.bin', '.py', '.gitkeep', '.txt_meta'}
    PURGE_EXTENSIONS = {'.pptx', '.pdf', '.docx', '.txt', '.upload', '.png', '.jpg', '.jpeg', '.json'}

    def _purge_loop():
        while True:
            try:
                now = time.time()
                cutoff = now - (max_age_hours * 3600)
                folders = [
                    'downloads',
                    'generated_presentations',
                    os.path.join('instance', 'uploads'),
                    os.path.join('instance', 'generated_presentations'),
                ]
                for folder in folders:
                    if not os.path.exists(folder):
                        continue
                    for f in glob.glob(os.path.join(folder, '**', '*'), recursive=True):
                        if os.path.isfile(f):
                            ext = os.path.splitext(f)[1].lower()
                            if ext in PROTECTED_EXTENSIONS:
                                continue
                            if ext in PURGE_EXTENSIONS and os.path.getmtime(f) < cutoff:
                                try:
                                    os.remove(f)
                                    logger.info("[CLEANUP] Purged expired file: %s", f)
                                except OSError:
                                    pass
            except Exception as ex:
                logger.warning("[CLEANUP] File purge cycle warning: %s", ex)
            time.sleep(interval_seconds)

    thread = threading.Thread(target=_purge_loop, daemon=True, name="pptx_purge_worker")
    thread.start()

def prewarm_ml_models():
    """
    Pre-warm ML models at startup in background thread to eliminate per-request model loading latency.
    Loads spaCy, SentenceTransformer, sklearn PresentationScorer, and Coach Intent Classifier into RAM.
    """
    start = time.time()
    logger.info("[PERF] Pre-warming ML models in background...")

    try:
        from nlp_module.scoring_model import load_scoring_models
        load_scoring_models()
    except Exception as e:
        logger.error(f"[PERF] Could not pre-warm scoring model: {e}", exc_info=True)

    try:
        from services.viva_rag_engine import _load_sentence_model, _load_spacy
        _load_sentence_model()
        _load_spacy()
    except Exception as e:
        logger.error(f"[PERF] Could not pre-warm SentenceTransformer/spaCy: {e}", exc_info=True)

    try:
        from services.coach_intent_engine import _get_intent_classifier
        _get_intent_classifier()
    except Exception as e:
        logger.error(f"[PERF] Could not pre-warm intent classifier: {e}", exc_info=True)

    elapsed = time.time() - start
    logger.info(f"[PERF] All ML models pre-warmed successfully in {elapsed:.3f}s")


def create_app():
    """
    Factory function to create and configure the Flask application.
    
    Initializes:
    - JWT authentication
    - CORS
    - Error handlers
    - Blueprints
    - MongoDB connection check
    - Async pre-warmed ML Models
    """
    import threading
    
    # ===== CREATE FLASK APP =====
    app = Flask(__name__)

    # Pre-warm ML models in background thread so server starts instantly.
    # FIX: measured locally, loading sentence-transformers (torch) + spaCy +
    # mediapipe + opencv + scikit-learn pushes resident memory past 500MB
    # within ~40s of boot — gunicorn logs "Listening" immediately (app
    # object returns fast), then the container gets OOM-killed once the
    # background thread finishes loading, past that point. Render's free
    # plan caps the instance at 512MB, so every request 502s once the
    # process is dead, even though the boot log looked healthy.
    # Default is OFF (opt-in) rather than on-by-default-with-opt-out:
    # this project's Render service does not reliably sync env vars from
    # render.yaml into the dashboard, so a safe default must not depend on
    # any env var being set at all. Set PREWARM_ML_MODELS=1 locally (or
    # anywhere with enough headroom) for instant-warm first requests.
    if os.getenv('PREWARM_ML_MODELS', '0').strip().lower() not in {'0', 'false', 'no', 'off'}:
        threading.Thread(target=prewarm_ml_models, daemon=True).start()
    else:
        logger.info("[PERF] ML model pre-warming disabled (PREWARM_ML_MODELS=0); models load lazily on first use.")

    # Start TTL purge worker for generated files and uploads
    _start_pptx_purge_worker()

    # ===== JWT CONFIGURATION =====
    # CRITICAL: In production, use a strong secret key from environment variables
    jwt_secret_key = os.getenv('JWT_SECRET_KEY', '').strip()
    if not jwt_secret_key:
        if os.getenv('FLASK_ENV', 'development').lower() == 'production':
            raise RuntimeError('JWT_SECRET_KEY must be configured in production.')
        jwt_secret_key = 'development-only-change-me'
    
    app.config['JWT_SECRET_KEY'] = jwt_secret_key
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
    
    # Initialize JWT with the app
    jwt = JWTManager(app)

    # ===== CORS CONFIGURATION =====
    # FIX: previously, setting CORS_ORIGINS fully REPLACED this list rather
    # than adding to it, and this project's Render service has repeatedly
    # not applied dashboard env var changes reliably (confirmed: the deployed
    # backend returned zero Access-Control-Allow-Origin headers for the live
    # Firebase Hosting origin even after CORS_ORIGINS was added on Render).
    # The actual deployed frontends must always work regardless of Render
    # dashboard state, so they're hardcoded as a baseline here and merged
    # with (not replaced by) whatever CORS_ORIGINS additionally provides.
    ALWAYS_ALLOWED_ORIGINS = [
        'https://presenova-fyp.web.app',
        'https://presenova-fyp.firebaseapp.com',
        'http://localhost:3000',
        'http://localhost:5173',
    ]
    cors_origins_env = os.getenv('CORS_ORIGINS', '').strip()
    extra_origins = []
    if cors_origins_env and cors_origins_env != '*':
        extra_origins = [o.strip() for o in cors_origins_env.split(',') if o.strip()]
    # De-dupe while preserving order (dict.fromkeys keeps first occurrence).
    parsed_origins = list(dict.fromkeys(ALWAYS_ALLOWED_ORIGINS + extra_origins))

    # AUDIT-09: Allow dynamic Vercel preview deployments either when not in production
    # OR when ALLOW_VERCEL_PREVIEWS=true is explicitly set (useful for Render+Vercel stacks).
    flask_env = os.getenv('FLASK_ENV', 'development').lower()
    allow_vercel_previews = os.getenv('ALLOW_VERCEL_PREVIEWS', 'false').lower() in ('1', 'true', 'yes', 'on')
    if flask_env != 'production' or allow_vercel_previews:
        import re
        parsed_origins.append(re.compile(r"^https://.*\.vercel\.app$"))

    CORS(
        app,
        resources={r"/*": {
            "origins": parsed_origins,
            "allow_headers": ["Content-Type", "Authorization"],
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        }},
    )

    # Flask enforces this before request handlers read multipart bodies. This
    # prevents oversized uploads from being copied to disk first.
    app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_BYTES

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify({
            'success': False,
            'message': f'File too large. Maximum allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.',
        }), 413

    # ===== SOCKET.IO CONFIGURATION =====
    socketio.init_app(app, cors_allowed_origins=parsed_origins)

    # ===== DATABASE INITIALIZATION VERIFICATION =====
    with app.app_context():
        try:
            from models import db
            if db is not None:
                logger.info("[INIT OK] Database layer initialized successfully")
        except Exception as e:
            logger.error("[INIT FAIL] Database initialization failed: %s", e)

    # ===== REGISTER JWT ERROR HANDLERS =====
    # Handles expired, invalid, and missing JWT tokens on JWTManager (ISSUE-04)
    register_jwt_error_handlers(jwt, app)

    # ===== REGISTER BLUEPRINTS =====
    # Phase 1: Authentication
    app.register_blueprint(auth_bp)
    
    # Compatibility blueprint for /auth without /api prefix
    from flask import Blueprint as BP
    auth_compat_bp = BP('auth_compat', __name__, url_prefix='/auth')
    auth_compat_bp.add_url_rule('/firebase-login', 'firebase_login_compat', firebase_login, methods=['POST', 'OPTIONS'])
    auth_compat_bp.add_url_rule('/login', 'login_compat', login, methods=['POST', 'OPTIONS'])
    auth_compat_bp.add_url_rule('/signup', 'signup_compat', signup, methods=['POST', 'OPTIONS'])
    auth_compat_bp.add_url_rule('/me', 'me_compat', get_current_user, methods=['GET', 'OPTIONS'])
    auth_compat_bp.add_url_rule('/refresh', 'refresh_compat', refresh, methods=['POST', 'OPTIONS'])
    app.register_blueprint(auth_compat_bp)
    
    # Phase 2: Document Analysis
    app.register_blueprint(phase_two_bp)
    
    # Phase 4: Speech Analysis
    app.register_blueprint(phase_four_bp)
    
    # Phase 5: AI Coach / Practice Mode
    app.register_blueprint(phase_five_bp)

    # Phase Live: Presentation Coach & Live Analyzer
    app.register_blueprint(phase_live_bp)
    init_socketio_events(socketio)

    # New Feature: AI Presentation Rewriter
    app.register_blueprint(presentation_rewriter_bp)

    # New Feature: Viva Question Generator
    app.register_blueprint(question_generator_bp)

    # New Feature: AI Presentation Generator
    app.register_blueprint(presentation_generator_bp)

    # ===== HEALTH-CHECK ENDPOINT =====
    @app.route('/', methods=['GET'])
    def health_check():
        """Health check endpoint to verify the service is running."""
        return jsonify({
            "status": "running",
            "service": "Presenova AI Presentation Platform",
            "version": "1.1.0",
            "database": "Firebase Firestore"
        }), 200

    @app.route('/api/health', methods=['GET'])
    def api_health():
        """Render.com health check endpoint."""
        return jsonify({"status": "ok"}), 200

    @app.route('/downloads/<path:filename>', methods=['GET'])
    def serve_download(filename):
        """Serve application installers (Windows, macOS, Android APK)."""
        candidate_dirs = [
            os.path.join(app.root_path, 'frontend', 'public', 'downloads'),
            os.path.join(app.root_path, 'downloads'),
        ]
        for d in candidate_dirs:
            if os.path.isfile(os.path.join(d, filename)):
                return send_from_directory(d, filename, as_attachment=True)
        return jsonify({"error": "File not found", "requested": filename}), 404

    return app


# Expose WSGI application instance for production servers (Gunicorn / Render)
app = create_app()

if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '5000'))

    # Run the Flask development server wrapped with Socket.IO
    debug = os.getenv('FLASK_DEBUG', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    socketio_kwargs = {
        'host': host,
        'port': port,
        'debug': debug,
        'use_reloader': False,
    }
    if debug:
        socketio_kwargs['allow_unsafe_werkzeug'] = True

    socketio.run(app, **socketio_kwargs)


