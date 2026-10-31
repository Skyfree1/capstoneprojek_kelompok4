LOAD CSV WITH HEADERS FROM 'file:///pw_rt.csv' AS row
MERGE (r:PinjamWarga:RT {rt_id: row.rt_id})
SET r.nama = row.rt_id;

LOAD CSV WITH HEADERS FROM 'file:///pw_kategori.csv' AS row
MERGE (:PinjamWarga:Kategori {nama: row.nama});

LOAD CSV WITH HEADERS FROM 'file:///pw_warga.csv' AS row
MERGE (w:PinjamWarga:Warga {warga_id: toInteger(row.warga_id)})
SET w.nama = row.nama,
    w.rt = row.rt_id,
    w.reputasi = toInteger(row.reputasi),
    w.trust_score = toInteger(row.trust_score);

LOAD CSV WITH HEADERS FROM 'file:///pw_barang.csv' AS row
MERGE (b:PinjamWarga:Barang {barang_id: toInteger(row.barang_id)})
SET b.nama = row.nama,
    b.kategori = row.kategori,
    b.jumlah = toInteger(row.jumlah),
    b.aktif = (row.aktif = 'true');

LOAD CSV WITH HEADERS FROM 'file:///pw_peminjaman.csv' AS row
MERGE (p:PinjamWarga:Peminjaman {peminjaman_id: toInteger(row.peminjaman_id)})
SET p.tgl_mulai = date(row.tgl_mulai),
    p.tgl_jatuh_tempo = date(row.tgl_jatuh_tempo),
    p.tgl_kembali = CASE WHEN coalesce(row.tgl_kembali, '') = '' THEN null ELSE date(row.tgl_kembali) END,
    p.status = row.status,
    p.jumlah = toInteger(row.jumlah),
    p.telat_hari = toInteger(row.telat_hari),
    p.rating = toInteger(row.rating),
    p.risiko = toFloat(row.risiko),
    p.label_risiko = CASE WHEN coalesce(row.label_risiko, '') = '' THEN null ELSE row.label_risiko END;
