import os
import secrets
from datetime import date, datetime


def _load_env_file(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

from flask import (Flask, render_template, request, redirect, url_for, flash, abort,
                   session, jsonify)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Item, Loan, Review, Vouch, RT_LIST, upgrade_schema
from logic import (CATEGORIES, MAX_QUANTITY, available_qty, booked_peak, mark_overdue,
                   parse_qty, reputation, trust_detail, features_for)
from ml.predict import predict_risk
from graph import connection as graph_conn
from graph import insights

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-ganti-di-produksi")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///sipinjam.db")
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Silakan masuk terlebih dahulu."
app.jinja_env.globals["reputation"] = reputation
app.jinja_env.globals["trust_detail"] = trust_detail

TRUST_BADGE = {"tinggi": "success", "sedang": "warning", "rendah": "danger"}


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


@app.before_request
def check_csrf():
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        if not sent or not secrets.compare_digest(sent, session.get("_csrf", "")):
            abort(400, "Token formulir tidak valid. Muat ulang halaman lalu coba lagi.")


@app.context_processor
def inject_globals():
    return {"csrf_token": csrf_token, "graph_enabled": graph_conn.enabled(),
            "trust_badge": TRUST_BADGE}


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name, email, pw = (request.form[k].strip() for k in ("name", "email", "password"))
        rt = request.form.get("rt", RT_LIST[0])
        if not (name and email and pw):
            flash("Semua kolom wajib diisi.", "danger")
        elif rt not in RT_LIST:
            flash("RT tidak valid.", "danger")
        elif len(pw) < 6:
            flash("Kata sandi minimal 6 karakter.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("Email sudah terdaftar.", "danger")
        else:
            db.session.add(User(name=name, email=email, rt=rt,
                                password_hash=generate_password_hash(pw)))
            db.session.commit()
            flash("Pendaftaran berhasil, silakan masuk.", "success")
            return redirect(url_for("login"))
    return render_template("auth.html", mode="register", rts=RT_LIST)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(email=request.form["email"].strip()).first()
        if u and check_password_hash(u.password_hash, request.form["password"]):
            login_user(u)
            return redirect(url_for("catalog"))
        flash("Email atau kata sandi salah.", "danger")
    return render_template("auth.html", mode="login", rts=RT_LIST)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def catalog():
    q = request.args.get("q", "").strip()
    cat = request.args.get("cat", "")
    query = Item.query.filter(Item.is_active.isnot(False))
    if q:
        query = query.filter(Item.name.ilike(f"%{q}%"))
    if cat in CATEGORIES:
        query = query.filter(Item.category == cat)
    return render_template("catalog.html", items=query.order_by(Item.id.desc()).all(),
                           q=q, cat=cat, categories=CATEGORIES)


@app.route("/items/new", methods=["GET", "POST"])
@login_required
def new_item():
    if request.method == "POST":
        name = request.form["name"].strip()
        category = request.form.get("category", "")
        qty = parse_qty(request.form.get("quantity", 1))
        if not name:
            flash("Nama alat wajib diisi.", "danger")
        elif category not in CATEGORIES:
            flash("Kategori tidak valid.", "danger")
        elif qty is None:
            flash(f"Jumlah harus bilangan bulat 1 - {MAX_QUANTITY}.", "danger")
        else:
            db.session.add(Item(name=name, category=category, quantity=qty,
                                description=request.form["description"].strip(),
                                owner_id=current_user.id))
            db.session.commit()
            flash("Alat berhasil didaftarkan.", "success")
            return redirect(url_for("my_items"))
    return render_template("item_form.html", categories=CATEGORIES, item=None,
                           max_qty=MAX_QUANTITY, min_qty=1)


def _min_quantity_allowed(item):
    today = date.today()
    future = [l.due_date for l in Loan.query.filter(
        Loan.item_id == item.id, Loan.status.in_(("disetujui", "dipinjam", "terlambat")))]
    if not future:
        return 1
    return max(1, booked_peak(item.id, today, max(max(future), today)))


@app.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id):
    item = db.get_or_404(Item, item_id)
    if item.owner_id != current_user.id:
        abort(403)
    min_qty = _min_quantity_allowed(item)
    if request.method == "POST":
        name = request.form["name"].strip()
        category = request.form.get("category", "")
        qty = parse_qty(request.form.get("quantity", 1))
        if not name:
            flash("Nama alat wajib diisi.", "danger")
        elif category not in CATEGORIES:
            flash("Kategori tidak valid.", "danger")
        elif qty is None:
            flash(f"Jumlah harus bilangan bulat 1 - {MAX_QUANTITY}.", "danger")
        elif qty < min_qty:
            flash(f"Jumlah tidak bisa kurang dari {min_qty}: unit sebanyak itu sedang dipinjam "
                  "atau sudah disetujui untuk dipinjam.", "danger")
        else:
            item.name, item.category, item.quantity = name, category, qty
            item.description = request.form["description"].strip()
            db.session.commit()
            flash("Data alat diperbarui.", "success")
            return redirect(url_for("my_items"))
    return render_template("item_form.html", categories=CATEGORIES, item=item,
                           max_qty=MAX_QUANTITY, min_qty=min_qty)


@app.route("/items/mine")
@login_required
def my_items():
    items = Item.query.filter_by(owner_id=current_user.id).order_by(Item.id.desc()).all()
    counts = {i.id: Loan.query.filter(Loan.item_id == i.id,
                                      Loan.status.in_(("dipinjam", "terlambat", "dikembalikan"))).count()
              for i in items}
    return render_template("my_items.html", items=items, counts=counts)


@app.route("/items/<int:item_id>/toggle", methods=["POST"])
@login_required
def toggle_item(item_id):
    item = db.get_or_404(Item, item_id)
    if item.owner_id != current_user.id:
        abort(403)
    item.is_active = not (item.is_active is not False)
    db.session.commit()
    flash(f"{item.name} {'diaktifkan' if item.is_active else 'dinonaktifkan (tidak tampil di katalog)'}.",
          "success")
    return redirect(url_for("my_items"))


@app.route("/loan/<int:item_id>", methods=["GET", "POST"])
@login_required
def request_loan(item_id):
    item = db.get_or_404(Item, item_id)
    if item.owner_id == current_user.id:
        flash("Anda tidak bisa meminjam alat milik sendiri.", "warning")
        return redirect(url_for("catalog"))
    if item.is_active is False:
        flash("Alat ini sedang dinonaktifkan pemiliknya.", "warning")
        return redirect(url_for("catalog"))
    if request.method == "POST":
        qty = parse_qty(request.form.get("quantity", 1))
        try:
            start, due = parse_date(request.form["start"]), parse_date(request.form["due"])
        except ValueError:
            start = due = None
        stock = item.quantity or 1
        if start is None:
            flash("Format tanggal tidak valid.", "danger")
        elif start < date.today() or due < start:
            flash("Tanggal tidak valid (tidak boleh di masa lalu, kembali >= mulai).", "danger")
        elif qty is None or qty > stock:
            flash(f"Jumlah pinjam harus 1 - {stock} (stok yang dimiliki pemilik).", "danger")
        elif available_qty(item, start, due) < qty:
            sisa = available_qty(item, start, due)
            flash(f"Hanya tersisa {sisa} dari {stock} unit pada tanggal itu. "
                  "Kurangi jumlah atau pilih tanggal lain." if sisa else
                  "Semua unit sudah terpesan pada tanggal itu. Pilih tanggal lain.", "danger")
        else:
            prob, label = predict_risk(features_for(current_user.id, item.category, start, due))
            db.session.add(Loan(item_id=item.id, borrower_id=current_user.id,
                                start_date=start, due_date=due, quantity=qty,
                                risk_prob=prob, risk_label=label))
            db.session.commit()
            flash("Pengajuan terkirim, menunggu persetujuan pemilik.", "success")
            return redirect(url_for("my_loans"))
    booked = (Loan.query.filter(Loan.item_id == item.id, Loan.status.in_(("disetujui", "dipinjam", "terlambat")),
                                (Loan.due_date >= date.today()) | (Loan.status == "terlambat"))
              .order_by(Loan.start_date).all())
    return render_template("request_loan.html", item=item, booked=booked,
                           rekomendasi=insights.rekomendasi_barang(item.id))


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
        sisa = available_qty(loan.item, loan.start_date, loan.due_date)
        if (loan.quantity or 1) > sisa:
            flash(f"Tidak bisa disetujui: diminta {loan.quantity} unit, tersisa {sisa} dari "
                  f"{loan.item.quantity or 1} pada tanggal tersebut.", "danger")
            return redirect(url_for("owner"))
        loan.status = "disetujui"
    elif action == "handover" and is_owner and loan.status == "disetujui":
        loan.status = "dipinjam"
    elif action == "return" and is_owner and loan.status in ("dipinjam", "terlambat"):
        loan.status = "dikembalikan"
        loan.returned_date = date.today()
        try:
            rating = min(5, max(1, int(request.form.get("rating", 3))))
        except ValueError:
            rating = 3
        db.session.add(Review(loan_id=loan.id, rating=rating,
                              note=request.form.get("note", "").strip()[:200]))
    else:
        abort(403)
    db.session.commit()
    return redirect(url_for("owner" if is_owner else "my_loans"))


@app.route("/warga")
@login_required
def warga_list():
    rt = request.args.get("rt", "")
    query = User.query
    if rt in RT_LIST:
        query = query.filter(User.rt == rt)
    users = query.order_by(User.rt, User.name).all()
    trust = {u.id: trust_detail(u.id) for u in users}
    return render_template("warga.html", users=users, trust=trust, rts=RT_LIST, rt=rt)


@app.route("/warga/<int:user_id>")
@login_required
def profile(user_id):
    mark_overdue()
    user = db.get_or_404(User, user_id)
    items = Item.query.filter_by(owner_id=user.id, is_active=True).all()
    vouchers = Vouch.query.filter_by(vouchee_id=user.id).all()
    vouchees = Vouch.query.filter_by(voucher_id=user.id).all()
    i_vouch = any(v.voucher_id == current_user.id for v in vouchers)
    history = (Loan.query.filter(Loan.borrower_id == user.id,
                                 Loan.status.in_(("dipinjam", "terlambat", "dikembalikan")))
               .order_by(Loan.start_date.desc()).limit(10).all())
    jalur = insights.jalur_kepercayaan(current_user.id, user.id) if user.id != current_user.id else None
    return render_template("profile.html", user=user, t=trust_detail(user.id), items=items,
                           vouchers=vouchers, vouchees=vouchees, i_vouch=i_vouch,
                           history=history, jalur=jalur)


@app.route("/warga/<int:user_id>/vouch", methods=["POST"])
@login_required
def vouch(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("Anda tidak bisa menjamin diri sendiri.", "warning")
        return redirect(url_for("profile", user_id=user.id))
    existing = Vouch.query.filter_by(voucher_id=current_user.id, vouchee_id=user.id).first()
    if existing:
        db.session.delete(existing)
        flash(f"Jaminan untuk {user.name} dicabut.", "info")
    else:
        db.session.add(Vouch(voucher_id=current_user.id, vouchee_id=user.id))
        flash(f"Anda sekarang menjamin {user.name}. Jaminan dihitung jika reputasi Anda baik.", "success")
    db.session.commit()
    return redirect(url_for("profile", user_id=user.id))


@app.route("/graf")
@login_required
def graph_dashboard():
    data = insights.ringkasan()
    return render_template("graph.html", data=data, error=graph_conn.last_error,
                           report=session.pop("sync_report", None))


@app.route("/graf/sync", methods=["POST"])
@login_required
def graph_sync():
    if not graph_conn.enabled():
        flash("Neo4j belum diatur. Isi NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD lalu jalankan ulang aplikasi.",
              "warning")
        return redirect(url_for("graph_dashboard"))
    from graph.sync import sync
    mark_overdue()
    try:
        rep = sync()
    except Exception as e:
        flash(f"Sinkronisasi gagal: {type(e).__name__}: {e}", "danger")
        return redirect(url_for("graph_dashboard"))
    session["sync_report"] = {"valid": rep["valid"], "validasi": rep["validasi"],
                              "gds_version": rep["gds_version"], "gds_error": rep["gds_error"],
                              "gds": {k: {kk: (round(vv, 4) if isinstance(vv, float) else vv)
                                          for kk, vv in v.items()}
                                      for k, v in (rep["gds"] or {}).items()
                                      if k in ("proyeksi_sosial", "wcc", "louvain", "pagerank")}}
    flash("Sinkronisasi selesai." if rep["valid"] else "Sinkronisasi selesai, tetapi ada jumlah yang tidak cocok.",
          "success" if rep["valid"] else "warning")
    return redirect(url_for("graph_dashboard"))


@app.route("/graf/data.json")
@login_required
def graph_data():
    data = insights.data_visual()
    if data is None:
        users = User.query.all()
        nodes = [{"id": u.id, "nama": u.name, "rt": u.rt, "komunitas": None, "pagerank": None,
                  "trust_score": trust_detail(u.id)["score"]} for u in users]
        edges = [{"dari": v.voucher_id, "ke": v.vouchee_id, "tipe": "MENJAMIN", "kali": None}
                 for v in Vouch.query.all()]
        pairs = {}
        for l in Loan.query.filter(Loan.status.in_(("dipinjam", "terlambat", "dikembalikan"))):
            k = (l.borrower_id, l.item.owner_id)
            pairs[k] = pairs.get(k, 0) + 1
        edges += [{"dari": a, "ke": b, "tipe": "PERNAH_MEMINJAM_DARI", "kali": n}
                  for (a, b), n in pairs.items()]
        data = {"sumber": "SQLite (Neo4j tidak terhubung)", "nodes": nodes, "edges": edges}
    return jsonify(data)


with app.app_context():
    db.create_all()
    upgrade_schema()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1")
