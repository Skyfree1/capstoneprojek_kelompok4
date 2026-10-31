from datetime import date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import inspect, text

db = SQLAlchemy()

RT_LIST = ["RT 01", "RT 02", "RT 03"]


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    rt = db.Column(db.String(10), default=RT_LIST[0])


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, default="")
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    quantity = db.Column(db.Integer, default=1)
    owner = db.relationship("User")


class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    borrower_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    returned_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="diajukan")
    quantity = db.Column(db.Integer, default=1)
    risk_prob = db.Column(db.Float)
    risk_label = db.Column(db.String(10))
    created_at = db.Column(db.Date, default=date.today)
    item = db.relationship("Item")
    borrower = db.relationship("User")


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey("loan.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(200), default="")


class Vouch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    voucher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    vouchee_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.Date, default=date.today)
    voucher = db.relationship("User", foreign_keys=[voucher_id])
    vouchee = db.relationship("User", foreign_keys=[vouchee_id])
    __table_args__ = (db.UniqueConstraint("voucher_id", "vouchee_id", name="uq_vouch"),)


def upgrade_schema():
    insp = inspect(db.engine)
    extra = {
        "user": [("rt", f"VARCHAR(10) DEFAULT '{RT_LIST[0]}'")],
        "item": [("is_active", "BOOLEAN DEFAULT 1"), ("quantity", "INTEGER DEFAULT 1")],
        "loan": [("quantity", "INTEGER DEFAULT 1")],
    }
    with db.engine.begin() as conn:
        for table, cols in extra.items():
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols:
                if name not in existing:
                    conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {name} {ddl}'))
