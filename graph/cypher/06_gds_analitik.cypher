RETURN gds.version() AS gdsVersion;

CALL gds.graph.drop('pwSosial', false) YIELD graphName RETURN graphName;
CALL gds.graph.project('pwSosial', 'Warga',
  {MENJAMIN: {orientation: 'UNDIRECTED'}, PERNAH_MEMINJAM_DARI: {orientation: 'UNDIRECTED'}})
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount;

CALL gds.degree.stream('pwSosial') YIELD nodeId, score
RETURN gds.util.asNode(nodeId).nama AS warga, gds.util.asNode(nodeId).rt AS rt, score AS derajat
ORDER BY derajat DESC, warga LIMIT 10;

CALL gds.wcc.stream('pwSosial', {concurrency: 1}) YIELD nodeId, componentId
WITH componentId, gds.util.asNode(nodeId).nama AS warga ORDER BY warga
RETURN componentId, count(*) AS ukuran, collect(warga) AS anggota
ORDER BY ukuran DESC;

CALL gds.louvain.stream('pwSosial', {concurrency: 1}) YIELD nodeId, communityId
WITH communityId, gds.util.asNode(nodeId) AS w ORDER BY w.nama
RETURN communityId, count(*) AS ukuran, collect(w.nama) AS anggota, collect(DISTINCT w.rt) AS rt
ORDER BY ukuran DESC;
CALL gds.louvain.stats('pwSosial', {concurrency: 1})
YIELD communityCount, modularity, ranLevels
RETURN communityCount, modularity, ranLevels;

CALL gds.louvain.write('pwSosial', {writeProperty: 'komunitas', concurrency: 1})
YIELD communityCount, modularity RETURN communityCount, modularity;

CALL gds.fastRP.stream('pwSosial',
  {embeddingDimension: 8, iterationWeights: [0.0, 1.0, 1.0], randomSeed: 42, concurrency: 1})
YIELD nodeId, embedding
RETURN gds.util.asNode(nodeId).nama AS warga, embedding ORDER BY warga LIMIT 10;

CALL gds.graph.drop('pwPenjamin', false) YIELD graphName RETURN graphName;
CALL gds.graph.project('pwPenjamin', 'Warga', {MENJAMIN: {orientation: 'NATURAL'}})
YIELD graphName, nodeCount, relationshipCount
RETURN graphName, nodeCount, relationshipCount;
CALL gds.pageRank.stream('pwPenjamin', {maxIterations: 20, dampingFactor: 0.85, concurrency: 1})
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).nama AS warga, round(score, 3) AS pagerank,
       gds.util.asNode(nodeId).trust_score AS trust_score
ORDER BY pagerank DESC LIMIT 10;
CALL gds.pageRank.write('pwPenjamin',
  {writeProperty: 'pagerank', maxIterations: 20, dampingFactor: 0.85, concurrency: 1})
YIELD nodePropertiesWritten, ranIterations RETURN nodePropertiesWritten, ranIterations;

MATCH (a:Warga {warga_id: 5})-[:MENGAJUKAN]->(:Peminjaman)-[:ATAS]->(x:Barang)
WITH a, collect(DISTINCT x) AS A
MATCH (b:Warga)-[:MENGAJUKAN]->(:Peminjaman)-[:ATAS]->(y:Barang) WHERE b <> a
WITH a, A, b, collect(DISTINCT y) AS B
WITH a, b, size([v IN A WHERE v IN B]) AS irisan, size(A) + size(B) - size([v IN A WHERE v IN B]) AS gabungan
WHERE irisan > 0
RETURN b.nama AS warga_mirip, irisan, round(toFloat(irisan) / gabungan, 2) AS jaccard
ORDER BY jaccard DESC, warga_mirip LIMIT 5;

CALL gds.graph.drop('pwSosial', false) YIELD graphName RETURN graphName;
CALL gds.graph.drop('pwPenjamin', false) YIELD graphName RETURN graphName;
