from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Item, Loan, Review
from logic import CATEGORIES, has_conflict, mark_overdue, reputation, features_for
from ml.predict import predict_risk

app = Flask(__name__)
app.config["SECRET_KEY"] = "ganti-dengan-kunci-rahasia"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sipinjam.db"
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
app.jinja_env.globals["reputation"] = reputation


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


# ---------- Autentikasi ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name, email, pw = (request.form[k].strip() for k in ("name", "email", "password"))
        if not (name and email and pw):
            flash("Semua kolom wajib diisi.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("Email sudah terdaftar.", "danger")
        else:
            db.session.add(User(name=name, email=email, password_hash=generate_password_hash(pw)))
            db.session.commit()
            flash("Pendaftaran berhasil, silakan masuk.", "success")
            return redirect(url_for("login"))
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(email=request.form["email"].strip()).first()
        if u and check_password_hash(u.password_hash, request.form["password"]):
            login_user(u)
            return redirect(url_for("catalog"))
        flash("Email atau kata sandi salah.", "danger")
    return render_template("auth.html", mode="login")


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------- Katalog ----------
@app.route("/")
@login_required
def catalog():
    q = request.args.get("q", "").strip()
    query = Item.query
    if q:
        query = query.filter(Item.name.ilike(f"%{q}%"))
    return render_template("catalog.html", items=query.order_by(Item.id.desc()).all(), q=q)


@app.route("/items/new", methods=["GET", "POST"])
@login_required
def new_item():
    if request.method == "POST":
        name = request.form["name"].strip()
        if not name:
            flash("Nama alat wajib diisi.", "danger")
        else:
            db.session.add(Item(name=name, category=request.form["category"],
                                description=request.form["description"].strip(),
                                owner_id=current_user.id))
            db.session.commit()
            flash("Alat berhasil didaftarkan.", "success")
            return redirect(url_for("catalog"))
    return render_template("item_form.html", categories=CATEGORIES)


# ---------- Pengajuan peminjaman ----------
@app.route("/loan/<int:item_id>", methods=["GET", "POST"])
@login_required
def request_loan(item_id):
    item = db.get_or_404(Item, item_id)
    if item.owner_id == current_user.id:
        flash("Anda tidak bisa meminjam alat milik sendiri.", "warning")
        return redirect(url_for("catalog"))
    if request.method == "POST":
        try:
            start, due = parse_date(request.form["start"]), parse_date(request.form["due"])
        except ValueError:
            flash("Format tanggal tidak valid.", "danger")
            return render_template("request_loan.html", item=item)
        if start < date.today() or due < start:
            flash("Tanggal tidak valid (tidak boleh di masa lalu, kembali >= mulai).", "danger")
        elif has_conflict(item.id, start, due):
            flash("Tanggal bentrok dengan peminjaman lain. Pilih tanggal berbeda.", "danger")
        else:
            prob, label = predict_risk(features_for(current_user.id, item.category, start, due))
            db.session.add(Loan(item_id=item.id, borrower_id=current_user.id,
                                start_date=start, due_date=due,
                                risk_prob=prob, risk_label=label))
            db.session.commit()
            flash("Pengajuan terkirim, menunggu persetujuan pemilik.", "success")
            return redirect(url_for("my_loans"))
    return render_template("request_loan.html", item=item)


@app.route("/my-loans")
@login_required
def my_loans():
    mark_overdue()
    loans = Loan.query.filter_by(borrower_id=current_user.id).order_by(Loan.id.desc()).all()
    return render_template("my_loans.html", loans=loans)


@app.route("/owner")
@login_required
def owner():
    mark_overdue()
    loans = (Loan.query.join(Item).filter(Item.owner_id == current_user.id)
             .order_by(Loan.id.desc()).all())
    return render_template("owner.html", loans=loans)


# ---------- Aksi status ----------
@app.route("/loan/<int:loan_id>/<action>", methods=["POST"])
@login_required
def loan_action(loan_id, action):
    loan = db.get_or_404(Loan, loan_id)
    is_owner = loan.item.owner_id == current_user.id
    is_borrower = loan.borrower_id == current_user.id

    if action == "cancel" and is_borrower and loan.status == "diajukan":
        loan.status = "dibatalkan"
    elif action == "reject" and is_owner and loan.status == "diajukan":
        loan.status = "ditolak"
    elif action == "approve" and is_owner and loan.status == "diajukan":
        if has_conflict(loan.item_id, loan.start_date, loan.due_date):
            flash("Tidak bisa disetujui: bentrok dengan peminjaman lain.", "danger")
            return redirect(url_for("owner"))
        loan.status = "disetujui"
    elif action == "handover" and is_owner and loan.status == "disetujui":
        loan.status = "dipinjam"
    elif action == "return" and is_owner and loan.status in ("dipinjam", "terlambat"):
        loan.status = "dikembalikan"
        loan.returned_date = date.today()
        rating = min(5, max(1, int(request.form.get("rating", 3))))
        db.session.add(Review(loan_id=loan.id, rating=rating,
                              note=request.form.get("note", "")[:200]))
    else:
        abort(403)
    db.session.commit()
    return redirect(url_for("owner" if is_owner else "my_loans"))


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
