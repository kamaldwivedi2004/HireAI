"""
api/portal.py — Recruiter & Job Seeker portal endpoints
"""
from flask import Blueprint, request, jsonify, session
from extensions import mongo
from bson import ObjectId
import datetime

portal_bp = Blueprint("portal", __name__)

def login_required(role=None):
    """Check session auth."""
    if "user_email" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    if role and session.get("user_role") != role:
        return jsonify({"error": f"Access denied — {role} only"}), 403
    return None

def oid(s):
    try: return ObjectId(s)
    except: return None


# ── RECRUITER ──────────────────────────────────────────────────────

@portal_bp.route("/recruiter/posts", methods=["GET"])
def get_posts():
    err = login_required("recruiter")
    if err: return err
    posts = list(mongo.db.job_posts.find(
        {"recruiter_email": session["user_email"]},
        {"_id": 1, "title": 1, "company": 1, "location": 1, "type": 1,
         "created_at": 1, "status": 1, "applicant_count": 1}
    ).sort("created_at", -1))
    for p in posts:
        p["_id"] = str(p["_id"])
        p["applicant_count"] = mongo.db.applications.count_documents({"job_id": p["_id"]})
    return jsonify({"posts": posts}), 200


@portal_bp.route("/recruiter/posts", methods=["POST"])
def create_post():
    err = login_required("recruiter")
    if err: return err
    d = request.json or {}
    required = ["title", "description", "skills", "experience"]
    for f in required:
        if not d.get(f):
            return jsonify({"error": f"Field '{f}' is required"}), 400

    post = {
        "recruiter_email": session["user_email"],
        "recruiter_name":  session["user_name"],
        "title":       d["title"],
        "company":     d.get("company", session["user_name"]),
        "location":    d.get("location", "Remote"),
        "type":        d.get("type", "Full-time"),
        "description": d["description"],
        "skills":      [s.strip() for s in d["skills"].split(",") if s.strip()],
        "experience":  d["experience"],
        "salary":      d.get("salary", ""),
        "status":      "active",
        "created_at":  datetime.datetime.utcnow(),
    }
    res = mongo.db.job_posts.insert_one(post)
    return jsonify({"success": True, "post_id": str(res.inserted_id)}), 201


@portal_bp.route("/recruiter/posts/<post_id>", methods=["GET"])
def get_post_detail(post_id):
    err = login_required("recruiter")
    if err: return err
    post = mongo.db.job_posts.find_one({"_id": oid(post_id), "recruiter_email": session["user_email"]})
    if not post:
        return jsonify({"error": "Post not found"}), 404
    post["_id"] = str(post["_id"])

    # Get all applicants with their screening data
    apps = list(mongo.db.applications.find({"job_id": post_id}).sort("applied_at", -1))
    for a in apps:
        a["_id"] = str(a["_id"])
        a["applied_at"] = a["applied_at"].isoformat() if hasattr(a.get("applied_at"), "isoformat") else ""

    return jsonify({"post": post, "applications": apps}), 200


@portal_bp.route("/recruiter/posts/<post_id>/status", methods=["PATCH"])
def update_post_status(post_id):
    err = login_required("recruiter")
    if err: return err
    d = request.json or {}
    mongo.db.job_posts.update_one(
        {"_id": oid(post_id), "recruiter_email": session["user_email"]},
        {"$set": {"status": d.get("status", "active")}}
    )
    return jsonify({"success": True}), 200


@portal_bp.route("/recruiter/applications/<app_id>/stage", methods=["PATCH"])
def update_app_stage(app_id):
    err = login_required("recruiter")
    if err: return err
    d = request.json or {}
    mongo.db.applications.update_one(
        {"_id": oid(app_id)},
        {"$set": {"stage": d.get("stage", "Applied"), "updated_at": datetime.datetime.utcnow()}}
    )
    return jsonify({"success": True}), 200


# ── JOB SEEKER ─────────────────────────────────────────────────────

@portal_bp.route("/jobs/active", methods=["GET"])
def active_jobs():
    # Public — no auth required
    jobs = list(mongo.db.job_posts.find(
        {"status": "active"},
        {"_id": 1, "title": 1, "company": 1, "location": 1, "type": 1,
         "skills": 1, "experience": 1, "salary": 1, "created_at": 1}
    ).sort("created_at", -1).limit(50))
    for j in jobs:
        j["_id"] = str(j["_id"])
        j["created_at"] = j["created_at"].isoformat() if hasattr(j.get("created_at"), "isoformat") else ""
    return jsonify({"jobs": jobs}), 200


@portal_bp.route("/jobseeker/apply", methods=["POST"])
def apply():
    err = login_required("jobseeker")
    if err: return err

    job_id   = request.form.get("job_id", "")
    if not job_id:
        return jsonify({"error": "job_id required"}), 400

    # Check already applied
    existing = mongo.db.applications.find_one({
        "job_id": job_id, "applicant_email": session["user_email"]
    })
    if existing:
        return jsonify({"error": "You have already applied to this job"}), 409

    # Save resume PDF if uploaded
    resume_text = ""
    screening = {}
    if "resume" in request.files:
        import os
        from werkzeug.utils import secure_filename
        from api.screener import extract_text_from_pdf, compute_experience_months, parse_required_experience, call_gemini, _heuristic
        rf = request.files["resume"]
        if rf.filename.endswith(".pdf"):
            path = f"/tmp/{secure_filename(rf.filename)}"
            rf.save(path)
            resume_text = extract_text_from_pdf(path)

            # Auto-screen against job
            job = mongo.db.job_posts.find_one({"_id": oid(job_id)})
            if job and resume_text:
                job_text = f"{job['title']}\n{job['description']}\nRequired skills: {', '.join(job.get('skills',[]))}\nExperience: {job.get('experience','')}"
                exp_months, exp_display = compute_experience_months(resume_text)
                req_min, req_max, _ = parse_required_experience(job_text)
                try:
                    screening = call_gemini(resume_text, job_text, exp_months, exp_display, req_min, req_max)
                except Exception:
                    screening = _heuristic(resume_text, job_text, exp_months, exp_display, req_min, req_max)

    # Save job details snapshot
    job = mongo.db.job_posts.find_one({"_id": oid(job_id)}, {"title": 1, "company": 1})

    app_doc = {
        "job_id":          job_id,
        "job_title":       job.get("title", "") if job else "",
        "job_company":     job.get("company", "") if job else "",
        "applicant_email": session["user_email"],
        "applicant_name":  session["user_name"],
        "resume_text":     resume_text[:3000],
        "screening":       screening,
        "stage":           "Applied",
        "applied_at":      datetime.datetime.utcnow(),
        "updated_at":      datetime.datetime.utcnow(),
    }
    res = mongo.db.applications.insert_one(app_doc)
    return jsonify({"success": True, "application_id": str(res.inserted_id), "screening": screening}), 201


@portal_bp.route("/jobseeker/applications", methods=["GET"])
def my_applications():
    err = login_required("jobseeker")
    if err: return err
    apps = list(mongo.db.applications.find(
        {"applicant_email": session["user_email"]},
        {"_id": 1, "job_id": 1, "job_title": 1, "job_company": 1,
         "stage": 1, "applied_at": 1, "screening": 1}
    ).sort("applied_at", -1))
    for a in apps:
        a["_id"] = str(a["_id"])
        a["applied_at"] = a["applied_at"].isoformat() if hasattr(a.get("applied_at"), "isoformat") else ""
    return jsonify({"applications": apps}), 200
