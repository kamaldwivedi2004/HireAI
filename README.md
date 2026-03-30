# HireAI — Intelligent Resume Screening Platform

> AI-powered hiring platform built with Flask + MongoDB Atlas + Google Gemini 2.0 Flash

## Features
- ⚡ **AI Resume Screener** — instant ATS score, match %, skill gaps (Gemini powered)
- 🏢 **Recruiter Portal** — post jobs, screen applicants, manage hiring pipeline
- 👤 **Job Seeker Portal** — browse jobs, apply, track application stages
- 📊 **Admin Dashboard** — full candidate pipeline with SHAP explanations
- ⚖️ **Bias Audit** — EEOC 4/5 disparate impact analysis

## Tech Stack
- **Backend**: Flask 3.0, Python 3.11
- **Database**: MongoDB Atlas
- **AI**: Google Gemini 2.0 Flash
- **ML**: PyTorch, XGBoost, Sentence-Transformers, spaCy

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/hireai.git
cd hireai
```

### 2. Create virtual environment
```bash
/usr/local/bin/python3.11 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu
pip install flask==3.0.3 flask-cors flask-pymongo flask-caching python-dotenv werkzeug "pymongo[srv]==4.7.3" dnspython numpy==1.26.4 scikit-learn==1.5.0 xgboost "sentence-transformers==2.7.0" "transformers==4.40.2" "tokenizers==0.19.1" "huggingface-hub==0.23.4" "spacy==3.7.5" "PyMuPDF==1.24.5" requests certifi tqdm scipy pandas cloudpickle
pip install shap==0.42.1 --no-deps
python -m spacy download en_core_web_sm
```

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env with your MongoDB URI and Gemini API key
```

### 5. Run
```bash
python app.py
```

Open `http://localhost:5003`

## Pages
| URL | Description |
|-----|-------------|
| `/` | Landing page |
| `/signup` | Register as Recruiter or Job Seeker |
| `/login` | Login |
| `/recruiter` | Recruiter dashboard |
| `/jobseeker` | Job Seeker dashboard |
| `/screener` | Free AI resume screener |
| `/dashboard` | Admin panel |

## Screenshots
*(Add screenshots here)*

## License
MIT
