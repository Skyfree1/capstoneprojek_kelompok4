from datetime import date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, default="")
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    owner = db.relationship("User")


class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    borrower_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    returned_date = db.Column(db.Date)
    # diajukan -> disetujui/ditolak/dibatalkan -> dipinjam -> terlambat -> dikembalikan
    status = db.Column(db.String(20), default="diajukan")
    risk_prob = db.Column(db.Float)
    risk_label = db.Column(db.String(10))
    created_at = db.Column(db.Date, default=date.today)
    item = db.relationship("Item")
    borrower = db.relationship("User")


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey("loan.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5, diberikan pemilik ke peminjam
    note = db.Column(db.String(200), default="")
