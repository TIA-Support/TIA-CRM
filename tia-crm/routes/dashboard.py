from datetime import date, timedelta
from flask import Blueprint, jsonify
from sqlalchemy import func, or_
from models import db, Company, Deal, Task, Activity, User, DEAL_STAGES, COMPANY_STATUSES
from routes.auth import login_required, can_see_all, current_user_id

dashboard_bp = Blueprint("dashboard", __name__)

REMINDER_WINDOW_DAYS = 7  # how far ahead "due soon" looks


def _urgency(due, today):
    if due < today:
        return "overdue"
    if due == today:
        return "today"
    return "soon"


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

    won_count = deal_q.filter(Deal.stage == "won").count()
    lost_count = deal_q.filter(Deal.stage == "lost").count()
    decided = won_count + lost_count
    win_rate = round((won_count / decided) * 100) if decided else 0

    # New leads per weekday, Monday through Friday of the current week — real created_at
    # data, not a fabricated trend line.
    monday = date.today() - timedelta(days=date.today().weekday())
    weekday_labels = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    new_leads_by_weekday = []
    for i, label in enumerate(weekday_labels):
        day = monday + timedelta(days=i)
        day_q = company_q.filter(func.date(Company.created_at) == day)
        new_leads_by_weekday.append({"day": label, "count": day_q.count()})

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
        "won_count": won_count,
        "lost_count": lost_count,
        "win_rate": win_rate,
        "new_leads_by_weekday": new_leads_by_weekday,
        "leaderboard_month": [{"name": n, "calls_made": c} for n, c in leaderboard],
    })


@dashboard_bp.route("/api/dashboard/reminders", methods=["GET"])
@login_required
def reminders():
    """Overdue and upcoming tasks + follow-ups, for the dashboard's 'Needs attention' panel.
    Unlike /summary (which only returns counts), this returns the actual rows so people can
    act on them without navigating away."""
    scoped = not can_see_all()
    uid = current_user_id()
    today = date.today()
    horizon = today + timedelta(days=REMINDER_WINDOW_DAYS)

    task_q = Task.query.filter(
        Task.status == "pending", Task.due_date.isnot(None), Task.due_date <= horizon
    )
    if scoped:
        task_q = task_q.filter(or_(Task.assigned_to == uid, Task.created_by == uid))
    tasks = task_q.order_by(Task.due_date.asc()).all()

    task_list = []
    for t in tasks:
        d = t.to_dict()
        d["urgency"] = _urgency(t.due_date, today)
        task_list.append(d)

    activity_q = Activity.query.filter(
        Activity.next_follow_up.isnot(None), Activity.next_follow_up <= horizon
    )
    if scoped:
        activity_q = activity_q.filter(Activity.user_id == uid)
    followups = activity_q.order_by(Activity.next_follow_up.asc()).all()

    followup_list = []
    for a in followups:
        d = a.to_dict()
        d["company_name"] = a.company.name if a.company else None
        d["urgency"] = _urgency(a.next_follow_up, today)
        followup_list.append(d)

    return jsonify({"tasks": task_list, "followups": followup_list})
