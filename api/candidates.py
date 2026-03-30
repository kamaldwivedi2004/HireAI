"""
Candidates Blueprint
GET   /api/candidates/               — list + filter candidates
GET   /api/candidates/<id>           — single candidate full detail
PATCH /api/candidates/<id>/status    — update pipeline stage
POST  /api/candidates/bias-audit     — run EEOC fairness audit
"""

from flask import Blueprint, request, jsonify
from bson import ObjectId
from extensions import mongo
from models.bias_monitor import BiasMonitor

candidates_bp = Blueprint("candidates", __name__)
_monitor = BiasMonitor()

VALID_STATUSES = {"pending", "scored", "review", "shortlisted", "rejected", "hired"}


@candidates_bp.route("/", methods=["GET"])
def list_candidates():
    job_id  = request.args.get("job_id")
    status  = request.args.get("status")
    sort_by = request.args.get("sort", "score")  # score | name | success
    limit   = min(int(request.args.get("limit", 50)), 200)
    skip    = int(request.args.get("skip", 0))

    query = {}
    if job_id:  query["job_id"] = job_id
    if status:  query["status"] = status

    sort_field = "scores.match" if sort_by == "score" else \
                 "scores.success" if sort_by == "success" else "profile.name"

    raw = list(mongo.db.candidates.find(query, {"profile.embedding": 0, "profile.raw_text": 0})
               .sort(sort_field, -1).skip(skip).limit(limit))

    out = []
    for c in raw:
        out.append({
            "id":                 str(c["_id"]),
            "name":               c["profile"].get("name"),
            "email":              c["profile"].get("email"),
            "job_id":             c["job_id"],
            "status":             c["status"],
            "match_score":        c["scores"].get("match"),
            "success_prob":       c["scores"].get("success"),
            "experience_months":  c["profile"].get("total_experience_months"),
            "skills":             c["profile"].get("skills", [])[:10],
            "education":          c["profile"].get("education", [])[:2],
            "created_at":         str(c.get("created_at", "")),
        })

    total = mongo.db.candidates.count_documents(query)
    return jsonify({"candidates": out, "returned": len(out), "total": total}), 200


@candidates_bp.route("/<candidate_id>", methods=["GET"])
def get_candidate(candidate_id):
    try:
        oid = ObjectId(candidate_id)
    except Exception:
        return jsonify({"error": "Invalid candidate_id"}), 400

    c = mongo.db.candidates.find_one({"_id": oid}, {"profile.embedding": 0})
    if not c:
        return jsonify({"error": "Not found"}), 404

    return jsonify({
        "id":                  str(c["_id"]),
        "job_id":              c["job_id"],
        "filename":            c.get("filename"),
        "status":              c["status"],
        "scores":              c["scores"],
        "shap_values":         c.get("shap_values", []),
        "interview_questions": c.get("interview_questions", []),
        "profile": {
            k: v for k, v in c["profile"].items()
            if k not in ("embedding", "raw_text")
        },
        "created_at": str(c.get("created_at", "")),
    }), 200


@candidates_bp.route("/<candidate_id>/status", methods=["PATCH"])
def update_status(candidate_id):
    try:
        oid = ObjectId(candidate_id)
    except Exception:
        return jsonify({"error": "Invalid candidate_id"}), 400

    body   = request.get_json(silent=True) or {}
    status = body.get("status", "").lower()

    if status not in VALID_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of: {sorted(VALID_STATUSES)}"}), 422

    result = mongo.db.candidates.update_one(
        {"_id": oid}, {"$set": {"status": status}}
    )
    if result.matched_count == 0:
        return jsonify({"error": "Candidate not found"}), 404

    return jsonify({"updated": candidate_id, "status": status}), 200


@candidates_bp.route("/bias-audit", methods=["POST"])
def bias_audit():
    body   = request.get_json(silent=True) or {}
    job_id = body.get("job_id", "").strip()
    if not job_id:
        return jsonify({"error": "job_id required"}), 422
    result = _monitor.run_audit(job_id)
    return jsonify(result), 200
