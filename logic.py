from datetime import date
from models import db, Item, Loan, Review, Vouch

BLOCKING = ("disetujui", "dipinjam", "terlambat")
CATEGORIES = ["Alat pesta", "Alat pertukangan", "Ruangan/fasilitas", "Lainnya"]

TRUST_W_REPUTASI = 0.8
TRUST_W_PENJAMIN = 0.2
PENJAMIN_MIN_REP = 70
PENJAMIN_MAKS = 3
REPUTASI_NETRAL = 50


MAX_QUANTITY = 10000


def booked_peak(item_id, start, due, exclude_loan_id=None):
    today = date.today()
    loans = Loan.query.filter(Loan.item_id == item_id, Loan.status.in_(BLOCKING),
                              Loan.start_date <= due).all()
    spans = []
    for l in loans:
        end = max(l.due_date, today) if l.status == "terlambat" else l.due_date
        if l.id == exclude_loan_id or end < start:
            continue
        spans.append((max(l.start_date, start), min(end, due), l.quantity or 1))
    return max((sum(q for s, e, q in spans if s <= d <= e) for d in {s for s, _, _ in spans}),
               default=0)


def available_qty(item, start, due, exclude_loan_id=None):
    return max(0, (item.quantity or 1) - booked_peak(item.id, start, due, exclude_loan_id))


def has_conflict(item_id, start, due, qty=1):
    item = db.session.get(Item, item_id)
    return available_qty(item, start, due) < qty


def parse_qty(value, default=1):
    try:
        n = int(str(value).strip() or default)
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= MAX_QUANTITY else None


def mark_overdue():
    today = date.today()
    for l in Loan.query.filter(Loan.status == "dipinjam", Loan.due_date < today):
        l.status = "terlambat"
    for l in Loan.query.filter(Loan.status == "disetujui", Loan.due_date < today):
        l.status = "dibatalkan"
    db.session.commit()


def _is_late_now(loan, today):
    return loan.status in ("dipinjam", "terlambat") and loan.due_date < today


def borrower_stats(user_id):
    today = date.today()
    loans = Loan.query.filter(Loan.borrower_id == user_id,
                              Loan.status.in_(("dikembalikan", "dipinjam", "terlambat"))).all()
    returned = [l for l in loans if l.status == "dikembalikan"]
    late_now = [l for l in loans if _is_late_now(l, today)]
    n = len(returned) + len(late_now)
    if n == 0:
        return {"n_prev": 0, "ontime_rate": 0.5, "avg_rating": 3.0, "late_now": 0}
    ontime = sum(1 for l in returned if l.returned_date <= l.due_date) / n
    ratings = [r.rating for r in Review.query.filter(Review.loan_id.in_([l.id for l in returned]))]
    avg = sum(ratings) / len(ratings) if ratings else 3.0
    return {"n_prev": n, "ontime_rate": ontime, "avg_rating": avg, "late_now": len(late_now)}


def reputation(user_id):
    s = borrower_stats(user_id)
    if s["n_prev"] == 0:
        return None
    return round(50 * s["avg_rating"] / 5 + 50 * s["ontime_rate"])


def trust_detail(user_id):
    s = borrower_stats(user_id)
    rep = reputation(user_id)
    rep_used = REPUTASI_NETRAL if rep is None else rep

    vouches = Vouch.query.filter_by(vouchee_id=user_id).all()
    good, problem = [], []
    for v in vouches:
        r = reputation(v.voucher_id)
        if borrower_stats(v.voucher_id)["late_now"] > 0:
            problem.append(v.voucher.name)
        elif r is not None and r >= PENJAMIN_MIN_REP:
            good.append(v.voucher.name)
    dukungan = round(100 * min(len(good), PENJAMIN_MAKS) / PENJAMIN_MAKS)
    score = round(TRUST_W_REPUTASI * rep_used + TRUST_W_PENJAMIN * dukungan)

    reasons = []
    if rep is None:
        reasons.append(f"Belum punya riwayat pinjam, mulai dari reputasi netral {REPUTASI_NETRAL}.")
    else:
        done = s["n_prev"]
        reasons.append(f"{done} pinjaman tercatat, {round(100 * s['ontime_rate'])}% tepat waktu.")
        reasons.append(f"Rata-rata rating dari pemilik alat {s['avg_rating']:.1f}/5.")
    if s["late_now"]:
        reasons.append(f"{s['late_now']} pinjaman sedang terlambat dan belum dikembalikan.")
    if good:
        reasons.append(f"Dijamin {len(good)} warga bereputasi baik: {', '.join(good)}.")
    elif vouches:
        reasons.append("Punya penjamin, tetapi belum ada yang bereputasi >= "
                       f"{PENJAMIN_MIN_REP} (tidak menambah skor).")
    else:
        reasons.append("Belum ada warga yang menjamin.")
    if problem:
        reasons.append(f"Perhatian: penjamin {', '.join(problem)} sedang punya pinjaman terlambat.")

    label = "tinggi" if score >= 75 else "sedang" if score >= 50 else "rendah"
    return {"score": score, "label": label, "reputasi": rep, "dukungan": dukungan,
            "penjamin_baik": len(good), "penjamin_total": len(vouches),
            "is_new": rep is None, "reasons": reasons}


def features_for(borrower_id, category, start, due):
    s = borrower_stats(borrower_id)
    return {
        "n_prev": s["n_prev"], "ontime_rate": s["ontime_rate"], "avg_rating": s["avg_rating"],
        "duration_days": (due - start).days + 1,
        "lead_days": (start - date.today()).days,
        "is_weekend": int(start.weekday() >= 5),
        "category_code": CATEGORIES.index(category) if category in CATEGORIES else 3,
    }
