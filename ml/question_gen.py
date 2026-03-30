"""
InterviewQuestionGenerator
Generates personalised questions based on skill gaps + role context.
Uses OpenAI if key is set, otherwise uses smart templates (no API needed).
"""

from __future__ import annotations
import os
import json
from typing import Optional


class InterviewQuestionGenerator:
    def __init__(self):
        self._key = os.getenv("OPENAI_API_KEY", "")
        self._url = os.getenv("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
        self._model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    def generate(self, profile: dict, job: dict) -> list:
        if self._key and self._key.startswith("sk-"):
            try:
                return self._call_llm(profile, job)
            except Exception as e:
                print(f"[QuestionGen] LLM call failed: {e}, using templates")
        return self._template_questions(profile, job)

    # ── LLM path ─────────────────────────────────────────────────

    def _call_llm(self, profile: dict, job: dict) -> list:
        import requests
        required = set(job.get("required_skills", []))
        candidate = set(profile.get("skills", []))
        gaps = required - candidate
        exp_years = profile.get("total_experience_months", 0) // 12

        prompt = f"""
Candidate: {profile.get('name', 'Candidate')}, {exp_years} years experience
Skills: {', '.join(list(candidate)[:15])}
Gaps (required but missing): {', '.join(gaps) or 'None'}
Role: {job.get('title')} ({job.get('seniority', 'mid')} level)
Required skills: {', '.join(job.get('required_skills', [])[:15])}

Generate exactly 5 targeted interview questions as a JSON array of strings only.
Mix behavioural STAR format and technical questions. Probe on gap areas specifically.
Return ONLY the JSON array, no other text.
"""
        resp = requests.post(
            self._url,
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
            json={"model": self._model, "messages": [
                {"role": "system", "content": "You are a senior technical recruiter. Return only JSON."},
                {"role": "user", "content": prompt}
            ], "max_tokens": 600, "temperature": 0.7},
            timeout=15,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)

    # ── Template path (no API key needed) ────────────────────────

    def _template_questions(self, profile: dict, job: dict) -> list:
        title    = job.get("title", "this role")
        exp_yrs  = max(1, profile.get("total_experience_months", 0) // 12)
        required = job.get("required_skills", [])
        skills   = set(profile.get("skills", []))
        gaps     = [s for s in required if s not in skills]
        top_skill = required[0] if required else "the core technology"
        gap_skill = gaps[0] if gaps else (required[1] if len(required) > 1 else "system design")

        return [
            f"Walk me through your most impactful project in the last {min(exp_yrs, 3)} years "
            f"that is most relevant to {title}. What was your specific contribution and what was the measurable outcome?",

            f"You listed {top_skill} on your resume — can you describe a challenging problem "
            f"you solved with it and why the approach you chose was the right one?",

            f"Your resume doesn't show strong experience with {gap_skill}. "
            f"How quickly could you get up to speed, and what's your learning strategy for new technologies?",

            f"Describe a situation where you disagreed with a technical decision made by your team or manager. "
            f"How did you handle it, and what was the result?",

            f"Where do you see your career in 3 years, and how does the {title} role fit into that trajectory?",
        ]
