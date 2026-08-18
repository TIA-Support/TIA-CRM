from flask import Blueprint, request, jsonify, session
from sqlalchemy import or_
from models import db, Company, Contact, Deal, Task, Activity, CompanyService, Order, COMPANY_STATUSES, SERVICES
from routes.auth import login_required, can_see_all, current_user_id

companies_bp = Blueprint("companies", __name__)


def _set_services(company, services):
    """Replace a company's service set. Silently drops anything not in the fixed catalogue
    rather than erroring, so a stray/old value in the payload doesn't block the whole save."""
    if services is None:
        return
    CompanyService.query.filter_by(company_id=company.id).delete()
    for s in services:
        if s in SERVICES:
            db.session.add(CompanyService(company_id=company.id, service=s))


@companies_bp.route("/api/companies", methods=["GET"])
@login_required
def list_companies():
    query = Company.query

    if not can_see_all():
        query = query.filter(
            or_(Company.assigned_to == current_user_id(), Company.created_by == current_user_id())
        )

    status = request.args.get("status")
    if status:
        query = query.filter(Company.status == status)

    assigned_to = request.args.get("assigned_to")
    if assigned_to:
        query = query.filter(Company.assigned_to == assigned_to)

    search = request.args.get("search")
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Company.name.ilike(like), Company.industry.ilike(like)))

    service = request.args.get("service")
    if service:
        query = query.join(CompanyService).filter(CompanyService.service == service)

    companies = query.order_by(Company.created_at.desc()).all()

    result = []
    for c in companies:
        d = c.to_dict()
        d["contact_count"] = c.contacts.count()
        d["open_deal_count"] = c.deals.filter(~Deal.stage.in_(["won", "lost"])).count()
        next_task = c.tasks.filter_by(status="pending").order_by("due_date").first()
        d["next_task_due"] = next_task.due_date.isoformat() if next_task and next_task.due_date else None
        result.append(d)
    return jsonify(result)


def _check_visible(company):
    if can_see_all():
        return True
    return company.assigned_to == current_user_id() or company.created_by == current_user_id()


@companies_bp.route("/api/companies/<int:company_id>", methods=["GET"])
@login_required
def get_company(company_id):
    company = Company.query.get_or_404(company_id)
    if not _check_visible(company):
        return jsonify({"error": "You don't have access to this company"}), 403

    d = company.to_dict()
    d["contacts"] = [c.to_dict() for c in company.contacts.order_by(Contact.is_primary.desc(), Contact.name)]
    d["deals"] = [dl.to_dict() for dl in company.deals.order_by(Deal.created_at.desc())]
    d["tasks"] = [t.to_dict() for t in company.tasks.order_by(Task.due_date)]
    d["activities"] = [a.to_dict() for a in company.activities.order_by(Activity.occurred_at.desc())]
    d["orders"] = [o.to_dict() for o in company.orders.order_by(Order.received_at.desc())]
    return jsonify(d)


@companies_bp.route("/api/companies", methods=["POST"])
@login_required
def create_company():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    company = Company(
        name=name,
        industry=data.get("industry"),
        website=data.get("website"),
        source=data.get("source"),
        status=data.get("status") if data.get("status") in COMPANY_STATUSES else "new",
        assigned_to=data.get("assigned_to") or current_user_id(),
        created_by=current_user_id(),
        tender_reference=data.get("tender_reference"),
    )
    db.session.add(company)
    db.session.flush()  # assigns company.id without a full commit, so services can reference it
    _set_services(company, data.get("services"))
    db.session.commit()
    return jsonify(company.to_dict()), 201


@companies_bp.route("/api/companies/<int:company_id>", methods=["PUT"])
@login_required
def update_company(company_id):
    company = Company.query.get_or_404(company_id)
    if not _check_visible(company):
        return jsonify({"error": "You don't have access to this company"}), 403

    data = request.get_json(force=True)
    for field in ["name", "industry", "website", "source", "assigned_to", "tender_reference"]:
        if field in data:
            setattr(company, field, data[field])
    if "status" in data and data["status"] in COMPANY_STATUSES:
        company.status = data["status"]
    if "services" in data:
        _set_services(company, data["services"])

    db.session.commit()
    return jsonify(company.to_dict())


@companies_bp.route("/api/companies/<int:company_id>", methods=["DELETE"])
@login_required
def delete_company(company_id):
    company = Company.query.get_or_404(company_id)
    if not can_see_all() and company.created_by != current_user_id():
        return jsonify({"error": "Only an admin, manager, or the creator can delete this"}), 403
    db.session.delete(company)
    db.session.commit()
    return jsonify({"ok": True})


# ---- Contacts (nested under companies) ----


@companies_bp.route("/api/companies/<int:company_id>/contacts", methods=["POST"])
@login_required
def add_contact(company_id):
    company = Company.query.get_or_404(company_id)
    if not _check_visible(company):
        return jsonify({"error": "You don't have access to this company"}), 403

    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    contact = Contact(
        company_id=company_id, name=name, title=data.get("title"),
        phone=data.get("phone"), email=data.get("email"),
        is_primary=bool(data.get("is_primary")), notes=data.get("notes"),
    )
    if contact.is_primary:
        Contact.query.filter_by(company_id=company_id).update({"is_primary": False})
    db.session.add(contact)
    db.session.commit()
    return jsonify(contact.to_dict()), 201


@companies_bp.route("/api/contacts/<int:contact_id>", methods=["PUT"])
@login_required
def update_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    company = Company.query.get_or_404(contact.company_id)
    if not _check_visible(company):
        return jsonify({"error": "You don't have access to this company"}), 403

    data = request.get_json(force=True)
    for field in ["name", "title", "phone", "email", "notes"]:
        if field in data:
            setattr(contact, field, data[field])
    if data.get("is_primary"):
        Contact.query.filter_by(company_id=contact.company_id).update({"is_primary": False})
        contact.is_primary = True
    db.session.commit()
    return jsonify(contact.to_dict())


@companies_bp.route("/api/contacts/<int:contact_id>", methods=["DELETE"])
@login_required
def delete_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    company = Company.query.get_or_404(contact.company_id)
    if not _check_visible(company):
        return jsonify({"error": "You don't have access to this company"}), 403
    db.session.delete(contact)
    db.session.commit()
    return jsonify({"ok": True})
