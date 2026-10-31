MATCH (n:PinjamWarga) UNWIND labels(n) AS l
WITH l WHERE l <> 'PinjamWarga'
RETURN l AS label, count(*) AS jumlah ORDER BY label;

MATCH (:PinjamWarga)-[r]->(:PinjamWarga)
RETURN type(r) AS tipe, count(*) AS jumlah ORDER BY tipe;

MATCH (p:Peminjaman) WITH p LIMIT 1
MATCH (b:Barang) WITH p, b LIMIT 1
RETURN valueType(p.peminjaman_id) AS id_type,
       valueType(p.tgl_mulai) AS tanggal_type,
       valueType(b.aktif) AS aktif_type;

MATCH (p:Peminjaman)
WHERE NOT EXISTS { MATCH (:Warga)-[:MENGAJUKAN]->(p) }
   OR NOT EXISTS { MATCH (p)-[:ATAS]->(:Barang) }
RETURN p.peminjaman_id AS peminjaman_yatim;

MATCH path = (w:Warga)-[:MENGAJUKAN]->(p:Peminjaman)-[:ATAS]->(b:Barang)<-[:MEMILIKI]-(o:Warga)
RETURN path LIMIT 15;
