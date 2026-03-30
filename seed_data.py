"""
seed_data.py — Test MongoDB connection and seed sample jobs
Run this FIRST to verify everything works:
    python seed_data.py
"""

import sys
from dotenv import load_dotenv
load_dotenv()

import os
from pymongo import MongoClient
from datetime import datetime


MONGO_URI = os.getenv("MONGO_URI")
SAMPLE_JOBS = [
    {
        "job_id": "JD-ML-001",
        "title": "Senior ML Engineer",
        "description": (
            "Build and deploy production ML models. Work with large-scale datasets, "
            "design ML pipelines, and collaborate with data scientists to bring models to prod."
        ),
        "required_skills": ["Python", "TensorFlow", "PyTorch", "MLOps", "Docker", "SQL", "AWS"],
        "seniority": "senior",
        "min_experience_months": 60,
        "keywords": ["machine learning", "deep learning", "production", "pipelines", "deployment"],
        "embedding": [],
        "created_at": datetime.utcnow(),
    },
    {
        "job_id": "JD-DS-001",
        "title": "Data Scientist",
        "description": (
            "Analyse large datasets, build predictive models, and communicate insights "
            "to business stakeholders. Strong statistics background required."
        ),
        "required_skills": ["Python", "Pandas", "scikit-learn", "SQL", "Statistics", "Matplotlib"],
        "seniority": "mid",
        "min_experience_months": 24,
        "keywords": ["data analysis", "statistics", "machine learning", "visualisation", "A/B testing"],
        "embedding": [],
        "created_at": datetime.utcnow(),
    },
    {
        "job_id": "JD-BE-001",
        "title": "Backend Engineer (Python)",
        "description": (
            "Design and build scalable REST APIs. Work with microservices, "
            "databases, and cloud infrastructure."
        ),
        "required_skills": ["Python", "Flask", "FastAPI", "PostgreSQL", "Docker", "Redis", "AWS"],
        "seniority": "mid",
        "min_experience_months": 36,
        "keywords": ["API", "backend", "microservices", "database", "cloud"],
        "embedding": [],
        "created_at": datetime.utcnow(),
    },
]


def main():
    print("\n" + "="*50)
    print("  HireAI — Connection Test & Seed")
    print("="*50 + "\n")

    if not MONGO_URI:
        print("❌  MONGO_URI not set in .env file")
        sys.exit(1)

    # Test connection
    print("→ Connecting to MongoDB Atlas…")
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        client.admin.command("ping")
        print("✅  MongoDB Atlas connected!\n")
    except Exception as e:
        print(f"❌  Connection failed: {e}")
        print("\nCheck:")
        print("  1. Your IP is whitelisted in MongoDB Atlas → Network Access")
        print("  2. The MONGO_URI in .env is correct")
        sys.exit(1)

    db = client["hireai"]

    # Ensure indexes
    print("→ Creating indexes…")
    db.candidates.create_index("job_id")
    db.candidates.create_index([("scores.match", -1)])
    db.jobs.create_index("job_id", unique=True)
    db.audit_log.create_index("created_at")
    print("✅  Indexes created\n")

    # Seed jobs
    print("→ Seeding sample job descriptions…")
    seeded = 0
    for job in SAMPLE_JOBS:
        if not db.jobs.find_one({"job_id": job["job_id"]}):
            db.jobs.insert_one(job)
            print(f"   ✓ Created: {job['title']} ({job['job_id']})")
            seeded += 1
        else:
            print(f"   - Already exists: {job['job_id']}")

    print(f"\n✅  Seeded {seeded} new job(s)\n")

    # Summary
    total_jobs  = db.jobs.count_documents({})
    total_cands = db.candidates.count_documents({})
    print("─"*40)
    print(f"  Jobs in DB:       {total_jobs}")
    print(f"  Candidates in DB: {total_cands}")
    print("─"*40)
    print("\n🚀  All good! Now run:  python app.py")
    print("   Then open:       http://localhost:5000\n")


if __name__ == "__main__":
    main()
