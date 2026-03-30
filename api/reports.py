"""
Reports Blueprint
GET /api/reports/pipeline/<job_id>  — full pipeline summary
GET /api/reports/stats              — overall system stats
"""

from flask import Blueprint, jsonify
from extensions import mongo
from datetime import datetime

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/pipeline/<job_id>", methods=["GET"])
def pipeline_report(job_id):
    job = mongo.db.jobs.find_one({"job_id": job_id}, {"embedding": 0})
    if not job:
        return jsonify({"error": f"Job '{job_id}' not found"}), 404

    candidates = list(mongo.db.candidates.find(
        {"job_id": job_id}, {"profile.embedding": 0, "profile.raw_text": 0}
    ))

    scores = [c["scores"].get("match") for c in candidates
              if c["scores"].get("match") is not None]

    status_counts = {}
    for c in candidates:
        s = c.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    top10 = sorted(
        [c for c in candidates if c["scores"].get("match")],
        key=lambda x: x["scores"]["match"],
        reverse=True
    )[:10]

    return jsonify({
        "job_id":     job_id,
        "title":      job.get("title"),
        "seniority":  job.get("seniority"),
        "required_skills": job.get("required_skills", []),
        "pipeline": {
            "total":       len(candidates),
            "avg_score":   round(sum(scores)/max(len(scores), 1), 1),
            "max_score":   max(scores) if scores else 0,
            "min_score":   min(scores) if scores else 0,
            "by_status":   status_counts,
        },
        "top_candidates": [
            {
                "id":           str(c["_id"]),
                "name":         c["profile"].get("name"),
                "email":        c["profile"].get("email"),
                "match_score":  c["scores"].get("match"),
                "success_prob": c["scores"].get("success"),
                "skills":       c["profile"].get("skills", [])[:8],
                "status":       c["status"],
            }
            for c in top10
        ],
        "generated_at": datetime.utcnow().isoformat(),
    }), 200


@reports_bp.route("/stats", methods=["GET"])
def system_stats():
    total_candidates = mongo.db.candidates.count_documents({})
    total_jobs       = mongo.db.jobs.count_documents({})
    shortlisted      = mongo.db.candidates.count_documents({"status": "shortlisted"})
    hired            = mongo.db.candidates.count_documents({"status": "hired"})

    return jsonify({
        "total_candidates": total_candidates,
        "total_jobs":       total_jobs,
        "shortlisted":      shortlisted,
        "hired":            hired,
        "hire_rate":        round(hired / max(total_candidates, 1) * 100, 1),
    }), 200
