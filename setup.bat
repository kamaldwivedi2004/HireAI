@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM  HireAI — Smart Setup Script (Windows)
REM  Run as: setup.bat
REM ─────────────────────────────────────────────────────────────────────────────
setlocal EnableDelayedExpansion

echo.
echo ╔═══════════════════════════════════════════╗
echo ║   HireAI — Smart Setup (Python 3.11)      ║
echo ╚═══════════════════════════════════════════╝
echo.

REM ── Find Python 3.11 ─────────────────────────────────────────────────────────
echo [1/7] Looking for Python 3.11...

set PY311=
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "C:\Python311\python.exe"
    "C:\Program Files\Python311\python.exe"
) do (
    if exist %%P (
        for /f "tokens=*" %%V in ('%%P -c "import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")"') do (
            if "%%V"=="3.11" set PY311=%%P
        )
    )
)

REM Try py launcher
if "%PY311%"=="" (
    py -3.11 --version >nul 2>&1
    if not errorlevel 1 (
        set PY311=py -3.11
    )
)

if "%PY311%"=="" (
    echo [ERROR] Python 3.11 not found!
    echo.
    echo Download from: https://www.python.org/downloads/release/python-3119/
    echo Make sure to check "Add Python to PATH" during install.
    pause & exit /b 1
)
echo [OK] Found Python 3.11: %PY311%

REM ── Virtual environment ───────────────────────────────────────────────────────
echo [2/7] Setting up virtual environment...
if exist venv (
    REM Check version
    venv\Scripts\python.exe -c "import sys; exit(0 if sys.version_info[:2]==(3,11) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo    Removing old venv (wrong Python version)...
        rmdir /s /q venv
    ) else (
        echo    Existing venv is Python 3.11 OK
    )
)

if not exist venv (
    %PY311% -m venv venv
    echo [OK] Created venv with Python 3.11
)
call venv\Scripts\activate.bat
echo [OK] venv active

REM ── Upgrade pip ──────────────────────────────────────────────────────────────
echo [3/7] Upgrading pip...
python -m pip install --upgrade pip -q
echo [OK] pip upgraded

REM ── PyTorch ──────────────────────────────────────────────────────────────────
echo [4/7] Installing PyTorch 2.3.1 for Python 3.11...
python -c "import torch" >nul 2>&1
if not errorlevel 1 (
    echo [OK] PyTorch already installed
) else (
    pip install torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu -q
    echo [OK] PyTorch installed
)

REM ── Other dependencies ────────────────────────────────────────────────────────
echo [5/7] Installing all other dependencies (3-5 mins)...
pip install ^
    flask==3.0.3 ^
    flask-cors==4.0.1 ^
    flask-pymongo==2.3.0 ^
    flask-caching==2.3.0 ^
    python-dotenv==1.0.1 ^
    werkzeug==3.0.3 ^
    "pymongo[srv]==4.7.3" ^
    dnspython==2.6.1 ^
    numpy==1.26.4 ^
    scikit-learn==1.5.0 ^
    xgboost==2.0.3 ^
    sentence-transformers==2.7.0 ^
    transformers==4.40.2 ^
    tokenizers==0.19.1 ^
    huggingface-hub==0.23.4 ^
    spacy==3.7.5 ^
    PyMuPDF==1.24.5 ^
    shap==0.45.1 ^
    requests==2.32.3 ^
    certifi ^
    tqdm -q
echo [OK] Dependencies installed

REM ── spaCy model ──────────────────────────────────────────────────────────────
echo [6/7] Downloading spaCy model...
python -c "import spacy; spacy.load('en_core_web_sm')" >nul 2>&1
if errorlevel 1 (
    python -m spacy download en_core_web_sm
)
echo [OK] spaCy model ready

REM ── Directories ──────────────────────────────────────────────────────────────
echo [7/7] Creating directories...
if not exist uploads mkdir uploads
if not exist ml\artifacts mkdir ml\artifacts
echo [OK] Directories ready

echo.
echo ╔═══════════════════════════════════════════════╗
echo ║  Setup complete!                              ║
echo ╚═══════════════════════════════════════════════╝
echo.
echo   Next steps:
echo   1. python seed_data.py    (test MongoDB connection)
echo   2. python app.py          (start server)
echo   3. Open http://localhost:5000
echo.
pause
