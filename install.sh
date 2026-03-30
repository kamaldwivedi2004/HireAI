#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  HireAI — Smart Install Script
#  Handles Python 3.11 / 3.12 / 3.13 / 3.14 automatically
#  Usage:  chmod +x install.sh && ./install.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   HireAI — Smart Dependency Installer        ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── Detect Python version ─────────────────────────────────────────────────────
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
PY_VER="${PY_MAJOR}.${PY_MINOR}"
echo -e "${GREEN}✓ Detected Python ${PY_VER}${NC}"

# ── Upgrade pip ───────────────────────────────────────────────────────────────
echo -e "${YELLOW}→ Upgrading pip…${NC}"
pip install --upgrade pip -q
echo -e "${GREEN}✓ pip upgraded${NC}"

# ── Install PyTorch based on Python version ───────────────────────────────────
echo ""
echo -e "${YELLOW}→ Installing PyTorch (version depends on your Python)…${NC}"

if [ "$PY_MINOR" -ge 13 ]; then
    # Python 3.13 or 3.14 — use nightly / pre-release torch
    echo -e "${YELLOW}  Python ${PY_VER} detected — installing PyTorch nightly (pre-release)${NC}"
    pip install --pre torch torchvision torchaudio \
        --index-url https://download.pytorch.org/whl/nightly/cpu -q \
        || pip install torch --pre -q \
        || {
            echo -e "${YELLOW}  ⚠ PyTorch not available for Python ${PY_VER} yet.${NC}"
            echo -e "${YELLOW}  Installing without PyTorch — app will use heuristic fallback.${NC}"
            touch .no_torch
        }
elif [ "$PY_MINOR" -eq 12 ]; then
    # Python 3.12 — stable torch 2.3+
    echo -e "${YELLOW}  Python 3.12 detected — installing stable PyTorch${NC}"
    pip install torch>=2.3.0 --index-url https://download.pytorch.org/whl/cpu -q
elif [ "$PY_MINOR" -le 11 ]; then
    # Python 3.10 or 3.11 — standard install
    echo -e "${YELLOW}  Python ${PY_VER} detected — installing stable PyTorch${NC}"
    pip install torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu -q
fi

echo -e "${GREEN}✓ PyTorch step complete${NC}"

# ── Install all other dependencies ────────────────────────────────────────────
echo ""
echo -e "${YELLOW}→ Installing all dependencies from requirements.txt…${NC}"
pip install -r requirements.txt -q
echo -e "${GREEN}✓ All dependencies installed${NC}"

# ── Install spaCy model ───────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}→ Installing spaCy English model…${NC}"
python3 -m spacy download en_core_web_sm -q || python3 -m spacy download en_core_web_sm
echo -e "${GREEN}✓ spaCy model ready${NC}"

# ── Create directories ────────────────────────────────────────────────────────
mkdir -p uploads ml/artifacts
echo -e "${GREEN}✓ Project directories created${NC}"

# ── Verify installation ───────────────────────────────────────────────────────
echo ""
echo -e "${YELLOW}→ Verifying installation…${NC}"
python3 - <<'PYCHECK'
import sys
results = []

def check(name, import_str):
    try:
        exec(import_str)
        results.append(f"  ✓ {name}")
    except ImportError as e:
        results.append(f"  ✗ {name}: {e}")

check("Flask",                "import flask")
check("PyMongo",              "import pymongo")
check("NumPy",                "import numpy")
check("scikit-learn",         "import sklearn")
check("XGBoost",              "import xgboost")
check("spaCy",                "import spacy; spacy.load('en_core_web_sm')")
check("PyMuPDF",              "import fitz")
check("Transformers",         "import transformers")
check("Sentence-Transformers","from sentence_transformers import SentenceTransformer")
check("Requests",             "import requests")

try:
    import torch
    results.append(f"  ✓ PyTorch {torch.__version__}")
except ImportError:
    results.append(f"  ⚠ PyTorch not installed (heuristic fallback active — app still works)")

for r in results:
    print(r)
PYCHECK

echo ""
echo -e "${GREEN}══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅  Installation complete!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════${NC}"
echo ""
echo -e "  Next steps:"
echo -e "  ${YELLOW}1.${NC}  python3 seed_data.py   ${BLUE}# test DB + seed jobs${NC}"
echo -e "  ${YELLOW}2.${NC}  python3 app.py          ${BLUE}# start server${NC}"
echo -e "  ${YELLOW}3.${NC}  open http://localhost:5000"
echo ""
