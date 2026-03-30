"""
MongoDB document schemas + bias / fairness monitoring.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
import hashlib
import statistics

from extensions import mongo


# ── Schemas ─────────────────────────────────────────────────────────────────────

def candidate_doc(job_id: str, filename: str, profile: dict) -> dict:
    return {
        "job_id":             job_id,
        "filename":           filename,
        "profile":            profile,
        "status":             "pending",
        "scores":             {"match": None, "success": None},
        "shap_values":        [],
        "interview_questions":[],
        "created_at":         datetime.utcnow(),
        "updated_at":         datetime.utcnow(),
    }


def job_doc(job_id: str, title: str, description: str,
            required_skills: list, seniority: str = "mid",
            min_experience_months: int = 24,
            keywords: Optional[list] = None) -> dict:
    return {
        "job_id":                 job_id,
        "title":                  title,
        "description":            description,
        "required_skills":        required_skills,
        "seniority":              seniority,
        "min_experience_months":  min_experience_months,
        "keywords":               keywords or [],
        "embedding":              [],
        "created_at":             datetime.utcnow(),
    }


def ensure_indexes(app):
    """Create MongoDB indexes — call once at startup."""
    with app.app_context():
        mongo.db.candidates.create_index("job_id")
        mongo.db.candidates.create_index("status")
        mongo.db.candidates.create_index([("scores.match", -1)])
        mongo.db.jobs.create_index("job_id", unique=True)
        mongo.db.audit_log.create_index("created_at")
        print("[DB] Indexes ensured.")


# ── Bias Monitor ────────────────────────────────────────────────────────────────

class BiasMonitor:
    """EEOC 4/5 disparate impact analysis on shortlisted candidates."""

    DIR_THRESHOLD = 0.80

    def run_audit(self, job_id: str) -> dict:
        candidates = list(mongo.db.candidates.find({"job_id": job_id}))
        if not candidates:
            return {"error": "No candidates found for this job_id"}

        shortlisted = [c for c in candidates
                       if (c["scores"].get("match") or 0) >= 70]

        shortlisted_ids = {str(c["_id"]) for c in shortlisted}

        dir_result   = self._disparate_impact(candidates, shortlisted_ids)
        score_dist   = self._score_distribution(candidates)
        name_check   = self._name_proxy(candidates, shortlisted_ids)
        passed       = all(v >= self.DIR_THRESHOLD
                           for v in dir_result.values() if isinstance(v, float))

        audit = {
            "job_id":               job_id,
            "total_candidates":     len(candidates),
            "shortlisted":          len(shortlisted),
            "shortlist_rate":       round(len(shortlisted) / max(len(candidates), 1), 3),
            "disparate_impact":     dir_result,
            "score_distribution":   score_dist,
            "name_bias_check":      name_check,
            "passed_eeoc_threshold":passed,
            "created_at":           datetime.utcnow().isoformat(),
        }
        if not passed:
            audit["alert"] = (
                "Disparate Impact Ratio below 0.80 EEOC threshold. "
                "Review feature weights and shortlisting criteria."
            )

        # Persist
        mongo.db.audit_log.insert_one({**audit})
        return audit

    def _disparate_impact(self, all_cands: list, shortlisted_ids: set) -> dict:
        groups: dict[str, list] = {"A": [], "B": [], "C": []}
        for c in all_cands:
            name = c.get("profile", {}).get("name", "")
            g = ["A", "B", "C"][int(hashlib.md5(name.encode()).hexdigest(), 16) % 3]
            groups[g].append(c)

        rates = {}
        for grp, members in groups.items():
            sel = sum(1 for m in members if str(m["_id"]) in shortlisted_ids)
            rates[grp] = sel / max(len(members), 1)

        result = {}
        keys = list(rates.keys())
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a, b = keys[i], keys[j]
                if rates[b] > 0:
                    result[f"group_{a}_vs_{b}"] = round(rates[a] / rates[b], 3)
        return result

    def _score_distribution(self, candidates: list) -> dict:
        scores = [c["scores"].get("match") for c in candidates
                  if c["scores"].get("match") is not None]
        if not scores:
            return {}
        return {
            "mean":   round(statistics.mean(scores), 1),
            "median": round(statistics.median(scores), 1),
            "stdev":  round(statistics.stdev(scores) if len(scores) > 1 else 0, 1),
            "min":    min(scores),
            "max":    max(scores),
        }

    def _name_proxy(self, candidates: list, shortlisted_ids: set) -> dict:
        group_scores: dict[str, list] = {}
        for c in candidates:
            score = c["scores"].get("match")
            if score is None:
                continue
            name = c.get("profile", {}).get("name", "")
            g = ["A", "B", "C"][int(hashlib.md5(name.encode()).hexdigest(), 16) % 3]
            group_scores.setdefault(g, []).append(score)

        avgs = {g: round(sum(s)/len(s), 1) for g, s in group_scores.items() if s}
        if len(avgs) >= 2:
            vals = list(avgs.values())
            delta = round(max(vals) - min(vals), 1)
            avgs["max_delta_pts"] = delta
            avgs["bias_alert"]    = delta > 5
        return avgs
