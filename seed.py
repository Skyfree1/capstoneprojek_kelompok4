import random
import sys
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from app import app
from logic import CATEGORIES, borrower_stats
from ml.predict import predict_risk
from models import db, User, Item, Loan, Review, Vouch, RT_LIST

SEED = 2026
N_PER_RT = 15
HISTORY_DAYS = 180

NAMES = [
    "Ahmad Fauzi", "Budi Santoso", "Citra Lestari", "Dedi Kurniawan", "Eka Putri", "Fajar Nugroho",
    "Gita Permata", "Hendra Wijaya", "Indah Sari", "Joko Susilo", "Kartika Dewi", "Lukman Hakim",
    "Maya Anggraini", "Nanda Pratama", "Oki Setiawan", "Putri Ramadhani", "Rahmat Hidayat",
    "Siti Aminah", "Taufik Ismail", "Umi Kalsum", "Vina Maharani", "Wahyu Saputra", "Yuni Astuti",
    "Zainal Abidin", "Agus Salim", "Bayu Firmansyah", "Cahya Ningsih", "Dian Novita", "Endang Wati",
    "Fitri Handayani", "Galih Prakoso", "Hana Safitri", "Irfan Maulana", "Jihan Aulia", "Khairul Anwar",
    "Lina Marlina", "Mira Oktaviani", "Nur Hasanah", "Oscar Siregar", "Pandu Wibowo", "Rina Yulianti",
    "Sandi Pratama", "Tari Wulandari", "Udin Syamsudin", "Wulan Sari",
]

ITEM_POOL = {
    "Alat pesta": {"Tenda 4x6": 2, "Kursi lipat": 60, "Meja panjang": 10, "Sound system kecil": 1,
                   "Dandang besar": 3, "Kompor gas 2 tungku": 2, "Termos nasi": 4, "Karpet masjid": 6,
                   "Lampu hias": 20, "Piring & gelas (set)": 100},
    "Alat pertukangan": {"Bor listrik": 1, "Tangga lipat 3 m": 1, "Gergaji mesin": 1, "Gerinda tangan": 1,
                         "Kunci pipa": 2, "Mesin potong rumput": 1, "Kompresor angin": 1,
                         "Linggis & cangkul": 4},
    "Ruangan/fasilitas": {"Pos ronda": 1, "Balai warga": 1, "Lapangan bulu tangkis": 1,
                          "Mushola (ruang serbaguna)": 1},
    "Lainnya": {"Gerobak dorong": 2, "Kursi roda": 1, "Payung tenda pasar": 3, "Proyektor": 1,
                "Jas hujan ponco": 10, "Ember besar & selang": 3},
}
PARTY = ["Tenda 4x6", "Kursi lipat", "Meja panjang", "Sound system kecil",
         "Termos nasi", "Piring & gelas (set)", "Dandang besar", "Kompor gas 2 tungku"]


def free_units(item, schedule, start, due):
    spans = [(max(s, start), min(e, due), q) for s, e, q in schedule if s <= due and e >= start]
    peak = max((sum(q for s, e, q in spans if s <= d <= e) for d in {s for s, _, _ in spans}), default=0)
    return item.quantity - peak


def pick_qty(rng, item, free):
    if free < 1:
        return 0
    if item.quantity == 1:
        return 1
    return min(free, rng.randint(max(1, item.quantity // 5), item.quantity))


def main():
    if "--reset" not in sys.argv:
        print("Gunakan: python seed.py --reset   (menghapus semua data lalu mengisi data demo)")
        return
    rng = random.Random(SEED)
    today = date.today()
    with app.app_context():
        db.drop_all()
        db.create_all()

        pw = generate_password_hash("warga123")
        users = []
        for i, name in enumerate(NAMES):
            rt = RT_LIST[i // N_PER_RT]
            users.append(User(name=name, email=f"warga{i + 1:02d}@demo.local", password_hash=pw, rt=rt))
        db.session.add_all(users)
        db.session.commit()
        disiplin = {u.id: rng.choice([rng.uniform(0.85, 0.99)] * 3 + [rng.uniform(0.6, 0.85)] * 2
                                      + [rng.uniform(0.3, 0.6)]) for u in users}
        newcomers = {users[i].id for i in (14, 29, 44, 43)}

        items = []
        owners = [u for u in users if u.id not in newcomers]
        for cat, names in ITEM_POOL.items():
            for nm, qty in names.items():
                o = rng.choice(owners)
                items.append(Item(name=nm, category=cat, owner_id=o.id, quantity=qty,
                                  description=f"{nm} milik {o.name.split()[0]}, kondisi baik."))
        db.session.add_all(items)
        db.session.commit()
        by_name = {i.name: i for i in items}
        rt_of = {u.id: u.rt for u in users}
        schedule = {i.id: [] for i in items}
        borrowers = [u for u in users if u.id not in newcomers]

        def pick_item(borrower):
            same_rt = rng.random() < 0.7
            pool = [i for i in items if i.owner_id != borrower.id and
                    (rt_of[i.owner_id] == borrower.rt) == same_rt]
            return rng.choice(pool or [i for i in items if i.owner_id != borrower.id])

        events = []
        for _ in range(170):
            b = rng.choice(borrowers)
            start = today - timedelta(days=rng.randint(5, HISTORY_DAYS))
            dur = rng.randint(1, 5)
            if rng.random() < 0.3:
                bundle = [by_name[n] for n in rng.sample(PARTY, rng.randint(2, 4))
                          if by_name[n].owner_id != b.id]
            else:
                bundle = [pick_item(b)]
            for it in bundle:
                events.append((start, dur, b, it))
        events.sort(key=lambda e: e[0])

        n_loans = 0
        for start, dur, b, it in events:
            due = start + timedelta(days=dur - 1)
            qty = pick_qty(rng, it, free_units(it, schedule[it.id], start, due))
            if qty == 0:
                continue
            lead = rng.randint(0, 14)
            s = borrower_stats(b.id)
            feats = {"n_prev": s["n_prev"], "ontime_rate": s["ontime_rate"], "avg_rating": s["avg_rating"],
                     "duration_days": dur, "lead_days": lead, "is_weekend": int(start.weekday() >= 5),
                     "category_code": CATEGORIES.index(it.category)}
            prob, label = predict_risk(feats)
            created = start - timedelta(days=lead)
            r = rng.random()
            if r < 0.05:
                db.session.add(Loan(item_id=it.id, borrower_id=b.id, start_date=start, due_date=due,
                                    quantity=qty, status="ditolak", risk_prob=prob, risk_label=label, created_at=created))
                db.session.commit()
                continue
            if r < 0.09:
                db.session.add(Loan(item_id=it.id, borrower_id=b.id, start_date=start, due_date=due,
                                    quantity=qty, status="dibatalkan", risk_prob=prob, risk_label=label, created_at=created))
                db.session.commit()
                continue
            on_time = rng.random() < disiplin[b.id]
            delay = 0 if on_time else rng.randint(1, 6)
            returned = due + timedelta(days=delay)
            if due >= today:
                status, returned = "dipinjam", None
            elif returned >= today:
                status, returned = "terlambat", None
            else:
                status = "dikembalikan"
            loan = Loan(item_id=it.id, borrower_id=b.id, start_date=start, due_date=due,
                        quantity=qty, returned_date=returned, status=status, risk_prob=prob, risk_label=label,
                        created_at=created)
            db.session.add(loan)
            db.session.commit()
            schedule[it.id].append((start, returned or max(due, today), qty))
            if status == "dikembalikan":
                base = 5 if delay == 0 else 4 if delay <= 2 else 2
                rating = max(1, min(5, base + rng.choice([0, 0, 0, -1, 1])))
                db.session.add(Review(loan_id=loan.id, rating=rating,
                                      note="" if delay == 0 else f"telat {delay} hari"))
                db.session.commit()
            n_loans += 1

        worst = sorted(borrowers, key=lambda u: disiplin[u.id])[:3]
        for b in worst:
            it = pick_item(b)
            start, due = today - timedelta(days=rng.randint(6, 10)), today - timedelta(days=rng.randint(1, 4))
            qty = pick_qty(rng, it, free_units(it, schedule[it.id], start, today))
            if qty == 0:
                continue
            db.session.add(Loan(item_id=it.id, borrower_id=b.id, start_date=start, due_date=due,
                                quantity=qty, status="terlambat", created_at=start - timedelta(days=2)))
            schedule[it.id].append((start, today, qty))
            n_loans += 1
        db.session.commit()

        for b in rng.sample(borrowers, 4):
            it = pick_item(b)
            start, due = today - timedelta(days=rng.randint(0, 2)), today + timedelta(days=rng.randint(1, 4))
            qty = pick_qty(rng, it, free_units(it, schedule[it.id], start, due))
            if qty == 0:
                continue
            db.session.add(Loan(item_id=it.id, borrower_id=b.id, start_date=start, due_date=due,
                                quantity=qty, status="dipinjam", created_at=start - timedelta(days=1)))
            schedule[it.id].append((start, due, qty))
            n_loans += 1
        db.session.commit()

        for b in rng.sample(borrowers, 6) + [u for u in users if u.id in newcomers][:2]:
            it = pick_item(b)
            start = today + timedelta(days=rng.randint(2, 10))
            due = start + timedelta(days=rng.randint(1, 4))
            qty = pick_qty(rng, it, free_units(it, schedule[it.id], start, due))
            if qty == 0:
                continue
            s = borrower_stats(b.id)
            prob, label = predict_risk({"n_prev": s["n_prev"], "ontime_rate": s["ontime_rate"],
                                        "avg_rating": s["avg_rating"], "duration_days": (due - start).days + 1,
                                        "lead_days": (start - today).days, "is_weekend": int(start.weekday() >= 5),
                                        "category_code": CATEGORIES.index(it.category)})
            db.session.add(Loan(item_id=it.id, borrower_id=b.id, start_date=start, due_date=due,
                                quantity=qty, status="diajukan", risk_prob=prob, risk_label=label))
            n_loans += 1
        db.session.commit()

        pairs = set()
        for u in users:
            k = rng.choice([0, 1, 1, 2, 2, 3])
            same = [v for v in users if v.id != u.id and v.rt == u.rt]
            other = [v for v in users if v.rt != u.rt]
            for _ in range(k):
                pool = same if rng.random() < 0.8 else other
                weights = [disiplin[v.id] ** 3 for v in pool]
                v = rng.choices(pool, weights=weights)[0]
                pairs.add((u.id, v.id))
        for nid in newcomers:
            nb = [v for v in users if v.rt == rt_of[nid] and v.id != nid and v.id not in newcomers]
            for v in rng.sample(nb, 2):
                pairs.add((v.id, nid))
        for a, b in sorted(pairs):
            db.session.add(Vouch(voucher_id=a, vouchee_id=b,
                                 created_at=today - timedelta(days=rng.randint(1, HISTORY_DAYS))))
        db.session.commit()

        print(f"Selesai: {len(users)} warga, {len(items)} alat, {n_loans} peminjaman, "
              f"{Review.query.count()} ulasan, {len(pairs)} penjaminan.")
        print("Login contoh: warga01@demo.local / warga123")


if __name__ == "__main__":
    main()
