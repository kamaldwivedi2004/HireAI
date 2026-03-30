import os
import ssl
import certifi
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "hireai-dev-secret")
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"

    # MongoDB Atlas — SSL fix for Mac
    _raw_uri = os.getenv("MONGO_URI", "")
    # Strip tlsAllowInvalidCertificates from URI if present (PyMongo handles it separately)
    MONGO_URI = _raw_uri.replace("&tlsAllowInvalidCertificates=true", "").replace(
        "?tlsAllowInvalidCertificates=true", ""
    )
    MONGO_DBNAME = os.getenv("MONGO_DBNAME", "hireai")

    # PyMongo kwargs — use certifi for SSL on Mac
    MONGO_TLS_CA_FILE = certifi.where()
    MONGO_CONNECT_KWARGS = {
        "tls": True,
        "tlsCAFile": certifi.where(),
        "serverSelectionTimeoutMS": 10000,
        "connectTimeoutMS": 10000,
    }

    # Cache
    CACHE_TYPE = os.getenv("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT = int(os.getenv("CACHE_DEFAULT_TIMEOUT", 300))

    # ML
    RANKING_MODEL_PATH   = os.getenv("RANKING_MODEL_PATH",   "ml/artifacts/xgb_ranker.pkl")
    PREDICTOR_MODEL_PATH = os.getenv("PREDICTOR_MODEL_PATH", "ml/artifacts/neural_predictor.pt")
    EMBEDDING_MODEL      = os.getenv("EMBEDDING_MODEL",      "sentence-transformers/all-MiniLM-L6-v2")

    # File uploads
    UPLOAD_FOLDER       = os.getenv("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH  = int(os.getenv("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))
    ALLOWED_EXTENSIONS  = {"pdf"}

    # LLM (optional)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    LLM_API_URL    = os.getenv("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
    LLM_MODEL      = os.getenv("LLM_MODEL", "gpt-4o-mini")

    # Bias thresholds
    DISPARATE_IMPACT_THRESHOLD = 0.80
    BIAS_ALERT_DELTA = 5

    # Bias thresholds
    DISPARATE_IMPACT_THRESHOLD = 0.80
    BIAS_ALERT_DELTA = 5