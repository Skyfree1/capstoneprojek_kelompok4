from collections import Counter

from models import User, Item, Loan, Review, Vouch, RT_LIST
from logic import reputation, trust_detail

REAL_LOAN_STATUS = ("dipinjam", "terlambat", "dikembalikan")


def collect_rows():
    users = User.query.order_by(User.id).all()
    items = Item.query.order_by(Item.id).all()
    loans = Loan.query.order_by(Loan.id).all()
    reviews = {r.loan_id: r for r in Review.query.all()}
    vouches = Vouch.query.order_by(Vouch.id).all()

    rts = sorted(set(RT_LIST) | {u.rt for u in users if u.rt})
    warga = []
    for u in users:
        t = trust_detail(u.id)
        warga.append({"warga_id": u.id, "nama": u.name, "rt_id": u.rt or RT_LIST[0],
                      "reputasi": reputation(u.id), "trust_score": t["score"]})

    barang = [{"barang_id": i.id, "nama": i.name, "kategori": i.category, "jumlah": i.quantity or 1,
               "pemilik_id": i.owner_id, "aktif": bool(i.is_active if i.is_active is not None else True)}
              for i in items]
    kategori = sorted({i.category for i in items})

    peminjaman = []
    for l in loans:
        r = reviews.get(l.id)
        telat = None
        if l.returned_date is not None:
            telat = max(0, (l.returned_date - l.due_date).days)
        peminjaman.append({
            "peminjaman_id": l.id, "peminjam_id": l.borrower_id, "barang_id": l.item_id,
            "tgl_mulai": l.start_date, "tgl_jatuh_tempo": l.due_date,
            "tgl_kembali": l.returned_date, "status": l.status, "telat_hari": telat,
            "jumlah": l.quantity or 1,
            "rating": r.rating if r else None, "risiko": l.risk_prob, "label_risiko": l.risk_label,
        })

    penjaminan = [{"penjamin_id": v.voucher_id, "dijamin_id": v.vouchee_id, "sejak": v.created_at}
                  for v in vouches]

    owner_of = {i.id: i.owner_id for i in items}
    pairs = Counter((l.borrower_id, owner_of[l.item_id]) for l in loans
                    if l.status in REAL_LOAN_STATUS and l.item_id in owner_of)
    interaksi = [{"peminjam_id": a, "pemilik_id": b, "kali": n} for (a, b), n in sorted(pairs.items())]

    return {"rt": [{"rt_id": r} for r in rts], "warga": warga, "kategori": [{"nama": k} for k in kategori],
            "barang": barang, "peminjaman": peminjaman, "penjaminan": penjaminan,
            "interaksi": interaksi}


def expected_counts(rows):
    return {
        "RT": len(rows["rt"]), "Warga": len(rows["warga"]), "Kategori": len(rows["kategori"]),
        "Barang": len(rows["barang"]), "Peminjaman": len(rows["peminjaman"]),
        "TINGGAL_DI": len(rows["warga"]), "MEMILIKI": len(rows["barang"]),
        "TERMASUK": len(rows["barang"]), "MENGAJUKAN": len(rows["peminjaman"]),
        "ATAS": len(rows["peminjaman"]), "MENJAMIN": len(rows["penjaminan"]),
        "PERNAH_MEMINJAM_DARI": len(rows["interaksi"]),
    }
