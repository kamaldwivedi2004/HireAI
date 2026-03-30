"""
ResumeParser — PDF extraction + NLP entity recognition
Uses PyMuPDF for text, spaCy for NER, Sentence-Transformers for embeddings
"""

from __future__ import annotations
import re
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

import fitz  # PyMuPDF
import spacy
from sentence_transformers import SentenceTransformer
from utils.skills_taxonomy import SKILLS_TAXONOMY


@dataclass
class Education:
    degree: str
    institution: str
    year: Optional[int] = None


@dataclass
class WorkExperience:
    title: str
    company: str
    duration_months: int
    description: str = ""
    skills_mentioned: list = field(default_factory=list)


@dataclass
class CandidateProfile:
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    total_experience_months: int = 0
    skills: list = field(default_factory=list)
    education: list = field(default_factory=list)
    experience: list = field(default_factory=list)
    summary: str = ""
    raw_text: str = ""
    embedding: list = field(default_factory=list)


class ResumeParser:
    _EMAIL   = re.compile(r"[\w.+\-]+@[\w\-]+\.[\w.]+")
    _PHONE   = re.compile(r"[\+\(]?[\d\s\-\.]{7,15}\d")
    _DEGREE  = re.compile(
        r"\b(B\.?Sc|B\.?E|B\.?Tech|M\.?Sc|M\.?E|M\.?Tech|MBA|PhD|Ph\.D|"
        r"Bachelor|Master|Doctor|Associate)\b", re.IGNORECASE
    )
    _YEAR_RANGE = re.compile(
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?[a-z]*[\s,]*"
        r"((?:19|20)\d{2})\s*[-–—]\s*"
        r"((?:19|20)\d{2}|Present|Current|Now|Till date)",
        re.IGNORECASE
    )

    def __init__(self, embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        print("[Parser] Loading spaCy model...")
        self._nlp = spacy.load("en_core_web_sm")
        print("[Parser] Loading sentence transformer...")
        self._embedder = SentenceTransformer(embedding_model)
        self._skills_lower = {s.lower(): s for s in SKILLS_TAXONOMY}
        print("[Parser] Ready.")

    def parse(self, pdf_path: str) -> dict:
        """Main entry point — returns serialisable dict."""
        text = self._extract_text(pdf_path)
        profile = CandidateProfile(raw_text=text)
        self._extract_contact(text, profile)
        self._extract_skills(text, profile)
        self._extract_education(text, profile)
        self._extract_experience(text, profile)
        profile.summary = text[:500].replace("\n", " ").strip()
        profile.embedding = self._embed(text)
        return asdict(profile)

    def _extract_text(self, path: str) -> str:
        doc = fitz.open(str(path))
        pages = [page.get_text("text") for page in doc]
        doc.close()
        return "\n".join(pages).strip()

    def _extract_contact(self, text: str, p: CandidateProfile):
        nlp_doc = self._nlp(text[:2000])
        for ent in nlp_doc.ents:
            if ent.label_ == "PERSON" and not p.name:
                p.name = ent.text.strip()
            if ent.label_ == "GPE" and not p.location:
                p.location = ent.text.strip()
        m = self._EMAIL.search(text)
        if m:
            p.email = m.group()
        m = self._PHONE.search(text)
        if m:
            p.phone = m.group().strip()

    def _extract_skills(self, text: str, p: CandidateProfile):
        text_lower = text.lower()
        found = []
        for skill_lower, skill_original in self._skills_lower.items():
            if skill_lower in text_lower:
                found.append(skill_original)
        p.skills = sorted(set(found))

    def _extract_education(self, text: str, p: CandidateProfile):
        for line in text.splitlines():
            deg_match = self._DEGREE.search(line)
            if deg_match:
                nlp_doc = self._nlp(line)
                orgs = [e.text for e in nlp_doc.ents if e.label_ == "ORG"]
                year_match = re.search(r"\b(19|20)\d{2}\b", line)
                p.education.append(asdict(Education(
                    degree=deg_match.group(),
                    institution=orgs[0] if orgs else "Unknown",
                    year=int(year_match.group()) if year_match else None,
                )))

    def _extract_experience(self, text: str, p: CandidateProfile):
        total_months = 0
        current_year = 2025
        for m in self._YEAR_RANGE.finditer(text):
            start = int(m.group(1))
            end_str = m.group(2)
            if end_str and end_str[0].isdigit():
                end = int(end_str)
            else:
                end = current_year
            months = max(0, (end - start) * 12)
            total_months += months
        # Remove duplicates — cap at 40 years
        p.total_experience_months = min(total_months, 480)

        # Extract job titles/companies
        nlp_doc = self._nlp(text[:4000])
        for sent in nlp_doc.sents:
            orgs = [e.text for e in sent.ents if e.label_ == "ORG"]
            skills = [self._skills_lower[s] for s in self._skills_lower if s in sent.text.lower()]
            if orgs and len(sent.text.strip()) > 20:
                p.experience.append(asdict(WorkExperience(
                    title="Engineer",
                    company=orgs[0],
                    duration_months=0,
                    description=sent.text.strip()[:300],
                    skills_mentioned=skills[:5],
                )))

    def _embed(self, text: str) -> list:
        truncated = " ".join(text.split()[:400])
        vec = self._embedder.encode(truncated, normalize_embeddings=True)
        return vec.tolist()
