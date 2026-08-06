from functools import wraps
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, ROLES

auth_bp = Blueprint("auth", __name__)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Not authenticated"}), 401
        return f(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return jsonify({"error": "Not authenticated"}), 401
            if session.get("role") not in roles:
                return jsonify({"error": "You don't have permission to do that"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


def current_user_id():
    return session.get("user_id")


def current_role():
    return session.get("role")


def can_see_all():
    """Admins and managers see everything; agents are scoped to their own records."""
    return session.get("role") in ("admin", "manager")


@auth_bp.route("/api/auth/register", methods=["POST"])
@role_required("admin")
def register():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = data.get("role", "agent")

    if not name or not email or not password:
        return jsonify({"error": "name, email and password are required"}), 400
    if role not in ROLES:
        role = "agent"
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    user = User(name=name, email=email, password_hash=generate_password_hash(password), role=role)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid email or password"}), 401

    session["user_id"] = user.id
    session["role"] = user.role
    session["name"] = user.name
    return jsonify(user.to_dict())


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@auth_bp.route("/api/auth/me", methods=["GET"])
@login_required
def me():
    return jsonify({"id": session["user_id"], "name": session["name"], "role": session["role"]})


@auth_bp.route("/api/users", methods=["GET"])
@login_required
def list_users():
    users = User.query.order_by(User.name).all()
    return jsonify([u.to_dict() for u in users])


@auth_bp.route("/api/users/<int:user_id>/reset_password", methods=["POST"])
@role_required("admin")
def reset_password(user_id):
    data = request.get_json(force=True)
    new_password = data.get("password") or ""
    if len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    user = User.query.get_or_404(user_id)
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return jsonify({"ok": True})
