LOAD CSV WITH HEADERS FROM 'file:///pw_warga.csv' AS row
MATCH (w:Warga {warga_id: toInteger(row.warga_id)})
MATCH (r:RT {rt_id: row.rt_id})
MERGE (w)-[:TINGGAL_DI]->(r);

LOAD CSV WITH HEADERS FROM 'file:///pw_barang.csv' AS row
MATCH (w:Warga {warga_id: toInteger(row.pemilik_id)})
MATCH (b:Barang {barang_id: toInteger(row.barang_id)})
MATCH (k:Kategori {nama: row.kategori})
MERGE (w)-[:MEMILIKI]->(b)
MERGE (b)-[:TERMASUK]->(k);

LOAD CSV WITH HEADERS FROM 'file:///pw_peminjaman.csv' AS row
MATCH (w:Warga {warga_id: toInteger(row.peminjam_id)})
MATCH (p:Peminjaman {peminjaman_id: toInteger(row.peminjaman_id)})
MATCH (b:Barang {barang_id: toInteger(row.barang_id)})
MERGE (w)-[:MENGAJUKAN]->(p)
MERGE (p)-[:ATAS]->(b);

LOAD CSV WITH HEADERS FROM 'file:///pw_penjaminan.csv' AS row
MATCH (a:Warga {warga_id: toInteger(row.penjamin_id)})
MATCH (b:Warga {warga_id: toInteger(row.dijamin_id)})
MERGE (a)-[r:MENJAMIN]->(b)
SET r.sejak = date(row.sejak);

LOAD CSV WITH HEADERS FROM 'file:///pw_interaksi.csv' AS row
MATCH (a:Warga {warga_id: toInteger(row.peminjam_id)})
MATCH (b:Warga {warga_id: toInteger(row.pemilik_id)})
MERGE (a)-[r:PERNAH_MEMINJAM_DARI]->(b)
SET r.kali = toInteger(row.kali);
