"""
Jobs Blueprint
POST /api/jobs/           — create a job description
GET  /api/jobs/           — list all jobs
GET  /api/jobs/<job_id>   — get one job
DELETE /api/jobs/<job_id> — delete job + its candidates
"""

from flask import Blueprint, request, jsonify
from extensions import mongo
from models.bias_monitor import job_doc

jobs_bp = Blueprint("jobs", __name__)


@jobs_bp.route("/", methods=["POST"])
def create_job():
    body = request.get_json(silent=True) or {}
    required = ["job_id", "title", "description", "required_skills"]
    missing  = [f for f in required if not body.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 422

    if mongo.db.jobs.find_one({"job_id": body["job_id"]}):
        return jsonify({"error": f"Job '{body['job_id']}' already exists"}), 409

    doc = job_doc(
        job_id               = body["job_id"],
        title                = body["title"],
        description          = body["description"],
        required_skills      = body["required_skills"],
        seniority            = body.get("seniority", "mid"),
        min_experience_months= body.get("min_experience_months", 24),
        keywords             = body.get("keywords", []),
    )
    mongo.db.jobs.insert_one(doc)
    return jsonify({"success": True, "job_id": body["job_id"],
                    "message": f"Job '{body['title']}' created successfully"}), 201


@jobs_bp.route("/", methods=["GET"])
def list_jobs():
    jobs = list(mongo.db.jobs.find({}, {"embedding": 0})
                .sort("created_at", -1).limit(50))
    for j in jobs:
        j["_id"] = str(j["_id"])
        j["created_at"] = str(j.get("created_at", ""))
    return jsonify({"jobs": jobs, "total": len(jobs)}), 200


@jobs_bp.route("/<job_id>", methods=["GET"])
def get_job(job_id):
    job = mongo.db.jobs.find_one({"job_id": job_id}, {"embedding": 0})
    if not job:
        return jsonify({"error": f"Job '{job_id}' not found"}), 404
    job["_id"] = str(job["_id"])
    job["created_at"] = str(job.get("created_at", ""))
    # Add candidate count
    job["candidate_count"] = mongo.db.candidates.count_documents({"job_id": job_id})
    return jsonify(job), 200


@jobs_bp.route("/<job_id>", methods=["DELETE"])
def delete_job(job_id):
    if not mongo.db.jobs.find_one({"job_id": job_id}):
        return jsonify({"error": "Not found"}), 404
    mongo.db.jobs.delete_one({"job_id": job_id})
    deleted = mongo.db.candidates.delete_many({"job_id": job_id}).deleted_count
    return jsonify({"deleted": job_id, "candidates_removed": deleted}), 200
