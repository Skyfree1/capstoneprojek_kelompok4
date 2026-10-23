from datetime import date
from models import db, Loan, Review

BLOCKING = ("disetujui", "dipinjam", "terlambat")
CATEGORIES = ["Alat pesta", "Alat pertukangan", "Ruangan/fasilitas", "Lainnya"]


def has_conflict(item_id, start, due):
    """Bentrok jika rentang tanggal baru beririsan dengan peminjaman aktif lain."""
    return Loan.query.filter(
        Loan.item_id == item_id,
        Loan.status.in_(BLOCKING),
        Loan.start_date <= due,
        Loan.due_date >= start,
    ).first() is not None


def mark_overdue():
    for l in Loan.query.filter(Loan.status == "dipinjam", Loan.due_date < date.today()):
        l.status = "terlambat"
    db.session.commit()


def borrower_stats(user_id):
    loans = Loan.query.filter_by(borrower_id=user_id, status="dikembalikan").all()
    n = len(loans)
    if n == 0:  # peminjam baru: nilai netral
        return {"n_prev": 0, "ontime_rate": 0.5, "avg_rating": 3.0}
    ontime = sum(1 for l in loans if l.returned_date <= l.due_date) / n
    ratings = [r.rating for r in Review.query.filter(Review.loan_id.in_([l.id for l in loans]))]
    avg = sum(ratings) / len(ratings) if ratings else 3.0
    return {"n_prev": n, "ontime_rate": ontime, "avg_rating": avg}


def reputation(user_id):
    """Skor 0-100 = 50% rating + 50% ketepatan waktu. None jika belum ada riwayat."""
    s = borrower_stats(user_id)
    if s["n_prev"] == 0:
        return None
    return round(50 * s["avg_rating"] / 5 + 50 * s["ontime_rate"])


def features_for(borrower_id, category, start, due):
    s = borrower_stats(borrower_id)
    return {
        **s,
        "duration_days": (due - start).days + 1,
        "lead_days": (start - date.today()).days,
        "is_weekend": int(start.weekday() >= 5),
        "category_code": CATEGORIES.index(category) if category in CATEGORIES else 3,
    }
