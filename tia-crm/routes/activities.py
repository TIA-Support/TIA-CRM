from datetime import date
from flask import Blueprint, request, jsonify
from models import db, Activity, Company, ACTIVITY_TYPES, CALL_OUTCOMES
from routes.auth import login_required, current_user_id

activities_bp = Blueprint("activities", __name__)

# When a call is logged with certain outcomes, auto-update the company's status
OUTCOME_TO_STATUS = {
    "interested": "interested",
    "not_interested": "not_interested",
    "converted": "customer",
    "no_answer": "contacted",
    "callback": "contacted",
    "wrong_number": "contacted",
}


@activities_bp.route("/api/activities", methods=["GET"])
@login_required
def list_activities():
    """List activities, optionally filtered by follow-up due date (e.g. today's callbacks)."""
    query = Activity.query

    follow_up_before = request.args.get("follow_up_before")
    if follow_up_before:
        query = query.filter(
            Activity.next_follow_up.isnot(None),
            Activity.next_follow_up <= date.fromisoformat(follow_up_before),
        )

    company_id = request.args.get("company_id")
    if company_id:
        query = query.filter(Activity.company_id == company_id)

    user_id = request.args.get("user_id")
    if user_id:
        query = query.filter(Activity.user_id == user_id)

    activities = query.order_by(Activity.occurred_at.desc()).all()
    result = []
    for a in activities:
        d = a.to_dict()
        d["company_name"] = a.company.name if a.company else None
        result.append(d)
    return jsonify(result)


@activities_bp.route("/api/activities", methods=["POST"])
@login_required
def create_activity():
    data = request.get_json(force=True)
    company_id = data.get("company_id")
    activity_type = data.get("type", "note")

    if not company_id:
        return jsonify({"error": "company_id is required"}), 400
    if activity_type not in ACTIVITY_TYPES:
        return jsonify({"error": "Invalid activity type"}), 400

    company = Company.query.get_or_404(company_id)

    outcome = data.get("outcome")
    if activity_type == "call":
        if outcome not in CALL_OUTCOMES:
            return jsonify({"error": "A valid outcome is required for calls"}), 400
    else:
        outcome = None

    activity = Activity(
        company_id=company.id,
        contact_id=data.get("contact_id"),
        deal_id=data.get("deal_id"),
        user_id=current_user_id(),
        type=activity_type,
        outcome=outcome,
        notes=data.get("notes"),
        next_follow_up=date.fromisoformat(data["next_follow_up"]) if data.get("next_follow_up") else None,
    )
    db.session.add(activity)

    if activity_type == "call" and outcome in OUTCOME_TO_STATUS:
        company.status = OUTCOME_TO_STATUS[outcome]

    db.session.commit()
    return jsonify(activity.to_dict()), 201


@activities_bp.route("/api/activities/<int:activity_id>", methods=["DELETE"])
@login_required
def delete_activity(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    db.session.delete(activity)
    db.session.commit()
    return jsonify({"ok": True})
