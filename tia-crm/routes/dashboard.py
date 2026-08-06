from datetime import date
from flask import Blueprint, jsonify
from sqlalchemy import func, or_
from models import db, Company, Deal, Task, Activity, User, DEAL_STAGES, COMPANY_STATUSES
from routes.auth import login_required, can_see_all, current_user_id

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/api/dashboard/summary", methods=["GET"])
@login_required
def summary():
    scoped = not can_see_all()
    uid = current_user_id()

    company_q = Company.query
    deal_q = Deal.query
    task_q = Task.query
    if scoped:
        company_q = company_q.filter(or_(Company.assigned_to == uid, Company.created_by == uid))
        deal_q = deal_q.filter(or_(Deal.assigned_to == uid, Deal.created_by == uid))
        task_q = task_q.filter(or_(Task.assigned_to == uid, Task.created_by == uid))

    total_companies = company_q.count()

    company_ids = [c.id for c in company_q.all()]
    status_counts = {s: 0 for s in COMPANY_STATUSES}
    status_query = db.session.query(Company.status, func.count(Company.id))
    if scoped:
        status_query = status_query.filter(Company.id.in_(company_ids))
    for status, count in status_query.group_by(Company.status).all():
        status_counts[status] = count

    open_deals = deal_q.filter(~Deal.stage.in_(["won", "lost"]))
    pipeline_value = sum(float(d.value) for d in open_deals if d.value is not None)

    deal_ids = [d.id for d in deal_q.all()]
    stage_counts = {s: 0 for s in DEAL_STAGES}
    stage_query = db.session.query(Deal.stage, func.count(Deal.id))
    if scoped:
        stage_query = stage_query.filter(Deal.id.in_(deal_ids))
    for stage, count in stage_query.group_by(Deal.stage).all():
        stage_counts[stage] = count

    tasks_due_today = task_q.filter(Task.status == "pending", Task.due_date <= date.today()).count()

    calls_today_q = Activity.query.filter(Activity.type == "call", func.date(Activity.occurred_at) == date.today())
    if scoped:
        calls_today_q = calls_today_q.filter(Activity.user_id == uid)
    calls_today = calls_today_q.count()

    followups_due_q = Activity.query.filter(
        Activity.next_follow_up.isnot(None), Activity.next_follow_up <= date.today()
    )
    if scoped:
        followups_due_q = followups_due_q.filter(Activity.user_id == uid)
    followups_due = followups_due_q.count()

    leaderboard = (
        db.session.query(User.name, func.count(Activity.id).label("calls_made"))
        .join(Activity, Activity.user_id == User.id)
        .filter(Activity.type == "call", Activity.occurred_at >= date.today().replace(day=1))
        .group_by(User.id)
        .order_by(func.count(Activity.id).desc())
        .all()
    )

    return jsonify({
        "total_companies": total_companies,
        "status_breakdown": status_counts,
        "pipeline_value": pipeline_value,
        "open_deal_count": open_deals.count(),
        "stage_breakdown": stage_counts,
        "tasks_due_today": tasks_due_today,
        "calls_today": calls_today,
        "followups_due": followups_due,
        "leaderboard_month": [{"name": n, "calls_made": c} for n, c in leaderboard],
    })
