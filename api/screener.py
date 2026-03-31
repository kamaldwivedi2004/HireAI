"""
api/screener.py — Resume Screener powered by Google Gemini AI
Accurate experience detection + Gemini 2.0 Flash analysis
"""

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os, re, json, datetime

screener_bp = Blueprint("screener", __name__)

# ── Gemini API Key ─────────────────────────────────────────────────
GEMINI_API_KEY = "YOUR API KEY"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

MONTH_MAP = {
    'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
    'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12,
    'january':1,'february':2,'march':3,'april':4,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12
}


# ── Helpers ────────────────────────────────────────────────────────

def extract_text_from_pdf(path):
    try:
        import fitz
        doc = fitz.open(path)
        text = "\n".join(page.get_text("text") for page in doc)
        doc.close()
        return text.strip()
    except Exception:
        return ""


def allowed_file(f):
    return "." in f and f.rsplit(".", 1)[1].lower() == "pdf"


def compute_experience_months(text):
    """
    Month-aware experience calculator.
    Only scans the Experience section — ignores Projects and Education.
    """
    now = datetime.datetime.now()
    text_lower = text.lower()
    month_names = '|'.join(sorted(MONTH_MAP.keys(), key=len, reverse=True))

    # Find section boundaries
    exp_m  = re.search(r'\n\s*(?:experience|work experience|employment|internship)\s*\n', text_lower)
    proj_m = re.search(r'\n\s*(?:projects?|personal projects?)\s*\n', text_lower)
    edu_m  = re.search(r'\n\s*(?:education|academic)\s*\n', text_lower)
    cert_m = re.search(r'\n\s*(?:certifications?|achievements?|awards?)\s*\n', text_lower)

    exp_start = exp_m.start() if exp_m else 0
    exp_end = len(text_lower)
    for m in [proj_m, edu_m, cert_m]:
        if m and m.start() > exp_start:
            exp_end = min(exp_end, m.start())

    exp_section = text_lower[exp_start:exp_end]

    # Education years to exclude
    edu_years = set()
    if edu_m:
        for y in re.finditer(r'\b(20\d{2})\b', text_lower[edu_m.start():edu_m.start()+600]):
            edu_years.add(int(y.group(1)))

    pattern = re.compile(
        rf'({month_names})[a-z]*[\s,]+(\d{{4}})\s*[-–—to]+\s*'
        rf'(?:({month_names})[a-z]*[\s,]+)?(\d{{4}}|present|current|now|till\s*date)',
        re.IGNORECASE
    )

    segments = []
    seen = set()

    for m in pattern.finditer(exp_section):
        sm_str = m.group(1).lower()[:3]
        sy = int(m.group(2))
        em_str = (m.group(3) or '').lower()[:3]
        end_str = m.group(4).strip().lower()

        if sy in edu_years:
            continue

        sm = MONTH_MAP.get(sm_str, 6)
        if end_str in ('present', 'current', 'now') or 'till' in end_str:
            ey, em = now.year, now.month
        else:
            ey = int(end_str[:4])
            em = MONTH_MAP.get(em_str, sm) if em_str else sm

        if sy in edu_years and ey in edu_years:
            continue

        span = (ey - sy) * 12 + (em - sm)
        if span > 60:  # skip >5yr spans (likely edu)
            continue

        key = (sy, sm)
        if key not in seen and span > 0:
            seen.add(key)
            segments.append(span)

    total = sum(segments)

    if total == 0:
        for m in re.finditer(r'(\d+)\s*months?', exp_section):
            v = int(m.group(1))
            if 1 <= v <= 36:
                total = max(total, v)

    total = max(0, min(total, 360))

    if total == 0:   return 0, "Fresher"
    if total < 12:   return total, f"{total} month{'s' if total>1 else ''}"
    yrs, mos = total // 12, total % 12
    if mos == 0:     return total, f"{yrs} yr{'s' if yrs>1 else ''}"
    return total, f"{yrs} yr{'s' if yrs>1 else ''} {mos} mo"


def parse_required_experience(job_text):
    jl = job_text.lower()
    for pat in [
        r'(\d+)\s*[-–—to]+\s*(\d+)\s*years?',
        r'(\d+)\s*\+\s*years?',
        r'minimum\s+(\d+)\s*years?',
        r'at\s+least\s+(\d+)\s*years?',
        r'(\d+)\s*years?\s+(?:of\s+)?experience',
    ]:
        m = re.search(pat, jl)
        if m:
            g = [int(x) for x in m.groups() if x and x.isdigit()]
            if g:
                return g[0], g[1] if len(g) > 1 else g[0], g[0] * 12
    return 0, 0, 0


def get_exp_situation(exp_months, req_min_yrs, req_max_yrs):
    """Returns situation string and context note for the prompt."""
    if req_min_yrs == 0:
        return "no_requirement", (
            "No specific experience requirement in JD. "
            "Do not generate experience-gap questions. "
            "Focus on skills and role relevance."
        )
    cand_yrs = exp_months / 12
    shortfall = max(0, req_min_yrs * 12 - exp_months)
    surplus   = max(0, exp_months - (req_max_yrs * 12 if req_max_yrs else 0))

    if shortfall > 6:
        return "underqualified", (
            f"⚠️ UNDERQUALIFIED: Candidate has {round(cand_yrs,1)} yrs but role needs "
            f"{req_min_yrs}–{req_max_yrs} yrs. "
            f"Set selection_probability < 30 and selection_chances to Low or Very Low. "
            f"Q1 MUST ask how candidate would compensate for this gap — be specific."
        )
    elif surplus > 18:
        return "overqualified", (
            f"⚠️ OVERQUALIFIED: Candidate has {round(cand_yrs,1)} yrs for a "
            f"{req_min_yrs}–{req_max_yrs} yr role. "
            f"NEVER ask gap-bridging questions. Q1 should explore motivation for applying "
            f"to a role below seniority level, or concern about being unchallenged. "
            f"experience_gap = 'Exceeds requirement'."
        )
    else:
        return "matched", (
            f"✅ MATCHED: {round(cand_yrs,1)} yrs fits the {req_min_yrs}–{req_max_yrs} yr window. "
            f"No experience gap questions needed. "
            f"Focus interview Q1 on most relevant project or biggest achievement. "
            f"experience_gap = 'Meets requirement'."
        )


# ── Gemini Analysis ────────────────────────────────────────────────

def call_gemini(resume_text, job_text, exp_months, exp_display, req_min_yrs, req_max_yrs):
    """Call Google Gemini 2.0 Flash for resume analysis."""
    import requests as r

    exp_situation, exp_context = get_exp_situation(exp_months, req_min_yrs, req_max_yrs)

    prompt = f"""You are a world-class ATS system and senior HR consultant with 20 years of hiring experience.
Analyze this resume against the job description with surgical precision.

═══ FIXED FACTS — NEVER OVERRIDE THESE ═══
• Candidate experience: {exp_display} ({exp_months} months)
• JD requires: {req_min_yrs}–{req_max_yrs} years
• Situation: {exp_situation.upper()}
• {exp_context}
• years_experience in JSON MUST be exactly "{exp_display}"

═══ CRITICAL RULES ═══
1. Every field must reference SPECIFIC content from THIS resume — no generic filler
2. Interview questions must be UNIQUE and tailored — based on actual projects, skills, gaps found
3. missing_skills = every skill/tool mentioned in JD that is NOT in the resume
4. keywords_missing = important JD terms absent from resume (hurts ATS ranking)
5. strengths must cite actual project names, actual companies, actual metrics from resume
6. If situation=overqualified: Q1 asks motivation/fit for junior role, NOT gap bridging
7. If situation=underqualified: Q1 probes how they compensate for the experience gap
8. If situation=matched: Q1 is about their strongest relevant achievement

Return ONLY this JSON — no markdown, no explanation:

{{
  "ats_score": <integer 0-100 — keyword and formatting match>,
  "match_percentage": <integer 0-100 — overall job fit>,
  "selection_chances": "<Very High|High|Moderate|Low|Very Low>",
  "selection_probability": <integer 0-100>,
  "overall_rating": "<Excellent|Good|Average|Below Average|Poor>",
  "candidate_name": "<full name from resume>",
  "years_experience": "{exp_display}",
  "experience_months": {exp_months},
  "current_role": "<most recent job title from resume>",
  "experience_gap": "<'Meets requirement' OR 'Exceeds requirement by X yrs' OR 'Gap: has X vs Y required'>",
  "recommendation": "<Apply Now|Apply with Cover Letter|Upskill First|Not Suitable Yet>",
  "strengths": [
    {{"title": "<specific strength title>", "detail": "<cite actual project/company/metric from resume>", "icon": "⚡"}},
    {{"title": "<specific strength title>", "detail": "<specific evidence>", "icon": "🎯"}},
    {{"title": "<specific strength title>", "detail": "<specific evidence>", "icon": "🔥"}}
  ],
  "skill_gaps": [
    {{"skill": "<tool/skill in JD but NOT in resume>", "importance": "<Critical|High|Medium>", "suggestion": "<specific course, cert, or project to gain this>"}},
    {{"skill": "<tool/skill in JD but NOT in resume>", "importance": "<Critical|High|Medium>", "suggestion": "<specific actionable step>"}},
    {{"skill": "<tool/skill in JD but NOT in resume>", "importance": "<High|Medium>", "suggestion": "<specific actionable step>"}},
    {{"skill": "<tool/skill in JD but NOT in resume>", "importance": "<High|Medium>", "suggestion": "<specific actionable step>"}}
  ],
  "matched_skills": ["<skill present in both resume AND JD>", "<skill>", "<skill>", "<skill>", "<skill>", "<skill>"],
  "missing_skills": ["<required skill from JD absent in resume>", "<skill>", "<skill>", "<skill>", "<skill>"],
  "improvements": [
    {{"priority": "High", "action": "<specific action referencing resume content>", "reason": "<why this matters for THIS specific role>"}},
    {{"priority": "High", "action": "<specific action>", "reason": "<specific reason>"}},
    {{"priority": "Medium", "action": "<specific action>", "reason": "<specific reason>"}},
    {{"priority": "Medium", "action": "<specific action>", "reason": "<specific reason>"}}
  ],
  "interview_questions": [
    "<Q1: situation-aware unique question — never a template — reference specific resume/JD content>",
    "<Q2: deep technical question probing a specific JD skill this candidate may lack — name the tool>",
    "<Q3: behavioral STAR question referencing a SPECIFIC named project from their resume>",
    "<Q4: probing question about the weakest area in their background vs this JD>",
    "<Q5: forward-looking question about career trajectory relevant to this exact role>"
  ],
  "keywords_found": ["<JD keyword present in resume>", "<keyword>", "<keyword>", "<keyword>", "<keyword>"],
  "keywords_missing": ["<important JD keyword absent from resume>", "<keyword>", "<keyword>", "<keyword>"],
  "red_flags": ["<genuine concern if any — cite specific evidence — or empty string>"],
  "summary": "<3 sentences: (1) overall fit with specific evidence, (2) biggest strength and biggest gap, (3) concrete actionable next step>"
}}

═══ RESUME ═══
{resume_text[:3800]}

═══ JOB DESCRIPTION ═══
{job_text[:2200]}

RETURN ONLY THE JSON OBJECT. No text before or after."""

    try:
        resp = r.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.35,
                    "maxOutputTokens": 2500,
                    "responseMimeType": "application/json",
                },
                "safetySettings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ],
            },
            timeout=30,
        )

        if resp.status_code == 400:
            raise ValueError(f"Gemini API error: {resp.json().get('error', {}).get('message', 'Bad request')}")
        if resp.status_code == 403:
            raise ValueError("Gemini API key invalid or quota exceeded")
        resp.raise_for_status()

        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        result = json.loads(raw)

        # Always enforce computed experience
        result["years_experience"] = exp_display
        result["experience_months"] = exp_months
        result["model_used"] = "gemini-2.0-flash"

        current_app.logger.info(f"Gemini analysis complete for {result.get('candidate_name', 'unknown')}")
        return result

    except (ValueError, json.JSONDecodeError) as e:
        raise
    except Exception as e:
        current_app.logger.warning(f"Gemini API failed: {e}")
        raise


# ── Heuristic fallback (when Gemini fails) ─────────────────────────

def _heuristic(resume_text, job_text, exp_months, exp_display, req_min_yrs, req_max_yrs):
    from utils.skills_taxonomy import SKILLS_TAXONOMY
    rl, jl = resume_text.lower(), job_text.lower()
    job_skills = [s for s in SKILLS_TAXONOMY if s.lower() in jl]
    resume_skills = [s for s in SKILLS_TAXONOMY if s.lower() in rl]
    matched = [s for s in job_skills if s.lower() in rl]
    missing = [s for s in job_skills if s.lower() not in rl]
    extra = [w for w in set(re.findall(r'\b[A-Z][a-zA-Z]{3,}\b', job_text)) if w.lower() not in rl][:4]
    missing_all = list(dict.fromkeys(missing + extra))
    match_pct = int(len(matched) / max(len(job_skills), 1) * 100)

    exp_situation, _ = get_exp_situation(exp_months, req_min_yrs, req_max_yrs)
    shortfall = max(0, req_min_yrs * 12 - exp_months)
    gap_penalty = min(50, shortfall // 3) if exp_situation == "underqualified" else 0
    adj = max(5, match_pct - gap_penalty)
    ats = min(85, max(10, match_pct + 5))

    if adj >= 65:   ch, pr, rt = "High", 65, "Good"
    elif adj >= 45: ch, pr, rt = "Moderate", 42, "Average"
    elif adj >= 25: ch, pr, rt = "Low", 20, "Below Average"
    else:           ch, pr, rt = "Very Low", 7, "Poor"

    if exp_situation == "underqualified":
        gap_display = f"Gap: has {exp_display} vs {req_min_yrs}–{req_max_yrs} yrs required"
        gap_flag = gap_display
        rec = "Not Suitable Yet" if adj < 25 else "Upskill First"
        q1 = f"This role requires {req_min_yrs}+ years and you have {exp_display} — how would you compensate for that gap?"
    elif exp_situation == "overqualified":
        surplus_yrs = round(max(0, exp_months - req_max_yrs*12) / 12, 1)
        gap_display = f"Exceeds requirement by ~{surplus_yrs} yrs"
        gap_flag = ""
        rec = "Apply with Cover Letter"
        q1 = f"You have {exp_display} experience but this role targets {req_min_yrs}–{req_max_yrs} years — what draws you to this position?"
    else:
        gap_display = "Meets requirement" if exp_situation == "matched" else "No specific requirement"
        gap_flag = ""
        rec = "Apply Now" if adj >= 65 else "Apply with Cover Letter"
        q1 = "Walk me through your most impactful project and what you personally contributed to its success"

    name = resume_text.split('\n')[0].strip()[:60]
    m0 = missing_all[0] if missing_all else "core required tools"

    return {
        "ats_score": ats, "match_percentage": adj,
        "selection_chances": ch, "selection_probability": pr,
        "overall_rating": rt, "candidate_name": name,
        "years_experience": exp_display, "experience_months": exp_months,
        "current_role": "See resume", "experience_gap": gap_display,
        "recommendation": rec,
        "strengths": [
            {"title": "Technical Skills", "detail": f"{len(matched)} skills match the JD: {', '.join(matched[:3])}", "icon": "⚡"},
            {"title": "Matched Requirements", "detail": f"{len(matched)} of {len(job_skills)} required skills found in resume", "icon": "🎯"},
            {"title": "Practical Experience", "detail": "Has hands-on project work demonstrating applied skills", "icon": "🔥"},
        ],
        "skill_gaps": [{"skill": s, "importance": "High", "suggestion": f"Build {s} via a targeted course or project"} for s in missing_all[:4]],
        "matched_skills": matched[:6], "missing_skills": missing_all[:6],
        "improvements": [
            {"priority": "High", "action": "Quantify achievements with numbers and business impact", "reason": "ATS and recruiters weight measurable results heavily"},
            {"priority": "High", "action": f"Add missing JD keywords: {', '.join(missing_all[:3])}", "reason": "These terms are in the JD but absent from resume — ATS filters you out"},
            {"priority": "Medium", "action": "Write a role-specific professional summary targeting this JD", "reason": "Generic summaries lower your match score"},
            {"priority": "Medium", "action": "Add links to GitHub projects or portfolio", "reason": "Demonstrates hands-on ability beyond what the resume text conveys"},
        ],
        "interview_questions": [
            q1,
            f"How much hands-on experience do you have with {m0}? Walk me through a specific use case.",
            "Describe a project where things went wrong — what was your specific role in the recovery?",
            f"The JD emphasizes {missing_all[1] if len(missing_all)>1 else 'strong analytical skills'} — how strong are you in this area?",
            "Where do you see yourself in 3 years and how does this specific role fit that trajectory?",
        ],
        "keywords_found": matched[:5], "keywords_missing": missing_all[:5],
        "red_flags": [gap_flag] if gap_flag else [],
        "summary": (
            f"Candidate has {exp_display} of experience with {len(matched)} matching skills. "
            + (f"{gap_display}. " if gap_display not in ("Meets requirement","No specific requirement") else "")
            + f"Skills match: {adj}%. "
            + (f"Key gaps: {', '.join(missing_all[:3])}." if missing_all else "Strong skill alignment.")
        ),
        "model_used": "heuristic_fallback",
    }


# ── Main endpoint ──────────────────────────────────────────────────

@screener_bp.route("/analyze", methods=["POST"])
def analyze():
    upload_dir = current_app.config.get("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # Resume PDF
    if "resume" not in request.files:
        return jsonify({"error": "Resume PDF required"}), 400
    rf = request.files["resume"]
    if not rf.filename or not allowed_file(rf.filename):
        return jsonify({"error": "Resume must be a PDF file"}), 415
    rp = os.path.join(upload_dir, secure_filename(rf.filename))
    rf.save(rp)
    resume_text = extract_text_from_pdf(rp)
    if len(resume_text.strip()) < 50:
        return jsonify({"error": "Could not extract text. Ensure PDF is not a scanned image."}), 422

    # Job description
    job_text = request.form.get("job_text", "").strip()
    if "job_pdf" in request.files:
        jf = request.files["job_pdf"]
        if jf.filename and allowed_file(jf.filename):
            jp = os.path.join(upload_dir, secure_filename(jf.filename))
            jf.save(jp)
            job_text = extract_text_from_pdf(jp) or job_text
    jt = request.form.get("job_title", "").strip()
    if jt and not job_text:
        job_text = f"Job Title: {jt}\nRequires relevant skills and experience for this role."
    if len(job_text.strip()) < 10:
        return jsonify({"error": "Job description required (paste text, upload PDF, or enter job title)"}), 422

    # Compute experience accurately
    exp_months, exp_display = compute_experience_months(resume_text)
    req_min, req_max, _    = parse_required_experience(job_text)

    # Try Gemini first, fall back to heuristic
    try:
        result = call_gemini(resume_text, job_text, exp_months, exp_display, req_min, req_max)
    except Exception as e:
        current_app.logger.warning(f"Gemini failed ({e}), using heuristic fallback")
        result = _heuristic(resume_text, job_text, exp_months, exp_display, req_min, req_max)

    return jsonify({"success": True, "analysis": result}), 200


@screener_bp.route("/test-gemini", methods=["GET"])
def test_gemini():
    """Quick endpoint to verify Gemini API connection."""
    import requests as r
    try:
        resp = r.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": "Say: Gemini connected!"}]}],
                  "generationConfig": {"maxOutputTokens": 20}},
            timeout=10,
        )
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return jsonify({"status": "connected", "model": "gemini-2.0-flash", "response": text})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
