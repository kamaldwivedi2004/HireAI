#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  HireAI — Smart Setup Script (Mac / Linux)
#  This handles Python 3.11 enforcement + PyTorch install correctly
#
#  Usage:
#    chmod +x setup.sh
#    ./setup.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${BLUE}${BOLD}╔═══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}${BOLD}║   HireAI — Smart Setup (Python 3.11)      ║${NC}"
echo -e "${BLUE}${BOLD}╚═══════════════════════════════════════════╝${NC}"
echo ""

# ── Step 1: Find Python 3.11 ─────────────────────────────────────────────────
echo -e "${YELLOW}[1/7] Looking for Python 3.11…${NC}"

PY311=""

# Try common locations for Python 3.11 on Mac
for candidate in \
    "/usr/local/bin/python3.11" \
    "/usr/bin/python3.11" \
    "/opt/homebrew/bin/python3.11" \
    "$(which python3.11 2>/dev/null)" \
    "$(brew --prefix python@3.11 2>/dev/null)/bin/python3.11"
do
    if [ -x "$candidate" ] 2>/dev/null; then
        VER=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        if [ "$VER" = "3.11" ]; then
            PY311="$candidate"
            break
        fi
    fi
done

# From VS Code dropdown we saw: /usr/local/bin/python3.11
if [ -z "$PY311" ]; then
    # Last resort: check if python3.11 is in PATH
    if command -v python3.11 &>/dev/null; then
        PY311=$(which python3.11)
    fi
fi

if [ -z "$PY311" ]; then
    echo -e "${RED}✗ Python 3.11 not found!${NC}"
    echo ""
    echo "  Install it with Homebrew:"
    echo "    brew install python@3.11"
    echo ""
    echo "  Or download from: https://www.python.org/downloads/release/python-3119/"
    echo "  Then re-run this script."
    exit 1
fi

echo -e "${GREEN}✓ Found Python 3.11 at: $PY311${NC}"

# ── Step 2: Remove old venv if wrong Python version ──────────────────────────
echo -e "${YELLOW}[2/7] Setting up virtual environment…${NC}"

if [ -d "venv" ]; then
    EXISTING_VER=$(venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "unknown")
    if [ "$EXISTING_VER" != "3.11" ]; then
        echo -e "${YELLOW}   Removing old venv (was Python $EXISTING_VER)…${NC}"
        rm -rf venv
    else
        echo -e "${GREEN}   Existing venv is already Python 3.11 ✓${NC}"
    fi
fi

if [ ! -d "venv" ]; then
    "$PY311" -m venv venv
    echo -e "${GREEN}✓ Created new venv with Python 3.11${NC}"
fi

# Activate
source venv/bin/activate
ACTIVE_VER=$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GREEN}✓ venv active — Python $ACTIVE_VER${NC}"

# ── Step 3: Upgrade pip ───────────────────────────────────────────────────────
echo -e "${YELLOW}[3/7] Upgrading pip…${NC}"
pip install --upgrade pip -q
echo -e "${GREEN}✓ pip upgraded${NC}"

# ── Step 4: Install PyTorch FIRST (needs special handling) ───────────────────
echo -e "${YELLOW}[4/7] Installing PyTorch 2.3.1 for Python 3.11…${NC}"

# Check if already installed
if python -c "import torch; assert torch.__version__.startswith('2.')" 2>/dev/null; then
    echo -e "${GREEN}✓ PyTorch already installed${NC}"
else
    # Mac CPU-only install (works on both Intel and Apple Silicon)
    pip install torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu -q
    echo -e "${GREEN}✓ PyTorch 2.3.1 installed${NC}"
fi

# ── Step 5: Install all other requirements ────────────────────────────────────
echo -e "${YELLOW}[5/7] Installing all other dependencies…${NC}"
echo -e "   (This may take 3–5 minutes on first run)"

pip install \
    flask==3.0.3 \
    flask-cors==4.0.1 \
    flask-pymongo==2.3.0 \
    flask-caching==2.3.0 \
    python-dotenv==1.0.1 \
    werkzeug==3.0.3 \
    "pymongo[srv]==4.7.3" \
    dnspython==2.6.1 \
    numpy==1.26.4 \
    scikit-learn==1.5.0 \
    xgboost==2.0.3 \
    "sentence-transformers==2.7.0" \
    "transformers==4.40.2" \
    "tokenizers==0.19.1" \
    "huggingface-hub==0.23.4" \
    "spacy==3.7.5" \
    "PyMuPDF==1.24.5" \
    "shap==0.45.1" \
    "requests==2.32.3" \
    certifi \
    tqdm -q

echo -e "${GREEN}✓ All dependencies installed${NC}"

# ── Step 6: spaCy model ───────────────────────────────────────────────────────
echo -e "${YELLOW}[6/7] Checking spaCy English model…${NC}"

if python -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null; then
    echo -e "${GREEN}✓ spaCy en_core_web_sm already installed${NC}"
else
    echo -e "${YELLOW}   Downloading spaCy English model…${NC}"
    python -m spacy download en_core_web_sm -q
    echo -e "${GREEN}✓ spaCy model downloaded${NC}"
fi

# ── Step 7: Create directories ────────────────────────────────────────────────
echo -e "${YELLOW}[7/7] Creating required directories…${NC}"
mkdir -p uploads ml/artifacts
echo -e "${GREEN}✓ Directories ready${NC}"

# ── Verify everything ─────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}${BOLD}── Verifying installation ──────────────────────${NC}"

python -c "
import sys
checks = [
    ('Python 3.11', lambda: sys.version_info[:2] == (3,11)),
    ('Flask',        lambda: __import__('flask') and True),
    ('PyMongo',      lambda: __import__('pymongo') and True),
    ('PyTorch',      lambda: __import__('torch') and True),
    ('Transformers', lambda: __import__('transformers') and True),
    ('spaCy',        lambda: __import__('spacy').load('en_core_web_sm') and True),
    ('PyMuPDF',      lambda: __import__('fitz') and True),
    ('XGBoost',      lambda: __import__('xgboost') and True),
    ('SHAP',         lambda: __import__('shap') and True),
    ('SentenceTF',   lambda: __import__('sentence_transformers') and True),
]
all_ok = True
for name, check in checks:
    try:
        check()
        print(f'  \033[32m✓\033[0m {name}')
    except Exception as e:
        print(f'  \033[31m✗\033[0m {name}: {e}')
        all_ok = False

print()
if all_ok:
    print('  \033[32m\033[1mAll checks passed!\033[0m')
else:
    print('  \033[31mSome checks failed — see above\033[0m')
    sys.exit(1)
"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║  ✅  Setup complete!                          ║${NC}"
echo -e "${GREEN}${BOLD}╚═══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Next steps:"
echo -e ""
echo -e "  ${YELLOW}1.${NC} Test MongoDB connection:"
echo -e "     ${BOLD}python seed_data.py${NC}"
echo ""
echo -e "  ${YELLOW}2.${NC} Start the server:"
echo -e "     ${BOLD}python app.py${NC}"
echo ""
echo -e "  ${YELLOW}3.${NC} Open dashboard:"
echo -e "     ${BOLD}http://localhost:5000${NC}"
echo ""
