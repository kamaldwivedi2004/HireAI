"""
Resume Blueprint
POST /api/resume/upload         — upload + parse PDF resume
POST /api/resume/rank           — rank all candidates for a job
GET  /api/resume/<id>/explain   — SHAP feature explanation
GET  /api/resume/<id>/questions — generated interview questions
"""

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from bson import ObjectId
import os

from extensions import mongo
from ml.parser import ResumeParser
from ml.ranker import ResumeRanker
from ml.predictor import SuccessPredictor, ShapExplainer
from ml.question_gen import InterviewQuestionGenerator
from models.bias_monitor import candidate_doc
from utils.validators import allowed_file, validate_job_id

resume_bp = Blueprint("resume", __name__)

# Lazy-loaded singletons
_parser     = None
_ranker     = None
_predictor  = None
_explainer  = None
_qgen       = None


def get_parser():
    global _parser
    if _parser is None:
        _parser = ResumeParser()
    return _parser

def get_ranker():
    global _ranker
    if _ranker is None:
        _ranker = ResumeRanker(current_app.config.get("RANKING_MODEL_PATH"))
    return _ranker

def get_predictor():
    global _predictor
    if _predictor is None:
        _predictor = SuccessPredictor(current_app.config.get("PREDICTOR_MODEL_PATH"))
    return _predictor

def get_explainer():
    global _explainer
    if _explainer is None:
        _explainer = ShapExplainer(get_ranker().model)
    return _explainer

def get_qgen():
    global _qgen
    if _qgen is None:
        _qgen = InterviewQuestionGenerator()
    return _qgen


# ── Upload ────────────────────────────────────────────────────────────────────

@resume_bp.route("/upload", methods=["POST"])
def upload_resume():
    if "file" not in request.files:
        return jsonify({"error": "No file in request. Send as multipart/form-data with key 'file'"}), 400

    file   = request.files["file"]
    job_id = request.form.get("job_id", "").strip()

    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "Only PDF files accepted"}), 415
    if not validate_job_id(job_id):
        return jsonify({"error": "Missing or invalid job_id (3-40 alphanumeric/dash/underscore)"}), 422

    # Check job exists
    job = mongo.db.jobs.find_one({"job_id": job_id})
    if not job:
        return jsonify({"error": f"Job '{job_id}' not found. Create it first via POST /api/jobs/"}), 404

    # Save PDF
    filename    = secure_filename(file.filename)
    upload_dir  = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    save_path   = os.path.join(upload_dir, filename)
    file.save(save_path)

    # Parse
    try:
        profile = get_parser().parse(save_path)
    except Exception as e:
        return jsonify({"error": f"PDF parsing failed: {str(e)}"}), 422

    # Store in MongoDB
    doc = candidate_doc(job_id, filename, profile)
    result = mongo.db.candidates.insert_one(doc)
    cid = str(result.inserted_id)

    # Score immediately
    try:
        ranker = get_ranker()
        scores = ranker.rank_single(doc, job)
        fv     = ranker.build_feature_vector(profile, job)
        shap   = get_explainer().explain(fv)
        qs     = get_qgen().generate(profile, job)

        mongo.db.candidates.update_one(
            {"_id": result.inserted_id},
            {"$set": {
                "scores": scores,
                "status": "scored",
                "shap_values": shap,
                "interview_questions": qs,
            }}
        )
        profile["scores"] = scores
    except Exception as e:
        print(f"[Upload] Scoring failed (non-fatal): {e}")

    return jsonify({
        "success":      True,
        "candidate_id": cid,
        "profile": {
            "name":                    profile.get("name"),
            "email":                   profile.get("email"),
            "skills":                  profile.get("skills", []),
            "total_experience_months": profile.get("total_experience_months"),
            "education":               profile.get("education", []),
        },
        "scores": profile.get("scores", {}),
    }), 201


# ── Rank batch ────────────────────────────────────────────────────────────────

@resume_bp.route("/rank", methods=["POST"])
def rank_resumes():
    body   = request.get_json(silent=True) or {}
    job_id = body.get("job_id", "").strip()

    if not validate_job_id(job_id):
        return jsonify({"error": "Missing or invalid job_id"}), 422

    job = mongo.db.jobs.find_one({"job_id": job_id})
    if not job:
        return jsonify({"error": f"Job '{job_id}' not found"}), 404

    candidates = list(mongo.db.candidates.find({"job_id": job_id}))
    if not candidates:
        return jsonify({"ranked": [], "total": 0, "message": "No candidates for this job yet"}), 200

    ranked = get_ranker().rank_batch(candidates, job)

    # Persist scores
    for c in ranked:
        mongo.db.candidates.update_one(
            {"_id": c["_id"]},
            {"$set": {"scores.match": c["match_score"],
                      "scores.success": c["success_prob"],
                      "status": "scored"}}
        )

    # Serialise
    output = []
    for c in ranked:
        output.append({
            "candidate_id": str(c["_id"]),
            "name":         c.get("profile", {}).get("name"),
            "email":        c.get("profile", {}).get("email"),
            "match_score":  c["match_score"],
            "success_prob": c["success_prob"],
            "skills":       c.get("profile", {}).get("skills", [])[:10],
            "status":       c.get("status"),
        })

    return jsonify({"ranked": output, "total": len(output), "job_id": job_id}), 200


# ── Explain ───────────────────────────────────────────────────────────────────

@resume_bp.route("/<candidate_id>/explain", methods=["GET"])
def explain(candidate_id):
    try:
        oid = ObjectId(candidate_id)
    except Exception:
        return jsonify({"error": "Invalid candidate_id"}), 400

    c = mongo.db.candidates.find_one({"_id": oid})
    if not c:
        return jsonify({"error": "Candidate not found"}), 404

    # Return cached SHAP if available
    if c.get("shap_values"):
        return jsonify({"candidate_id": candidate_id, "shap": c["shap_values"]}), 200

    job = mongo.db.jobs.find_one({"job_id": c["job_id"]})
    if not job:
        return jsonify({"error": "Job not found"}), 404

    import numpy as np
    fv   = get_ranker().build_feature_vector(c["profile"], job)
    shap = get_explainer().explain(fv)
    mongo.db.candidates.update_one({"_id": oid}, {"$set": {"shap_values": shap}})
    return jsonify({"candidate_id": candidate_id, "shap": shap}), 200


# ── Interview questions ───────────────────────────────────────────────────────

@resume_bp.route("/<candidate_id>/questions", methods=["GET"])
def questions(candidate_id):
    try:
        oid = ObjectId(candidate_id)
    except Exception:
        return jsonify({"error": "Invalid candidate_id"}), 400

    c = mongo.db.candidates.find_one({"_id": oid})
    if not c:
        return jsonify({"error": "Candidate not found"}), 404

    # Return cached questions if available
    if c.get("interview_questions"):
        return jsonify({"candidate_id": candidate_id,
                        "questions": c["interview_questions"]}), 200

    job = mongo.db.jobs.find_one({"job_id": c["job_id"]})
    qs  = get_qgen().generate(c["profile"], job or {})
    mongo.db.candidates.update_one({"_id": oid}, {"$set": {"interview_questions": qs}})
    return jsonify({"candidate_id": candidate_id, "questions": qs}), 200
