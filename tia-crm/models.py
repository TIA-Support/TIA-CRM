from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

ROLES = ("admin", "manager", "agent")
COMPANY_STATUSES = ("new", "contacted", "interested", "not_interested", "customer", "do_not_contact")
DEAL_STAGES = ("lead", "qualified", "proposal_sent", "negotiation", "won", "lost")
TASK_STATUSES = ("pending", "done")
ACTIVITY_TYPES = ("call", "email", "meeting", "note")
CALL_OUTCOMES = ("no_answer", "callback", "interested", "not_interested", "converted", "wrong_number")


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="agent")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email, "role": self.role}


class Company(db.Model):
    __tablename__ = "companies"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    industry = db.Column(db.String(120))
    website = db.Column(db.String(255))
    source = db.Column(db.String(120))
    status = db.Column(db.String(30), nullable=False, default="new")
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    tender_reference = db.Column(db.String(120))  # link to a TIA tender/bid reference, optional
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    contacts = db.relationship("Contact", backref="company", cascade="all, delete-orphan", lazy="dynamic")
    deals = db.relationship("Deal", backref="company", cascade="all, delete-orphan", lazy="dynamic")
    activities = db.relationship("Activity", backref="company", cascade="all, delete-orphan", lazy="dynamic")
    tasks = db.relationship("Task", backref="company", cascade="all, delete-orphan", lazy="dynamic")
    assignee = db.relationship("User", foreign_keys=[assigned_to])

    def to_dict(self, include_extra=None):
        d = {
            "id": self.id,
            "name": self.name,
            "industry": self.industry,
            "website": self.website,
            "source": self.source,
            "status": self.status,
            "assigned_to": self.assigned_to,
            "assigned_name": self.assignee.name if self.assignee else None,
            "tender_reference": self.tender_reference,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_extra:
            d.update(include_extra)
        return d


class Contact(db.Model):
    __tablename__ = "contacts"
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    title = db.Column(db.String(120))
    phone = db.Column(db.String(60))
    email = db.Column(db.String(160))
    is_primary = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id, "company_id": self.company_id, "name": self.name, "title": self.title,
            "phone": self.phone, "email": self.email, "is_primary": self.is_primary, "notes": self.notes,
        }


class Deal(db.Model):
    __tablename__ = "deals"
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    stage = db.Column(db.String(30), nullable=False, default="lead")
    value = db.Column(db.Numeric(12, 2))
    expected_close_date = db.Column(db.Date)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime)

    assignee = db.relationship("User", foreign_keys=[assigned_to])

    def to_dict(self, include_company=False):
        d = {
            "id": self.id, "company_id": self.company_id, "title": self.title, "stage": self.stage,
            "value": float(self.value) if self.value is not None else None,
            "expected_close_date": self.expected_close_date.isoformat() if self.expected_close_date else None,
            "assigned_to": self.assigned_to,
            "assigned_name": self.assignee.name if self.assignee else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_company and self.company:
            d["company_name"] = self.company.name
        return d


class Task(db.Model):
    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    status = db.Column(db.String(20), nullable=False, default="pending")
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"))
    deal_id = db.Column(db.Integer, db.ForeignKey("deals.id"))
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assignee = db.relationship("User", foreign_keys=[assigned_to])
    deal = db.relationship("Deal")

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "description": self.description,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status, "company_id": self.company_id,
            "company_name": self.company.name if self.company_id and self.company else None,
            "deal_id": self.deal_id,
            "deal_title": self.deal.title if self.deal_id and self.deal else None,
            "assigned_to": self.assigned_to,
            "assigned_name": self.assignee.name if self.assignee else None,
        }


class Activity(db.Model):
    """Unified timeline entry: a call, email, meeting, or free-form note against a company."""
    __tablename__ = "activities"
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id"))
    deal_id = db.Column(db.Integer, db.ForeignKey("deals.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type = db.Column(db.String(20), nullable=False, default="note")
    outcome = db.Column(db.String(30))  # only meaningful when type == "call"
    notes = db.Column(db.Text)
    next_follow_up = db.Column(db.Date)
    occurred_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")
    contact = db.relationship("Contact")

    def to_dict(self):
        return {
            "id": self.id, "company_id": self.company_id, "contact_id": self.contact_id,
            "contact_name": self.contact.name if self.contact else None,
            "deal_id": self.deal_id, "type": self.type, "outcome": self.outcome,
            "notes": self.notes,
            "next_follow_up": self.next_follow_up.isoformat() if self.next_follow_up else None,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "user_id": self.user_id, "user_name": self.user.name if self.user else None,
        }
