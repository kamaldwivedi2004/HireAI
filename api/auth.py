"""
api/auth.py — Auth endpoints: register, login, logout, me
Stores users in MongoDB with hashed passwords (no JWT needed — session cookie)
"""
from flask import Blueprint, request, jsonify, session
from extensions import mongo
import hashlib, secrets, re, datetime

auth_bp = Blueprint("auth", __name__)

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def valid_email(e): return re.match(r'^[^@]+@[^@]+\.[^@]+$', e)


@auth_bp.route("/register", methods=["POST"])
def register():
    d = request.json or {}
    name  = (d.get("name") or "").strip()
    email = (d.get("email") or "").strip().lower()
    pw    = d.get("password") or ""
    role  = d.get("role") or ""  # "recruiter" | "jobseeker"

    if not name or not email or not pw or role not in ("recruiter", "jobseeker"):
        return jsonify({"error": "All fields required and role must be recruiter or jobseeker"}), 400
    if not valid_email(email):
        return jsonify({"error": "Invalid email address"}), 400
    if len(pw) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    try:
        existing = mongo.db.users.find_one({"email": email})
        if existing:
            return jsonify({"error": "Email already registered"}), 409

        user = {
            "name": name, "email": email,
            "password": hash_pw(pw), "role": role,
            "created_at": datetime.datetime.utcnow(),
            "company": d.get("company", ""),
        }
        mongo.db.users.insert_one(user)
        session["user_email"] = email
        session["user_role"]  = role
        session["user_name"]  = name
        return jsonify({"success": True, "role": role, "name": name}), 201
    except Exception as e:
        return jsonify({"error": f"DB error: {str(e)[:80]}"}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    d = request.json or {}
    email = (d.get("email") or "").strip().lower()
    pw    = d.get("password") or ""

    try:
        user = mongo.db.users.find_one({"email": email, "password": hash_pw(pw)})
        if not user:
            return jsonify({"error": "Invalid email or password"}), 401
        session["user_email"] = email
        session["user_role"]  = user["role"]
        session["user_name"]  = user["name"]
        return jsonify({"success": True, "role": user["role"], "name": user["name"]}), 200
    except Exception as e:
        return jsonify({"error": f"DB error: {str(e)[:80]}"}), 500


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True}), 200


@auth_bp.route("/me", methods=["GET"])
def me():
    if "user_email" not in session:
        return jsonify({"logged_in": False}), 200
    return jsonify({
        "logged_in": True,
        "email": session["user_email"],
        "role":  session["user_role"],
        "name":  session["user_name"],
    }), 200
