@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM  HireAI — One-click startup script (Windows)
REM  Double-click this file OR run from Command Prompt
REM ─────────────────────────────────────────────────────────────────────────────

echo.
echo ╔══════════════════════════════════════╗
echo ║     HireAI — Starting Up             ║
echo ╚══════════════════════════════════════╝
echo.

REM Check Python
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERROR] Python not found. Install from https://python.org
    pause & exit /b 1
)
echo [OK] Python found

REM Create virtual environment
IF NOT EXIST "venv" (
    echo [->] Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
echo [OK] Virtual environment active

REM Install dependencies
echo [->] Installing dependencies (first run takes 3-5 mins)...
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo [OK] Dependencies installed

REM spaCy model
python -c "import spacy; spacy.load('en_core_web_sm')" >nul 2>&1
IF ERRORLEVEL 1 (
    echo [->] Downloading spaCy English model...
    python -m spacy download en_core_web_sm
)
echo [OK] spaCy model ready

REM Directories
IF NOT EXIST "uploads" mkdir uploads
IF NOT EXIST "ml\artifacts" mkdir ml\artifacts
echo [OK] Directories ready

echo.
echo ══════════════════════════════════════════
echo   HireAI running at http://localhost:5000
echo   Press Ctrl+C to stop
echo ══════════════════════════════════════════
echo.

python app.py
pause
