MATCH (w:Warga)-[:TINGGAL_DI]->(r:RT {rt_id: 'RT 02'})
RETURN w.warga_id AS id, w.nama AS nama, w.trust_score AS trust_score
ORDER BY nama;

MATCH (p:Peminjaman)-[:ATAS]->(b:Barang)
WHERE p.status IN ['dipinjam', 'terlambat', 'dikembalikan']
RETURN b.nama AS barang, b.kategori AS kategori, count(p) AS kali_dipinjam,
       sum(p.jumlah) AS total_unit_dipinjam, b.jumlah AS stok
ORDER BY kali_dipinjam DESC, barang LIMIT 5;

MATCH (w:Warga)-[:MENGAJUKAN]->(p:Peminjaman {status: 'terlambat'})-[:ATAS]->(b:Barang)<-[:MEMILIKI]-(o:Warga)
RETURN w.nama AS peminjam, b.nama AS barang, o.nama AS pemilik,
       p.tgl_jatuh_tempo AS jatuh_tempo
ORDER BY jatuh_tempo;

MATCH (p:Peminjaman {status: 'dikembalikan'})-[:ATAS]->(:Barang)-[:TERMASUK]->(k:Kategori)
RETURN k.nama AS kategori, count(p) AS selesai,
       round(avg(p.rating), 2) AS rata_rating,
       round(100.0 * sum(CASE WHEN p.telat_hari = 0 THEN 1 ELSE 0 END) / count(p), 1) AS persen_tepat_waktu
ORDER BY selesai DESC;

MATCH (r:RT)<-[:TINGGAL_DI]-(:Warga)-[:MENGAJUKAN]->(p:Peminjaman)
WHERE p.status IN ['dipinjam', 'terlambat', 'dikembalikan']
WITH r, count(p) AS total,
     sum(CASE WHEN p.status = 'terlambat' OR p.telat_hari > 0 THEN 1 ELSE 0 END) AS telat
RETURN r.rt_id AS rt, total, telat, round(100.0 * telat / total, 1) AS persen_telat
ORDER BY rt;

MATCH (p:Peminjaman {status: 'dikembalikan'}) WHERE p.label_risiko IS NOT NULL
RETURN p.label_risiko AS label_risiko, count(p) AS jumlah,
       round(100.0 * sum(CASE WHEN p.telat_hari > 0 THEN 1 ELSE 0 END) / count(p), 1) AS persen_benar_telat
ORDER BY label_risiko;

MATCH (b:Barang {barang_id: 1}) RETURN b.nama, b.aktif;

MATCH (b:Barang {barang_id: 1}) SET b.aktif = false RETURN b.nama, b.aktif;

MATCH (b:Barang) RETURN b.aktif AS aktif, count(*) AS jumlah;
