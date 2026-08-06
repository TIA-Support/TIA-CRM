from datetime import date
from flask import Blueprint, request, jsonify
from sqlalchemy import or_
from models import db, Task
from routes.auth import login_required, can_see_all, current_user_id

tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.route("/api/tasks", methods=["GET"])
@login_required
def list_tasks():
    query = Task.query
    if not can_see_all():
        query = query.filter(or_(Task.assigned_to == current_user_id(), Task.created_by == current_user_id()))

    status = request.args.get("status")
    if status:
        query = query.filter(Task.status == status)

    due_before = request.args.get("due_before")
    if due_before:
        query = query.filter(Task.due_date <= date.fromisoformat(due_before))

    company_id = request.args.get("company_id")
    if company_id:
        query = query.filter(Task.company_id == company_id)

    tasks = query.order_by(Task.due_date.asc().nullslast()).all()
    return jsonify([t.to_dict() for t in tasks])


@tasks_bp.route("/api/tasks", methods=["POST"])
@login_required
def create_task():
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    task = Task(
        title=title,
        description=data.get("description"),
        due_date=date.fromisoformat(data["due_date"]) if data.get("due_date") else None,
        company_id=data.get("company_id"),
        deal_id=data.get("deal_id"),
        assigned_to=data.get("assigned_to") or current_user_id(),
        created_by=current_user_id(),
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@tasks_bp.route("/api/tasks/<int:task_id>", methods=["PUT"])
@login_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.get_json(force=True)

    for field in ["title", "description", "assigned_to"]:
        if field in data:
            setattr(task, field, data[field])
    if "due_date" in data:
        task.due_date = date.fromisoformat(data["due_date"]) if data["due_date"] else None
    if "status" in data and data["status"] in ("pending", "done"):
        task.status = data["status"]

    db.session.commit()
    return jsonify(task.to_dict())


@tasks_bp.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return jsonify({"ok": True})
