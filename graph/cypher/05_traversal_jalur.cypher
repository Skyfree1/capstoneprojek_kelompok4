MATCH (w:Warga {warga_id: 5})-[:MENGAJUKAN]->(:Peminjaman)-[:ATAS]->(b:Barang)
      <-[:ATAS]-(:Peminjaman)<-[:MENGAJUKAN]-(lain:Warga)
WHERE lain <> w
RETURN lain.nama AS warga_lain, count(DISTINCT b) AS jumlah_barang_sama,
       collect(DISTINCT b.nama) AS barang_sama
ORDER BY jumlah_barang_sama DESC, warga_lain;

MATCH p = (penjamin:Warga)-[:MENJAMIN*1..3]->(w:Warga {warga_id: 5})
WHERE penjamin <> w
RETURN [n IN nodes(p) | n.nama] AS rantai, length(p) AS tingkat
ORDER BY tingkat, rantai;

MATCH p = (w:Warga)-[:MENGAJUKAN]->(:Peminjaman)-[:ATAS]->(:Barang)<-[:MEMILIKI]-(o:Warga)
WHERE w.warga_id = 5
RETURN [n IN nodes(p) | coalesce(n.nama, toString(n.peminjaman_id))] AS simpul,
       [r IN relationships(p) | type(r)] AS relasi, length(p) AS hop
LIMIT 5;

MATCH (a:Warga {warga_id: 1}), (b:Warga {warga_id: 20})
MATCH p = shortestPath((a)-[:MENJAMIN|PERNAH_MEMINJAM_DARI*..4]-(b))
RETURN [n IN nodes(p) | n.nama] AS simpul,
       [r IN relationships(p) | startNode(r).nama + ' -' + type(r) + '-> ' + endNode(r).nama] AS bacaan,
       length(p) AS hop;

MATCH (a:Warga {warga_id: 1}), (b:Warga {warga_id: 20})
MATCH p = allShortestPaths((a)-[:MENJAMIN|PERNAH_MEMINJAM_DARI*..4]-(b))
RETURN [n IN nodes(p) | n.nama] AS simpul, length(p) AS hop;

MATCH (penjamin:Warga)-[:MENJAMIN]->(w:Warga)-[:MENGAJUKAN]->(p:Peminjaman {status: 'terlambat'})
RETURN penjamin.nama AS penjamin, collect(DISTINCT w.nama) AS dijamin_yang_terlambat;
