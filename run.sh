#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  HireAI — Start server (after setup.sh has been run)
# ─────────────────────────────────────────────────────────────────────────────

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

# Must have venv
if [ ! -d "venv" ]; then
    echo -e "${RED}✗ No venv found. Run setup.sh first:${NC}"
    echo "  chmod +x setup.sh && ./setup.sh"
    exit 1
fi

source venv/bin/activate

# Verify Python 3.11
VER=$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [ "$VER" != "3.11" ]; then
    echo -e "${RED}✗ venv is Python $VER, not 3.11. Run setup.sh to recreate it.${NC}"
    exit 1
fi

mkdir -p uploads ml/artifacts

echo ""
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}  HireAI running at http://localhost:5000${NC}"
echo -e "${GREEN}  Python $VER | Press Ctrl+C to stop${NC}"
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo ""

python app.py
