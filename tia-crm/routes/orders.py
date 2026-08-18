from datetime import date
from flask import Blueprint, request, jsonify
from sqlalchemy import or_
from models import db, Order, ORDER_STATUSES
from routes.auth import login_required, can_see_all, current_user_id

orders_bp = Blueprint("orders", __name__)


@orders_bp.route("/api/orders", methods=["GET"])
@login_required
def list_orders():
    query = Order.query
    if not can_see_all():
        query = query.filter(or_(Order.assigned_to == current_user_id(), Order.created_by == current_user_id()))

    status = request.args.get("status")
    if status:
        query = query.filter(Order.status == status)

    service = request.args.get("service")
    if service:
        query = query.filter(Order.service == service)

    company_id = request.args.get("company_id")
    if company_id:
        query = query.filter(Order.company_id == company_id)

    orders = query.order_by(Order.received_at.desc().nullslast(), Order.created_at.desc()).all()
    return jsonify([o.to_dict() for o in orders])


@orders_bp.route("/api/orders", methods=["POST"])
@login_required
def create_order():
    data = request.get_json(force=True)
    description = (data.get("description") or "").strip()
    company_id = data.get("company_id")
    if not description:
        return jsonify({"error": "description is required"}), 400
    if not company_id:
        return jsonify({"error": "company_id is required"}), 400

    order = Order(
        company_id=company_id,
        reference=data.get("reference"),
        service=data.get("service") if data.get("service") else None,
        description=description,
        quantity=int(data["quantity"]) if data.get("quantity") not in (None, "") else 1,
        value=data.get("value") or None,
        status=data.get("status") if data.get("status") in ORDER_STATUSES else "received",
        received_at=date.fromisoformat(data["received_at"]) if data.get("received_at") else date.today(),
        dispatched_at=date.fromisoformat(data["dispatched_at"]) if data.get("dispatched_at") else None,
        assigned_to=data.get("assigned_to") or current_user_id(),
        created_by=current_user_id(),
    )
    db.session.add(order)
    db.session.commit()
    return jsonify(order.to_dict()), 201


@orders_bp.route("/api/orders/<int:order_id>", methods=["PUT"])
@login_required
def update_order(order_id):
    order = Order.query.get_or_404(order_id)
    data = request.get_json(force=True)

    for field in ["reference", "service", "description", "assigned_to"]:
        if field in data:
            setattr(order, field, data[field])
    if "quantity" in data:
        order.quantity = int(data["quantity"]) if data["quantity"] not in (None, "") else 1
    if "value" in data:
        order.value = data["value"] or None
    if "received_at" in data:
        order.received_at = date.fromisoformat(data["received_at"]) if data["received_at"] else None
    if "dispatched_at" in data:
        order.dispatched_at = date.fromisoformat(data["dispatched_at"]) if data["dispatched_at"] else None
    if "status" in data and data["status"] in ORDER_STATUSES:
        order.status = data["status"]
        # convenience: flipping to "dispatched" stamps the date if one wasn't set explicitly
        if order.status == "dispatched" and not order.dispatched_at and "dispatched_at" not in data:
            order.dispatched_at = date.today()

    db.session.commit()
    return jsonify(order.to_dict())


@orders_bp.route("/api/orders/<int:order_id>", methods=["DELETE"])
@login_required
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)
    db.session.delete(order)
    db.session.commit()
    return jsonify({"ok": True})
