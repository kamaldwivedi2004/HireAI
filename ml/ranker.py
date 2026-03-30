"""
ResumeRanker — XGBoost LTR ranking model
Falls back to weighted heuristic when model not yet trained.
"""

from __future__ import annotations
import pickle
from pathlib import Path
from typing import Optional
import numpy as np
from sentence_transformers import SentenceTransformer


EDUCATION_SCORE = {"phd": 4, "ph.d": 4, "master": 3, "m.sc": 3, "m.tech": 3,
                   "mba": 3, "bachelor": 2, "b.sc": 2, "b.tech": 2, "b.e": 2,
                   "associate": 1}
SENIORITY_MAP = {"junior": 1, "mid": 2, "senior": 3, "lead": 4, "principal": 5}

FEATURE_NAMES = [
    "embedding_similarity",
    "skills_match_ratio",
    "experience_gap_years",
    "education_score",
    "seniority_delta",
    "keyword_density",
    "skills_count",
    "experience_months_norm",
]

# Feature weights for heuristic (when XGBoost model not available)
_WEIGHTS = [0.28, 0.32, -0.06, 0.12, -0.06, 0.10, 0.08, 0.10]


class ResumeRanker:
    def __init__(self, model_path: Optional[str] = None):
        print("[Ranker] Loading sentence transformer...")
        self._embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        self.model = self._load(model_path)
        print("[Ranker] Ready.")

    # ── Public ────────────────────────────────────────────────────

    def rank_batch(self, candidates: list, job: dict) -> list:
        job_emb = self._embed_job(job)
        results = []
        for c in candidates:
            fv = self.build_feature_vector(c.get("profile", {}), job, job_emb)
            match_score  = round(float(self._score(fv)) * 100, 1)
            success_prob = round(float(self._heuristic_success(fv)) * 100, 1)
            results.append({
                **c,
                "match_score":  match_score,
                "success_prob": success_prob,
                "feature_vector": fv.tolist(),
            })
        return sorted(results, key=lambda x: x["match_score"], reverse=True)

    def rank_single(self, candidate: dict, job: dict) -> dict:
        ranked = self.rank_batch([candidate], job)
        r = ranked[0]
        return {"match": r["match_score"], "success": r["success_prob"]}

    def build_feature_vector(self, profile: dict, job: dict,
                             job_emb: Optional[np.ndarray] = None) -> np.ndarray:
        if job_emb is None:
            job_emb = self._embed_job(job)

        cand_emb = np.array(profile.get("embedding", [0.0] * 384))
        if cand_emb.shape[0] == 0:
            cand_emb = np.zeros(384)

        # 1. Cosine similarity
        emb_sim = float(np.dot(cand_emb, job_emb))

        # 2. Skills match ratio
        req_skills   = {s.lower() for s in job.get("required_skills", [])}
        cand_skills  = {s.lower() for s in profile.get("skills", [])}
        skills_ratio = len(req_skills & cand_skills) / max(len(req_skills), 1)

        # 3. Experience gap (years)
        req_months  = job.get("min_experience_months", 0)
        cand_months = profile.get("total_experience_months", 0)
        exp_gap = (req_months - cand_months) / 12.0

        # 4. Education level (normalised 0–1)
        edu_score = self._edu_level(profile) / 4.0

        # 5. Seniority delta
        req_sen  = SENIORITY_MAP.get(job.get("seniority", "mid"), 2)
        cand_sen = self._infer_seniority(cand_months)
        sen_delta = abs(req_sen - cand_sen) / 4.0

        # 6. Keyword density
        kw_density = self._keyword_density(profile.get("raw_text", ""), job)

        # 7. Skills count (normalised to 60)
        skills_count = len(cand_skills) / 60.0

        # 8. Experience months (normalised, cap 10 yrs)
        exp_norm = min(cand_months / 120.0, 1.0)

        return np.array([emb_sim, skills_ratio, exp_gap, edu_score,
                         sen_delta, kw_density, skills_count, exp_norm],
                        dtype=np.float32)

    def train(self, training_data: list):
        """Train XGBRanker on labelled historical data."""
        import xgboost as xgb
        from itertools import groupby

        data = sorted(training_data, key=lambda x: x["job"]["job_id"])
        X, y, groups = [], [], []
        for job_id, group in groupby(data, key=lambda x: x["job"]["job_id"]):
            group = list(group)
            job_emb = self._embed_job(group[0]["job"])
            for item in group:
                X.append(self.build_feature_vector(item["profile"], item["job"], job_emb))
                y.append(item["label"])
            groups.append(len(group))

        X = np.array(X)
        y = np.array(y)

        self.model = xgb.XGBRanker(
            objective="rank:pairwise",
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="ndcg",
        )
        self.model.fit(X, y, group=groups, verbose=True)
        Path("ml/artifacts").mkdir(parents=True, exist_ok=True)
        with open("ml/artifacts/xgb_ranker.pkl", "wb") as f:
            pickle.dump(self.model, f)
        print("[Ranker] Model saved.")

    # ── Private ───────────────────────────────────────────────────

    def _load(self, path):
        if path and Path(path).exists():
            with open(path, "rb") as f:
                return pickle.load(f)
        return None

    def _score(self, fv: np.ndarray) -> float:
        if self.model:
            raw = float(self.model.predict(fv.reshape(1, -1))[0])
            return float(1 / (1 + np.exp(-raw)))
        raw = float(np.dot(fv, _WEIGHTS)) + 0.42
        return float(np.clip(raw, 0.0, 1.0))

    def _heuristic_success(self, fv: np.ndarray) -> float:
        w = [0.25, 0.30, -0.05, 0.12, -0.05, 0.08, 0.05, 0.20]
        raw = float(np.dot(fv, w)) + 0.38
        return float(np.clip(raw, 0.0, 1.0))

    def _embed_job(self, job: dict) -> np.ndarray:
        text = (f"{job.get('title','')} {job.get('description','')} "
                f"{' '.join(job.get('required_skills', []))}")
        return self._embedder.encode(text[:512], normalize_embeddings=True)

    def _edu_level(self, profile: dict) -> int:
        for edu in profile.get("education", []):
            deg = edu.get("degree", "").lower()
            for key, score in EDUCATION_SCORE.items():
                if key in deg:
                    return score
        return 1

    def _infer_seniority(self, months: int) -> int:
        if months < 24:   return 1
        if months < 60:   return 2
        if months < 120:  return 3
        return 4

    def _keyword_density(self, text: str, job: dict) -> float:
        if not text:
            return 0.0
        keywords = job.get("keywords", []) + job.get("required_skills", [])
        if not keywords:
            return 0.0
        text_lower = text.lower()
        hits = sum(1 for kw in keywords if kw.lower() in text_lower)
        return hits / len(keywords)
