from datetime import datetime, date
from flask import Blueprint, request, jsonify
from sqlalchemy import or_
from models import db, Deal, Company, DEAL_STAGES
from routes.auth import login_required, can_see_all, current_user_id

deals_bp = Blueprint("deals", __name__)


def _visible_deal_query():
    query = Deal.query
    if not can_see_all():
        query = query.filter(or_(Deal.assigned_to == current_user_id(), Deal.created_by == current_user_id()))
    return query


@deals_bp.route("/api/deals", methods=["GET"])
@login_required
def list_deals():
    query = _visible_deal_query()

    stage = request.args.get("stage")
    if stage:
        query = query.filter(Deal.stage == stage)

    company_id = request.args.get("company_id")
    if company_id:
        query = query.filter(Deal.company_id == company_id)

    deals = query.order_by(Deal.created_at.desc()).all()
    return jsonify([d.to_dict(include_company=True) for d in deals])


@deals_bp.route("/api/pipeline", methods=["GET"])
@login_required
def pipeline():
    """Deals grouped by stage, for a kanban-style board. Excludes won/lost by default."""
    query = _visible_deal_query().filter(~Deal.stage.in_(["won", "lost"]))
    deals = query.order_by(Deal.created_at.desc()).all()

    board = {stage: [] for stage in DEAL_STAGES}
    for d in deals:
        board[d.stage].append(d.to_dict(include_company=True))
    return jsonify(board)


@deals_bp.route("/api/deals", methods=["POST"])
@login_required
def create_deal():
    data = request.get_json(force=True)
    title = (data.get("title") or "").strip()
    company_id = data.get("company_id")
    if not title or not company_id:
        return jsonify({"error": "title and company_id are required"}), 400

    company = Company.query.get_or_404(company_id)

    expected_close = None
    if data.get("expected_close_date"):
        expected_close = date.fromisoformat(data["expected_close_date"])

    deal = Deal(
        company_id=company.id,
        title=title,
        stage=data.get("stage") if data.get("stage") in DEAL_STAGES else "lead",
        value=data.get("value"),
        expected_close_date=expected_close,
        assigned_to=data.get("assigned_to") or current_user_id(),
        created_by=current_user_id(),
    )
    db.session.add(deal)
    db.session.commit()
    return jsonify(deal.to_dict()), 201


@deals_bp.route("/api/deals/<int:deal_id>", methods=["PUT"])
@login_required
def update_deal(deal_id):
    deal = Deal.query.get_or_404(deal_id)

    data = request.get_json(force=True)
    if "title" in data:
        deal.title = data["title"]
    if "value" in data:
        deal.value = data["value"]
    if "assigned_to" in data:
        deal.assigned_to = data["assigned_to"]
    if "expected_close_date" in data:
        deal.expected_close_date = date.fromisoformat(data["expected_close_date"]) if data["expected_close_date"] else None
    if "stage" in data and data["stage"] in DEAL_STAGES:
        deal.stage = data["stage"]
        if data["stage"] in ("won", "lost"):
            deal.closed_at = datetime.utcnow()
        else:
            deal.closed_at = None

    db.session.commit()
    return jsonify(deal.to_dict())


@deals_bp.route("/api/deals/<int:deal_id>", methods=["DELETE"])
@login_required
def delete_deal(deal_id):
    deal = Deal.query.get_or_404(deal_id)
    db.session.delete(deal)
    db.session.commit()
    return jsonify({"ok": True})
