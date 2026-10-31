from graph.connection import enabled, safe_run

REAL = "['dipinjam', 'terlambat', 'dikembalikan']"

REL_LABEL = {
    "MENJAMIN": "menjamin",
    "PERNAH_MEMINJAM_DARI": "pernah meminjam dari",
}


def rekomendasi_barang(barang_id, limit=3):
    if not enabled():
        return None
    q = f"""
MATCH (b1:Barang {{barang_id: $id}})<-[:ATAS]-(p1:Peminjaman)<-[:MENGAJUKAN]-(w:Warga)
WHERE p1.status IN {REAL}
WITH b1, collect(DISTINCT w) AS peminjam1
WHERE size(peminjam1) > 0
UNWIND peminjam1 AS w
MATCH (w)-[:MENGAJUKAN]->(p2:Peminjaman)-[:ATAS]->(b2:Barang)
WHERE b2 <> b1 AND b2.aktif AND p2.status IN {REAL}
WITH b1, peminjam1, b2, count(DISTINCT w) AS irisan
MATCH (b2)<-[:ATAS]-(p3:Peminjaman)<-[:MENGAJUKAN]-(w2:Warga)
WHERE p3.status IN {REAL}
WITH b2, irisan, size(peminjam1) AS n1, count(DISTINCT w2) AS n2
RETURN b2.barang_id AS barang_id, b2.nama AS nama, irisan,
       round(toFloat(irisan) / (n1 + n2 - irisan), 2) AS jaccard
ORDER BY jaccard DESC, irisan DESC, nama
LIMIT $limit"""
    return safe_run(q, id=barang_id, limit=limit)


def jalur_kepercayaan(dari_id, ke_id):
    if not enabled() or dari_id == ke_id:
        return None
    q = """
MATCH (a:Warga {warga_id: $a}), (b:Warga {warga_id: $b})
MATCH p = shortestPath((a)-[:MENJAMIN|PERNAH_MEMINJAM_DARI*..4]-(b))
RETURN length(p) AS hop,
       [n IN nodes(p) | n.nama] AS simpul,
       [r IN relationships(p) | {tipe: type(r), dari: startNode(r).nama, ke: endNode(r).nama}] AS relasi"""
    res = safe_run(q, a=dari_id, b=ke_id)
    if res is None:
        return None
    if not res:
        return {"hop": None, "simpul": [], "kalimat": []}
    row = res[0]
    row["kalimat"] = [f"{r['dari']} {REL_LABEL.get(r['tipe'], r['tipe'])} {r['ke']}" for r in row["relasi"]]
    return row


def ringkasan():
    if not enabled():
        return None
    hitung = safe_run("""MATCH (n:PinjamWarga) UNWIND labels(n) AS l
WITH l WHERE l <> 'PinjamWarga' RETURN l AS nama, count(*) AS jumlah ORDER BY nama""")
    if hitung is None:
        return None
    out = {"hitung": hitung}
    out["barang_populer"] = safe_run(f"""
MATCH (b:Barang)<-[:ATAS]-(p:Peminjaman) WHERE p.status IN {REAL}
RETURN b.nama AS nama, b.kategori AS kategori, count(p) AS kali
ORDER BY kali DESC, nama LIMIT 5""") or []
    out["telat_per_rt"] = safe_run(f"""
MATCH (r:RT)<-[:TINGGAL_DI]-(w:Warga)-[:MENGAJUKAN]->(p:Peminjaman)
WHERE p.status IN {REAL}
WITH r, count(p) AS total,
     sum(CASE WHEN p.status = 'terlambat' OR p.telat_hari > 0 THEN 1 ELSE 0 END) AS telat
RETURN r.rt_id AS rt, total, telat, round(100.0 * telat / total, 1) AS persen_telat
ORDER BY rt""") or []
    out["pagerank"] = safe_run("""
MATCH (w:Warga) WHERE w.pagerank IS NOT NULL
OPTIONAL MATCH (p:Warga)-[:MENJAMIN]->(w)
RETURN w.nama AS nama, w.rt AS rt, round(w.pagerank, 3) AS pagerank,
       count(p) AS dijamin_oleh, w.trust_score AS trust_score
ORDER BY pagerank DESC, nama LIMIT 5""") or []
    out["komunitas"] = safe_run("""
MATCH (w:Warga) WHERE w.komunitas IS NOT NULL
WITH w ORDER BY w.nama
WITH w.komunitas AS komunitas, collect(w.nama) AS anggota, collect(w.rt) AS rts
UNWIND rts AS rt
WITH komunitas, anggota, rt, count(*) AS n
ORDER BY komunitas, n DESC
WITH komunitas, anggota, collect(rt + ' (' + toString(n) + ')') AS sebaran_rt
RETURN komunitas, size(anggota) AS ukuran, anggota, sebaran_rt
ORDER BY ukuran DESC""") or []
    out["terisolasi"] = safe_run("""
MATCH (w:Warga)
WHERE NOT EXISTS { MATCH (w)-[:MENJAMIN|PERNAH_MEMINJAM_DARI]-(:Warga) }
RETURN w.nama AS nama, w.rt AS rt ORDER BY nama""") or []
    out["lintas_rt"] = safe_run("""
MATCH (a:Warga)-[r:MENJAMIN|PERNAH_MEMINJAM_DARI]->(b:Warga)
RETURN sum(CASE WHEN a.rt = b.rt THEN 1 ELSE 0 END) AS dalam_rt,
       sum(CASE WHEN a.rt <> b.rt THEN 1 ELSE 0 END) AS lintas_rt""") or []
    return out


def data_visual():
    if not enabled():
        return None
    nodes = safe_run("""MATCH (w:Warga)
RETURN w.warga_id AS id, w.nama AS nama, w.rt AS rt, w.komunitas AS komunitas,
       w.pagerank AS pagerank, w.trust_score AS trust_score""")
    if nodes is None:
        return None
    edges = safe_run("""MATCH (a:Warga)-[r:MENJAMIN|PERNAH_MEMINJAM_DARI]->(b:Warga)
RETURN a.warga_id AS dari, b.warga_id AS ke, type(r) AS tipe, r.kali AS kali""") or []
    return {"sumber": "Neo4j", "nodes": nodes, "edges": edges}
