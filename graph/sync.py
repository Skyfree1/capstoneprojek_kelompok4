from graph.connection import run
from graph.extract import collect_rows, expected_counts

CONSTRAINTS = [
    "CREATE CONSTRAINT pw_warga_id IF NOT EXISTS FOR (w:Warga) REQUIRE w.warga_id IS UNIQUE",
    "CREATE CONSTRAINT pw_rt_id IF NOT EXISTS FOR (r:RT) REQUIRE r.rt_id IS UNIQUE",
    "CREATE CONSTRAINT pw_barang_id IF NOT EXISTS FOR (b:Barang) REQUIRE b.barang_id IS UNIQUE",
    "CREATE CONSTRAINT pw_kategori_nama IF NOT EXISTS FOR (k:Kategori) REQUIRE k.nama IS UNIQUE",
    "CREATE CONSTRAINT pw_peminjaman_id IF NOT EXISTS FOR (p:Peminjaman) REQUIRE p.peminjaman_id IS UNIQUE",
]
INDEXES = [
    "CREATE INDEX pw_peminjaman_status IF NOT EXISTS FOR (p:Peminjaman) ON (p.status)",
]

CLEAR = "MATCH (n:PinjamWarga) DETACH DELETE n"

LOAD_NODES = [
    ("rt", """UNWIND $rows AS row
MERGE (r:PinjamWarga:RT {rt_id: row.rt_id})
SET r.nama = row.rt_id"""),
    ("kategori", """UNWIND $rows AS row
MERGE (:PinjamWarga:Kategori {nama: row.nama})"""),
    ("warga", """UNWIND $rows AS row
MERGE (w:PinjamWarga:Warga {warga_id: row.warga_id})
SET w.nama = row.nama, w.rt = row.rt_id,
    w.reputasi = row.reputasi, w.trust_score = row.trust_score"""),
    ("barang", """UNWIND $rows AS row
MERGE (b:PinjamWarga:Barang {barang_id: row.barang_id})
SET b.nama = row.nama, b.kategori = row.kategori, b.aktif = row.aktif,
    b.jumlah = row.jumlah"""),
    ("peminjaman", """UNWIND $rows AS row
MERGE (p:PinjamWarga:Peminjaman {peminjaman_id: row.peminjaman_id})
SET p.tgl_mulai = row.tgl_mulai, p.tgl_jatuh_tempo = row.tgl_jatuh_tempo,
    p.tgl_kembali = row.tgl_kembali, p.status = row.status, p.jumlah = row.jumlah,
    p.telat_hari = row.telat_hari, p.rating = row.rating,
    p.risiko = row.risiko, p.label_risiko = row.label_risiko"""),
]

LOAD_RELS = [
    ("warga", """UNWIND $rows AS row
MATCH (w:Warga {warga_id: row.warga_id})
MATCH (r:RT {rt_id: row.rt_id})
MERGE (w)-[:TINGGAL_DI]->(r)"""),
    ("barang", """UNWIND $rows AS row
MATCH (w:Warga {warga_id: row.pemilik_id})
MATCH (b:Barang {barang_id: row.barang_id})
MATCH (k:Kategori {nama: row.kategori})
MERGE (w)-[:MEMILIKI]->(b)
MERGE (b)-[:TERMASUK]->(k)"""),
    ("peminjaman", """UNWIND $rows AS row
MATCH (w:Warga {warga_id: row.peminjam_id})
MATCH (p:Peminjaman {peminjaman_id: row.peminjaman_id})
MATCH (b:Barang {barang_id: row.barang_id})
MERGE (w)-[:MENGAJUKAN]->(p)
MERGE (p)-[:ATAS]->(b)"""),
    ("penjaminan", """UNWIND $rows AS row
MATCH (a:Warga {warga_id: row.penjamin_id})
MATCH (b:Warga {warga_id: row.dijamin_id})
MERGE (a)-[r:MENJAMIN]->(b)
SET r.sejak = row.sejak"""),
    ("interaksi", """UNWIND $rows AS row
MATCH (a:Warga {warga_id: row.peminjam_id})
MATCH (b:Warga {warga_id: row.pemilik_id})
MERGE (a)-[r:PERNAH_MEMINJAM_DARI]->(b)
SET r.kali = row.kali"""),
]

VALIDATE_NODES = """MATCH (n:PinjamWarga) UNWIND labels(n) AS l
WITH l WHERE l <> 'PinjamWarga'
RETURN l AS nama, count(*) AS jumlah"""
VALIDATE_RELS = """MATCH (:PinjamWarga)-[r]->(:PinjamWarga)
RETURN type(r) AS nama, count(*) AS jumlah"""

GDS_STEPS = [
    ("drop_sosial", "CALL gds.graph.drop('pwSosial', false) YIELD graphName RETURN graphName"),
    ("proyeksi_sosial", """CALL gds.graph.project('pwSosial', 'Warga',
  {MENJAMIN: {orientation: 'UNDIRECTED'}, PERNAH_MEMINJAM_DARI: {orientation: 'UNDIRECTED'}})
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount"""),
    ("wcc", """CALL gds.wcc.write('pwSosial', {writeProperty: 'komponen', concurrency: 1})
YIELD componentCount RETURN componentCount"""),
    ("louvain", """CALL gds.louvain.write('pwSosial', {writeProperty: 'komunitas', concurrency: 1})
YIELD communityCount, modularity RETURN communityCount, modularity"""),
    ("degree", """CALL gds.degree.write('pwSosial', {writeProperty: 'derajat'})
YIELD nodePropertiesWritten RETURN nodePropertiesWritten"""),
    ("drop_penjamin", "CALL gds.graph.drop('pwPenjamin', false) YIELD graphName RETURN graphName"),
    ("proyeksi_penjamin", """CALL gds.graph.project('pwPenjamin', 'Warga', {MENJAMIN: {orientation: 'NATURAL'}})
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount"""),
    ("pagerank", """CALL gds.pageRank.write('pwPenjamin',
  {writeProperty: 'pagerank', maxIterations: 20, dampingFactor: 0.85, concurrency: 1})
YIELD nodePropertiesWritten, ranIterations RETURN nodePropertiesWritten, ranIterations"""),
    ("bersihkan_1", "CALL gds.graph.drop('pwSosial', false) YIELD graphName RETURN graphName"),
    ("bersihkan_2", "CALL gds.graph.drop('pwPenjamin', false) YIELD graphName RETURN graphName"),
]


def gds_version():
    try:
        return run("RETURN gds.version() AS v")[0]["v"]
    except Exception:
        return None


def run_gds():
    out = {}
    for name, q in GDS_STEPS:
        res = run(q)
        out[name] = res[0] if res else {}
    return out


def sync(with_gds=True):
    rows = collect_rows()
    for q in CONSTRAINTS + INDEXES:
        run(q)
    run(CLEAR)
    for key, q in LOAD_NODES:
        if rows[key]:
            run(q, rows=rows[key])
    for key, q in LOAD_RELS:
        if rows[key]:
            run(q, rows=rows[key])

    expected = expected_counts(rows)
    actual = {r["nama"]: r["jumlah"] for r in run(VALIDATE_NODES) + run(VALIDATE_RELS)}
    check = [{"elemen": k, "harapan": v, "aktual": actual.get(k, 0), "ok": actual.get(k, 0) == v}
             for k, v in expected.items()]

    report = {"validasi": check, "valid": all(c["ok"] for c in check),
              "gds_version": None, "gds": None, "gds_error": None}
    if with_gds:
        report["gds_version"] = gds_version()
        if report["gds_version"]:
            try:
                report["gds"] = run_gds()
            except Exception as e:
                report["gds_error"] = f"{type(e).__name__}: {e}"
    return report


if __name__ == "__main__":
    from app import app

    with app.app_context():
        rep = sync()
    print("Validasi import (harapan = jumlah di SQLite):")
    for c in rep["validasi"]:
        print(f"  {'OK ' if c['ok'] else 'BEDA'} {c['elemen']:<22} harapan={c['harapan']:<5} aktual={c['aktual']}")
    if rep["gds_version"]:
        print(f"GDS {rep['gds_version']}:", rep["gds"] or rep["gds_error"])
    else:
        print("GDS tidak terpasang: analitik komunitas/PageRank dilewati.")
